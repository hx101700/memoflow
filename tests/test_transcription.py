"""验证配置确认、媒体准备、BL执行和三格式交付流程。"""

import hashlib
import io
import json
import os
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from asr_runtime import MODEL
from asr_runtime.utils.auth import read_api_key
from asr_runtime.utils.bailian import BailianFailure
from asr_runtime.utils.environment import SetupError
from asr_runtime.utils.media import probe_audio
from asr_runtime.application.session import Session
from asr_runtime.application.recovery import finish_session
from asr_runtime.application.transcription import export_job, job_status, transcribe
from asr_runtime.utils.job_files import save_record
from asr_runtime.utils.files import file_fingerprint
from tests.support import RuntimeTestCase


def transcript_result(*texts):
    """构造带音轨和时间戳的合成转写结果。"""
    return {"transcripts": [
        {"channel_id": channel, "text": text, "sentences": [
            {"text": text, "begin_time": 100, "end_time": 900, "speaker_id": 0}
        ]}
        for channel, text in enumerate(texts or ("合成测试转写。",))
    ]}


class TranscriptionTests(RuntimeTestCase):
    def setUp(self):
        """准备独立项目、合成Key和BL进程替身。"""
        super().setUp()
        self.secret = "asr-transcription-synthetic-transcription-key"
        self.runtime.path(".env").write_text(
            f"DASHSCOPE_API_KEY={self.secret}\n", encoding="utf-8"
        )
        # 用例测试不安装或运行另一个CLI；参数长度检查仍走生产实现。
        command = patch("asr_runtime.utils.bailian.bl_command", side_effect=lambda runtime, args: [
            "node", str(runtime.bl_entry), *args, "--quiet"
        ])
        command.start()
        self.addCleanup(command.stop)
        execution = patch("asr_runtime.application.transcription.run_recognition", side_effect=self.write_result)
        self.cli = execution.start()
        self.addCleanup(execution.stop)

    def make_job(self, *, channels=1, diarization=True, enhancement="none", **options):
        """选择合成音频原文件、确认任务并关闭网页会话。"""
        session = Session(self.runtime)
        audio_bytes = io.BytesIO()
        with wave.open(audio_bytes, "wb") as audio:
            audio.setnchannels(channels)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0" * 32000 * channels)
        content = audio_bytes.getvalue()
        source = self.runtime.workspace / session.session_id / "合成录音.wav"
        source.parent.mkdir()
        source.write_bytes(content)
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=source):
            selection = session.select_audio("fixture-audio")
        payload = {
            "auth_mode": "api_key", "audio_id": selection["audio_id"],
            "diarization_enabled": diarization, "enhancement_mode": enhancement,
            "hotword_rows": [], "context": "",
            "json_directory": "default", "document_directory": "default",
            **options,
        }
        if enhancement in ("hotwords", "both"):
            workbook = Workbook()
            workbook.active.append(["text", "weight"])
            workbook.active.append(["合成术语", 5])
            workbook.active.append(["Qwen", 50])
            stream = io.BytesIO()
            workbook.save(stream)
            workbook.close()
            data = stream.getvalue()
            words = session.receive_hotwords("合成热词.xlsx", io.BytesIO(data), len(data))
            payload["hotword_rows"] = words["rows"]
        if enhancement in ("context", "both"):
            payload["context"] = "讨论合成术语与Qwen的识别效果。"
        try:
            preview = session.validate(payload)
            session.preview_ready(preview["validation_id"])
            receipt = session.confirm()
            config = json.loads(Path(receipt["config_path"]).read_text(encoding="utf-8"))
            return receipt["job_id"], config
        finally:
            session.cleanup()
            finish_session(self.runtime, session.session_id)

    @staticmethod
    def output_path(arguments):
        """从BL参数取得原始JSON保存路径。"""
        return Path(arguments[arguments.index("--out") + 1])

    def write_result(self, runtime, command, private):
        """保存合成BL结果供解析和文档导出。"""
        self.output_path(command.argv).write_text(
            json.dumps(transcript_result(), ensure_ascii=False), encoding="utf-8"
        )

    def test_handoff_authorization_executes_without_a_second_flag(self):
        """验证交接授权直接用于执行，配置阶段不再单独索取授权。"""
        job_id, config = self.make_job()
        self.assertTrue(config["execution_authorized"])
        self.assertTrue(job_status(self.runtime, job_id)["execution_authorized"])
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        self.assertEqual(report["authorization_source"], "session_handoff")
        self.cli.assert_called_once()

    def test_confirmation_checksum_matches_the_saved_utf8_bytes(self):
        """验证确认摘要对应实际保存的UTF-8配置字节。"""
        job_id, _ = self.make_job(enhancement="both")
        path = self.runtime.path(f".state/jobs/{job_id}/config.json")
        checksum = path.with_suffix(".sha256").read_text(encoding="ascii").strip()
        self.assertEqual(checksum, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_modified_snapshot_is_rejected_before_execution_is_claimed(self):
        """验证确认后配置变化时拒绝执行。"""
        for changed in ("context", "vocabulary", "audio_metadata", "recognition_options"):
            with self.subTest(changed=changed):
                job_id, config = self.make_job(enhancement="both")
                if changed == "context":
                    config["enhancement"]["context"] = "保存后修改的上下文。"
                elif changed == "vocabulary":
                    config["enhancement"]["hotwords"]["vocabulary"] = {"替换后的词": 5}
                elif changed == "audio_metadata":
                    config["audio"]["metadata"]["sample_rate"] = 8000
                else:
                    config["recognition_options"]["language_hints"] = ["en"]
                path = self.runtime.path(f".state/jobs/{job_id}/config.json")
                path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
                with self.assertRaisesRegex(SetupError, "配置发生变化"):
                    transcribe(self.runtime, job_id)
                self.assertFalse(path.parent.joinpath("execution").exists())
                self.cli.assert_not_called()

    def test_configuration_without_checksum_is_not_automatically_accepted(self):
        """验证缺少配置摘要时返回确认来源错误。"""
        job_id, _ = self.make_job()
        path = self.runtime.path(f".state/jobs/{job_id}/config.sha256")
        path.unlink()
        with self.assertRaisesRegex(SetupError, "缺少确认摘要"):
            transcribe(self.runtime, job_id)
        self.assertFalse(path.exists())
        self.assertFalse(path.parent.joinpath("execution").exists())
        self.cli.assert_not_called()

    def test_success_delivers_documents_and_never_reexecutes_the_saved_job(self):
        """验证成功任务交付三格式并复用执行记录。"""
        job_id, config = self.make_job()
        self.assertEqual(config["model"], "qwen-audio-3.1-asr-flash-filetrans")
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        self.assertEqual(report["cloud_outcome"], "result_received")
        self.assertTrue(report["documents_ready"])
        self.assertTrue(Path(report["json_path"]).is_file())
        self.assertEqual(job_status(self.runtime, job_id), report)
        self.assertEqual(transcribe(self.runtime, job_id), report)
        self.cli.assert_called_once()
        config_text = self.runtime.path(f".state/jobs/{job_id}/config.json").read_text(encoding="utf-8")
        self.assertTrue(json.loads(config_text)["execution_authorized"])
        self.assertNotIn(self.secret, config_text + json.dumps(report))

    def test_different_confirmed_model_is_not_uploaded_or_changed(self):
        """验证模型更新后旧任务需重新配置，原任务及结果保持不变。"""
        job_id, config = self.make_job()
        config["model"] = "qwen-audio-3.0-asr-flash-filetrans"
        path = self.runtime.path(f".state/jobs/{job_id}/config.json")
        content = json.dumps(config, ensure_ascii=False).encode("utf-8")
        checksum = hashlib.sha256(content).hexdigest().encode("ascii")
        path.write_bytes(content)
        path.with_suffix(".sha256").write_bytes(checksum)
        with self.assertRaisesRegex(SetupError, "重新配置并确认新任务"):
            transcribe(self.runtime, job_id)
        self.assertFalse(path.parent.joinpath("execution").exists())
        self.assertEqual(path.read_bytes(), content)
        self.assertEqual(path.with_suffix(".sha256").read_bytes(), checksum)
        self.assertEqual(job_status(self.runtime, job_id)["status"], "CONFIGURED")
        self.cli.assert_not_called()

    def test_saved_configuration_requires_a_model_name(self):
        """验证本地任务配置仍要求非空字符串模型名称。"""
        for model in (None, "", " \t", []):
            with self.subTest(model=model):
                job_id, config = self.make_job()
                config["model"] = model
                path = self.runtime.path(f".state/jobs/{job_id}/config.json")
                content = json.dumps(config, ensure_ascii=False).encode("utf-8")
                path.write_bytes(content)
                path.with_suffix(".sha256").write_text(hashlib.sha256(content).hexdigest(), encoding="ascii")
                with self.assertRaises(SetupError):
                    job_status(self.runtime, job_id)
                self.assertFalse(path.parent.joinpath("execution").exists())
        self.cli.assert_not_called()

    def test_audio_and_vocabulary_snapshot_execute_after_web_session_cleanup(self):
        """验证网页关闭后通过音频和词典快照执行任务。"""
        job_id, config = self.make_job(channels=2, enhancement="both")
        audio = Path(config["audio"]["path"])
        self.assertTrue(audio.is_file())
        self.assertFalse(list(audio.parent.glob("*.xlsx")))
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        self.assertEqual(report["cloud_outcome"], "result_received")
        self.assertTrue(audio.is_file())
        self.assertFalse(list(audio.parent.glob("*.xlsx")))
        arguments = self.cli.call_args.args[1].argv
        self.assertEqual(json.loads(arguments[arguments.index("--vocabulary") + 1]),
                         config["enhancement"]["hotwords"]["vocabulary"])
        self.cli.assert_called_once()

    def test_unchanged_snapshot_avoids_excel_parsing_and_original_audio_probe(self):
        """验证执行复用确认信息并完成一次音频摘要核对。"""
        for channels in (1, 2):
            with self.subTest(channels=channels):
                job_id, config = self.make_job(channels=channels, enhancement="both",
                                               language_hint="zh", speaker_count=3)
                source = Path(config["audio"]["path"])
                converted = self.runtime.path(f".state/jobs/{job_id}/execution/mono.flac")

                def only_probe_new_copy(path):
                    """核对媒体探测对象为本次生成的FLAC。"""
                    self.assertEqual(path, converted, "不能重复探测已确认的源文件")
                    return probe_audio(path)

                # 多声道仍实际解码/混音；只允许探测新FLAC，源内容摘要只在执行前核对一次。
                with patch("asr_runtime.application.inputs.probe_audio", side_effect=AssertionError("重复探测原音频")), \
                        patch("asr_runtime.utils.media.probe_audio", side_effect=only_probe_new_copy) as probe, \
                        patch("asr_runtime.utils.hotwords.load_workbook", side_effect=AssertionError("重复解析Excel")), \
                        patch("asr_runtime.application.transcription.file_fingerprint", wraps=file_fingerprint) as fingerprint:
                    report = transcribe(self.runtime, job_id)
                self.assertEqual(report["status"], "JSON_READY")
                self.assertEqual(probe.call_count, 1 if channels == 2 else 0)
                fingerprint.assert_called_once_with(source)
                arguments = self.cli.call_args.args[1].argv
                self.assertIn("--context=" + config["enhancement"]["context"], arguments)
                self.assertEqual(json.loads(arguments[arguments.index("--vocabulary") + 1]),
                                 config["enhancement"]["hotwords"]["vocabulary"])

    def test_api_key_is_read_once_for_the_prepared_command(self):
        """验证命令准备读取一次Key并隐藏对象表示中的凭据。"""
        job_id, _ = self.make_job()
        with patch("asr_runtime.utils.auth.read_api_key", wraps=read_api_key) as read_key:
            report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        read_key.assert_called_once_with(self.runtime)
        command = self.cli.call_args.args[1]
        self.assertEqual(command.env["DASHSCOPE_API_KEY"], self.secret)
        self.assertNotIn(self.secret, repr(command))

    def test_console_execution_does_not_run_auth_status_or_read_dotenv(self):
        """验证控制台模式使用独立凭据环境执行识别。"""
        job_id, _ = self.make_job(auth_mode="console")
        with patch("asr_runtime.utils.bailian.console_status", side_effect=AssertionError("重复查询鉴权状态")), \
                patch("asr_runtime.utils.bailian._run_bl", side_effect=AssertionError("执行识别前启动了额外BL命令")), \
                patch("asr_runtime.utils.auth.read_api_key", side_effect=AssertionError("控制台模式读取了.env")):
            report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        self.assertNotIn("DASHSCOPE_API_KEY", self.cli.call_args.args[1].env)
        self.cli.assert_called_once()

    def test_concurrent_execution_enters_bl_only_once(self):
        """验证并发执行通过任务占用产生一次BL调用。"""
        job_id, _ = self.make_job()
        entered, release = threading.Event(), threading.Event()

        def block_cli(*args):
            """暂停BL替身以模拟同一任务的并发调用。"""
            entered.set()
            if not release.wait(5):
                raise AssertionError("测试未释放BL边界")
            self.write_result(*args)

        self.cli.side_effect = block_cli
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(transcribe, self.runtime, job_id)
            try:
                self.assertTrue(entered.wait(5))
                second = pool.submit(transcribe, self.runtime, job_id)
                observed = second.result(timeout=5)
                self.assertEqual(observed["status"], "RUNNING")
                self.assertEqual(self.cli.call_count, 1)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5)["status"], "JSON_READY")

    def test_crashed_execution_marker_prevents_resubmission(self):
        """验证执行记录缺失时返回云端结果未知状态。"""
        job_id, _ = self.make_job()
        self.runtime.path(f".state/jobs/{job_id}/execution").mkdir()
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "OUTCOME_UNKNOWN")
        self.assertEqual(report["cloud_outcome"], "unknown")
        self.cli.assert_not_called()

    def test_changed_audio_bytes_are_rejected_even_with_same_size_and_mtime(self):
        """验证音频摘要识别同大小和修改时间下的内容变化。"""
        job_id, config = self.make_job()
        path = Path(config["audio"]["path"])
        before = path.stat()
        content = bytearray(path.read_bytes())
        content[-1] ^= 1
        path.write_bytes(content)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "STOPPED")
        self.assertEqual(report["cloud_outcome"], "not_started")
        self.cli.assert_not_called()

    def test_mtime_change_alone_does_not_reject_identical_audio(self):
        """验证音频内容相同时修改时间变化仍可执行。"""
        job_id, config = self.make_job()
        path = Path(config["audio"]["path"])
        before = path.stat()
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        self.cli.assert_called_once()

    def test_missing_key_after_confirmation_stops_without_cloud_request(self):
        """验证运行Key缺失时返回准备阶段的停止状态。"""
        job_id, _ = self.make_job()
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=\n", encoding="utf-8")
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "STOPPED")
        self.assertEqual(report["cloud_outcome"], "not_started")
        self.cli.assert_not_called()

    def test_stereo_is_converted_once_and_original_file_is_preserved(self):
        """验证多声道生成单声道FLAC并保留源内容和采样率。"""
        job_id, config = self.make_job(channels=2)
        original = Path(config["audio"]["path"])
        original_bytes = original.read_bytes()
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        arguments = self.cli.call_args.args[1].argv
        uploaded = Path(arguments[arguments.index("--url") + 1])
        self.assertNotEqual(uploaded, original)
        self.assertEqual(uploaded.suffix, ".flac")
        metadata = probe_audio(uploaded)
        self.assertEqual(metadata.channels, 1)
        self.assertEqual(metadata.sample_rate, 16000)
        self.assertAlmostEqual(metadata.duration_seconds, 1.0)
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertEqual(probe_audio(original).channels, 2)

    def test_mono_or_disabled_diarization_uses_existing_audio(self):
        """验证单声道或关闭说话人区分时使用既有音频。"""
        for channels, diarization in ((1, True), (2, False)):
            with self.subTest(channels=channels, diarization=diarization):
                self.cli.reset_mock()
                job_id, config = self.make_job(channels=channels, diarization=diarization)
                report = transcribe(self.runtime, job_id)
                self.assertEqual(report["status"], "JSON_READY")
                arguments = self.cli.call_args.args[1].argv
                self.assertEqual(arguments[arguments.index("--url") + 1], config["audio"]["path"])
                self.assertEqual("--diarization" in arguments, diarization)
                self.assertNotIn("--speaker-count", arguments)
                self.assertFalse(self.runtime.path(f".state/jobs/{job_id}/execution/mono.flac").exists())

    def test_actual_upload_size_limit_applies_after_mono_conversion(self):
        """验证转换副本超出上传大小限制时停止准备。"""
        job_id, _ = self.make_job(channels=2)
        # 降低阈值以覆盖超限，不创建1GB测试文件；探测和FLAC转换仍真实执行。
        with patch("asr_runtime.application.rules.MAX_UPLOAD_BYTES", 1):
            report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "STOPPED")
        self.assertEqual(report["cloud_outcome"], "not_started")
        converted = self.runtime.path(f".state/jobs/{job_id}/execution/mono.flac")
        self.assertEqual(probe_audio(converted).channels, 1)
        self.cli.assert_not_called()

    def test_dual_enhancement_and_recognition_options_reach_the_same_request(self):
        """验证热词、上下文、语言和人数共同进入转写命令。"""
        job_id, config = self.make_job(enhancement="both", language_hint="zh", speaker_count=3)
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        _, command, private = self.cli.call_args.args
        arguments = command.argv
        self.assertEqual(command.env["DASHSCOPE_API_KEY"], self.secret)
        # 取出指定CLI选项之后的参数值。
        values = lambda flag: arguments[arguments.index(flag) + 1]
        self.assertEqual(values("--model"), MODEL)
        self.assertEqual(values("--language"), "zh")
        self.assertEqual(values("--speaker-count"), "3")
        self.assertIn("--context=" + config["enhancement"]["context"], arguments)
        self.assertEqual(json.loads(values("--vocabulary")), {"合成术语": 5, "Qwen": 50})
        self.assertIn("合成术语", private)
        self.assertIn(config["enhancement"]["context"], private)
        self.assertNotIn(self.secret, json.dumps(arguments))

    def test_existing_json_is_preserved_without_starting_bl(self):
        """验证结果文件已存在时保留原内容并停止准备。"""
        job_id, config = self.make_job()
        destination = Path(config["json_directory"]) / "transcription.json"
        destination.parent.mkdir(parents=True)
        destination.write_text("previous result", encoding="utf-8")
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "STOPPED")
        self.assertEqual(report["cloud_outcome"], "not_started")
        self.assertEqual(destination.read_text(encoding="utf-8"), "previous result")
        self.cli.assert_not_called()

    def test_final_json_destination_in_skill_stops_before_bl(self):
        """验证最终JSON目录在Skill中时停止执行并保留资源。"""
        job_id, config = self.make_job()
        destination = self.runtime.skill_root / job_id / "json"
        config["json_directory"] = str(destination)
        path = self.runtime.path(f".state/jobs/{job_id}/config.json")
        content = json.dumps(config, ensure_ascii=False).encode("utf-8")
        path.write_bytes(content)
        path.with_suffix(".sha256").write_text(hashlib.sha256(content).hexdigest(), encoding="ascii")
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "STOPPED")
        self.assertEqual(report["cloud_outcome"], "not_started")
        self.assertIn("Skill安装目录", report["message"])
        self.assertFalse(destination.parent.exists())
        self.cli.assert_not_called()

    def test_exit_zero_requires_usable_json_and_keeps_unusable_files(self):
        """验证BL退出成功后检查JSON并保留异常结果文件。"""
        empty_sentences = {"transcripts": [{"sentences": []}]}
        cases = [None, "", "not json", "[]", json.dumps([transcript_result()]),
                 json.dumps({"transcripts": []}), json.dumps(empty_sentences),
                 json.dumps(transcript_result("   "))]
        for content in cases:
            with self.subTest(content=content):
                self.cli.reset_mock()
                job_id, config = self.make_job()

                def save_unusable(runtime, command, private):
                    """模拟BL返回缺失或异常JSON结果。"""
                    if content is not None:
                        self.output_path(command.argv).write_text(content, encoding="utf-8")

                self.cli.side_effect = save_unusable
                report = transcribe(self.runtime, job_id)
                self.assertEqual(report["status"], "STOPPED")
                self.assertEqual(report["cloud_outcome"], "unknown")
                self.assertFalse(report["documents_ready"])
                self.cli.assert_called_once()
                path = Path(config["json_directory"]) / "transcription.json"
                self.assertEqual(path.exists(), content is not None)
                if content is not None:
                    self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_invalid_sentence_timestamps_do_not_become_success(self):
        """验证异常句子时间戳返回停止状态并保留结果位置。"""
        for begin, end in ((True, 900), (100, 99), (-1, 900), (0, 1.5)):
            with self.subTest(begin=begin, end=end):
                job_id, _ = self.make_job()
                result = transcript_result()
                result["transcripts"][0]["sentences"][0].update(begin_time=begin, end_time=end)

                def write_invalid(runtime, command, private):
                    """保存当前场景的异常时间戳结果。"""
                    self.output_path(command.argv).write_text(json.dumps(result), encoding="utf-8")

                self.cli.side_effect = write_invalid
                report = transcribe(self.runtime, job_id)
                self.assertEqual(report["status"], "STOPPED")
                self.assertTrue(Path(report["json_path"]).is_file())

    def test_multiple_result_tracks_are_kept_without_normalization(self):
        """验证原JSON保留多音轨和上游扩展字段。"""
        job_id, _ = self.make_job()
        result = transcript_result("第一音轨。", "第二音轨。")
        result["provider_extension"] = {"preserve": True}
        text = json.dumps(result, ensure_ascii=False, indent=4) + "\n"

        def write_tracks(runtime, command, private):
            """按既定字节保存含多个音轨的BL结果。"""
            self.output_path(command.argv).write_text(text, encoding="utf-8")

        self.cli.side_effect = write_tracks
        report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        self.assertEqual(report["result"]["audio_tracks"], 2)
        self.assertEqual(report["result"]["sentences"], 2)
        self.assertEqual(Path(report["json_path"]).read_text(encoding="utf-8"), text)

    def test_bl_start_failure_and_interrupted_wait_have_distinct_outcomes(self):
        """验证进程启动失败和等待中断返回对应云端结果。"""
        for started, code in ((False, "LOCAL_PROCESS_START_FAILED"), (True, "LOCAL_WAIT_INTERRUPTED")):
            with self.subTest(started=started):
                self.cli.reset_mock()
                job_id, _ = self.make_job()
                self.cli.side_effect = BailianFailure(
                    {"source": "local", "code": code, "explanation": "合成的BL边界故障"},
                    started=started,
                )
                report = transcribe(self.runtime, job_id)
                self.assertEqual(report["status"], "STOPPED")
                self.assertEqual(report["cloud_outcome"], "unknown" if started else "not_started")
                self.assertEqual(report["error"]["code"], code)
                self.assertEqual(transcribe(self.runtime, job_id), report)
                self.cli.assert_called_once()

    def test_verified_result_does_not_need_another_existence_probe(self):
        """验证结果解析完成后返回JSON成功回执。"""
        job_id, config = self.make_job()
        destination = Path(config["json_directory"]) / "transcription.json"
        original_is_file = Path.is_file

        def reject_result_probe(path):
            """模拟结果JSON探测错误并保留其他真实文件检查。"""
            if path == destination:
                raise PermissionError("private synthetic result path")
            return original_is_file(path)

        with patch.object(Path, "is_file", reject_result_probe):
            report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        self.assertTrue(report["documents_ready"])
        self.assertEqual(report["json_path"], str(destination))
        self.cli.assert_called_once()

    def test_record_failure_before_bl_reports_not_started_without_retry(self):
        """验证准备记录保存失败时说明故障阶段和云端状态。"""
        for failed_status in ("PREPARING", "RUNNING"):
            with self.subTest(failed_status=failed_status):
                self.cli.reset_mock()
                job_id, _ = self.make_job()
                attempts = []

                def save_until_failure(directory, report):
                    """保存前序状态并在指定阶段注入文件错误。"""
                    attempts.append(report["status"])
                    if report["status"] == failed_status:
                        raise PermissionError("private synthetic path")
                    save_record(directory, report)

                with patch("asr_runtime.application.transcription.save_record", side_effect=save_until_failure):
                    report = transcribe(self.runtime, job_id)
                self.assertEqual(report["status"], "STOPPED")
                self.assertEqual(report["cloud_outcome"], "not_started")
                self.assertFalse(report["documents_ready"])
                self.assertEqual(report["record_error"]["phase"], "save_status")
                self.assertEqual(report["record_error"]["attempted_status"], failed_status)
                self.assertEqual(report["record_error"]["error_type"], "PermissionError")
                self.assertNotIn("private synthetic", json.dumps(report))
                self.assertEqual(attempts, ["PREPARING"] if failed_status == "PREPARING" else ["PREPARING", "RUNNING"])
                transcribe(self.runtime, job_id)
                self.cli.assert_not_called()

    def test_success_record_failure_preserves_json_and_does_not_restart(self):
        """验证成功记录保存失败时保留JSON和执行占用。"""
        job_id, _ = self.make_job()
        attempts = []

        def fail_success_record(directory, report):
            """保存准备和运行记录并模拟成功记录写入失败。"""
            attempts.append(report["status"])
            if report["status"] == "JSON_READY":
                raise OSError("private synthetic disk failure")
            save_record(directory, report)

        with patch("asr_runtime.application.transcription.save_record", side_effect=fail_success_record), \
             patch("asr_runtime.application.transcription.export_documents") as export:
            report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "JSON_READY")
        self.assertEqual(report["cloud_outcome"], "result_received")
        self.assertEqual(report["record_error"]["attempted_status"], "JSON_READY")
        self.assertEqual(report["record_error"]["error_type"], "OSError")
        self.assertNotIn("private synthetic", json.dumps(report))
        self.assertFalse(report["documents_ready"])
        content = Path(report["json_path"]).read_bytes()
        self.assertEqual(report["result"]["sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(attempts, ["PREPARING", "RUNNING", "JSON_READY"])
        export.assert_not_called()
        self.assertEqual(job_status(self.runtime, job_id)["status"], "RUNNING")
        with self.assertRaisesRegex(SetupError, "尚无"):
            export_job(self.runtime, job_id)
        transcribe(self.runtime, job_id)
        self.cli.assert_called_once()

    def test_local_failure_explains_phase_and_type_without_private_text(self):
        """验证本地故障报告阶段、异常类型和脱敏说明。"""
        cases = (
            ("prepare_input", SetupError("已知的输入问题"), "已知的输入问题", "not_started"),
            ("prepare_input", OSError("private synthetic path"), "文件操作失败", "not_started"),
            ("prepare_input", RuntimeError("private synthetic content"), "程序发生异常", "not_started"),
            ("prepare_input", KeyboardInterrupt("private synthetic content"), "操作已中断", "not_started"),
            ("load_transcript", TypeError("private synthetic transcript"), "程序发生异常", "unknown"),
        )
        for function, error, message, outcome in cases:
            with self.subTest(function=function, error=type(error).__name__):
                self.cli.reset_mock()
                job_id, _ = self.make_job()
                with patch(f"asr_runtime.application.transcription.{function}", side_effect=error):
                    report = transcribe(self.runtime, job_id)
                self.assertEqual(report["status"], "STOPPED")
                self.assertEqual(report["cloud_outcome"], outcome)
                self.assertEqual(report["error"]["phase"], "read_result" if function == "load_transcript" else "prepare_input")
                self.assertEqual(report["error"]["error_type"], type(error).__name__)
                self.assertIn(message, report["message"])
                self.assertNotIn("private synthetic", json.dumps(report))
                self.assertEqual(self.cli.call_count, 1 if function == "load_transcript" else 0)

    def test_stopped_record_failure_keeps_original_error(self):
        """验证停止记录保存失败时保留最初故障原因。"""
        job_id, _ = self.make_job()

        def fail_stopped_record(directory, report):
            """保存准备记录并模拟停止记录写入失败。"""
            if report["status"] == "STOPPED":
                raise OSError("private synthetic disk failure")
            save_record(directory, report)

        with patch("asr_runtime.application.transcription.prepare_input", side_effect=SetupError("已知输入错误")), \
             patch("asr_runtime.application.transcription.save_record", side_effect=fail_stopped_record):
            report = transcribe(self.runtime, job_id)
        self.assertEqual(report["status"], "STOPPED")
        self.assertEqual(report["cloud_outcome"], "not_started")
        self.assertEqual(report["error"]["explanation"], "已知输入错误")
        self.assertEqual(report["record_error"]["attempted_status"], "STOPPED")
        self.assertNotIn("private synthetic", json.dumps(report))
        self.cli.assert_not_called()
