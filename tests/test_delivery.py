"""验证固定目录导出、同名替换和格式失败处理。"""

import hashlib
import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from docx import Document
from openpyxl import load_workbook

from asr_runtime import MODEL
from asr_runtime.__main__ import main
from asr_runtime.utils.documents import DocumentError, write_xlsx
from asr_runtime.utils.files import write_json_atomic
from asr_runtime.utils.environment import SetupError
from asr_runtime.utils.results import load_transcript
from asr_runtime.utils.documents import timestamp
from asr_runtime.application.transcription import export_job, job_status, transcribe
from tests.support import RuntimeTestCase


class DeliveryTests(RuntimeTestCase):
    def setUp(self):
        """准备已保存任务、合成JSON和文档目录。"""
        super().setUp()
        self.job_id = "a" * 32
        self.root = self.runtime.path(f".state/jobs/{self.job_id}")
        (self.root / "execution").mkdir(parents=True)
        base = self.runtime.output_root / self.job_id
        self.config = {"schema_version": 1, "job_id": self.job_id, "model": MODEL,
                       "region": "cn-beijing", "status": "CONFIGURED",
                       "execution_authorized": True, "confirmed_at": "synthetic-time",
                       "json_directory": str(base / "json"),
                       "document_directory": str(base / "documents"),
                       "audio": {"name": "合成录音.wav"}}
        self.save_config()
        self.json_path = base / "json/transcription.json"
        self.json_path.parent.mkdir(parents=True)
        self.json_path.write_text(json.dumps({
            "file_url": "https://example.invalid/private-result?signature=synthetic-secret",
            "transcripts": [{"channel_id": 0, "sentences": [
                {"text": "合成文本。", "begin_time": 1, "end_time": 1501, "speaker_id": 0},
                {"text": "", "begin_time": 1501, "end_time": 1501},
            ]}, {"channel_id": 2, "sentences": [
                {"text": "=HYPERLINK(\"https://example.invalid\")", "begin_time": 0, "end_time": 1234},
            ]}]
        }, ensure_ascii=False), encoding="utf-8")
        self.save_execution()
        cloud = patch("asr_runtime.application.transcription.run_recognition", side_effect=AssertionError("local export must not call BL"))
        self.cloud = cloud.start()
        self.addCleanup(cloud.stop)

    def save_config(self):
        """保存合成任务配置及对应内容摘要。"""
        content = json.dumps(self.config, ensure_ascii=False).encode("utf-8")
        (self.root / "config.json").write_bytes(content)
        (self.root / "config.sha256").write_text(hashlib.sha256(content).hexdigest(), encoding="ascii")

    def save_execution(self, **changes):
        """保存测试用执行状态与结果摘要。"""
        report = {"job_id": self.job_id, "status": "JSON_READY",
                  "cloud_outcome": "result_received", "json_path": str(self.json_path),
                  "result": load_transcript(self.json_path).summary()}
        report.update(changes)
        (self.root / "execution/status.json").write_text(json.dumps(report), encoding="utf-8")

    def test_existing_json_exports_without_key_audio_or_bl_and_preserves_source(self):
        """验证已有JSON独立导出并保留原结果。"""
        original = self.json_path.read_bytes()
        report = export_job(self.runtime, self.job_id)
        self.assertTrue(report["documents_ready"])
        self.assertEqual(report["delivery"]["status"], "COMPLETE")
        self.assertEqual(set(report["delivery"]["files"]), {"xlsx", "docx", "md"})
        for record in report["delivery"]["files"].values():
            content = Path(record["path"]).read_bytes()
            self.assertEqual(len(content), record["bytes"])
            self.assertNotIn("sha256", record)
        self.assertEqual(report["result"]["sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(self.json_path.read_bytes(), original)
        self.cloud.assert_not_called()
        self.assertNotIn("delivery", job_status(self.runtime, self.job_id))
        self.assertFalse((self.root / "delivery").exists())

    def test_one_format_failure_retains_other_formats_and_never_retries(self):
        """验证单格式失败保留其他成品且各格式调用一次。"""
        with patch("asr_runtime.application.delivery.write_docx", side_effect=RuntimeError("private transcript in exception")) as writer:
            report = export_job(self.runtime, self.job_id)
        writer.assert_called_once()
        self.assertFalse(report["documents_ready"])
        self.assertEqual(report["status"], "JSON_READY")
        self.assertEqual(report["cloud_outcome"], "result_received")
        self.assertEqual(report["delivery"]["status"], "PARTIAL")
        self.assertEqual(report["delivery"]["files"]["docx"]["error_type"], "RuntimeError")
        self.assertIn("程序发生异常", report["delivery"]["files"]["docx"]["message"])
        self.assertNotIn("磁盘", report["delivery"]["files"]["docx"]["message"])
        self.assertNotIn("private transcript", json.dumps(report))
        for extension in ("xlsx", "md"):
            self.assertTrue(Path(report["delivery"]["files"][extension]["path"]).is_file())
        repeated = transcribe(self.runtime, self.job_id)
        self.assertEqual(repeated["status"], "JSON_READY")
        self.assertNotIn("delivery", repeated)
        self.cloud.assert_not_called()

    def test_known_document_error_and_filesystem_error_have_specific_messages(self):
        """验证格式错误和文件系统错误有对应说明。"""
        for error, message in ((DocumentError("已知格式限制"), "已知格式限制"),
                               (OSError("private path"), "目录权限")):
            with self.subTest(error=type(error).__name__), \
                 patch("asr_runtime.application.delivery.write_docx", side_effect=error):
                report = export_job(self.runtime, self.job_id)
            failure = report["delivery"]["files"]["docx"]
            self.assertIn(message, failure["message"])
            self.assertNotIn("private path", json.dumps(report))
            self.assertEqual(report["delivery"]["status"], "PARTIAL")

    def test_unexpected_serializer_error_is_not_reported_as_disk_failure(self):
        """验证序列化异常返回对应的程序错误说明。"""
        with patch("asr_runtime.utils.documents.Workbook.save", side_effect=ValueError("private transcript")):
            report = export_job(self.runtime, self.job_id)
        failure = report["delivery"]["files"]["xlsx"]
        self.assertEqual(failure["error_type"], "ValueError")
        self.assertIn("程序发生异常", failure["message"])
        self.assertNotIn("目录", failure["message"])
        self.assertNotIn("private transcript", json.dumps(report))
        self.assertEqual(report["delivery"]["status"], "PARTIAL")

    def test_explicit_reexport_replaces_the_same_three_files(self):
        """验证重导使用固定目录并替换三个同名文件。"""
        first = export_job(self.runtime, self.job_id)["delivery"]
        expected = {Path(self.config["document_directory"]) / f"transcription.{ext}"
                    for ext in ("xlsx", "docx", "md")}
        for record in first["files"].values():
            Path(record["path"]).write_bytes(b"synthetic edited document")
        second = export_job(self.runtime, self.job_id)["delivery"]
        self.assertEqual(second["status"], "COMPLETE")
        for extension, record in first["files"].items():
            self.assertEqual(record["path"], second["files"][extension]["path"])
            self.assertNotEqual(Path(record["path"]).read_bytes(), b"synthetic edited document")
        self.assertEqual(set(Path(self.config["document_directory"]).iterdir()), expected)
        self.assertFalse((self.root / "delivery").exists())
        self.assertFalse((self.root / "exports").exists())
        self.cloud.assert_not_called()

    def test_overlapping_exports_do_not_replace_each_others_temporary_files(self):
        """验证两次导出交错时各自发布成功，不互删临时文档。"""
        ready, release = threading.Event(), threading.Event()
        lock = threading.Lock()
        paths = []

        def pause_first_xlsx(transcript, path, **metadata):
            """首轮真实Excel生成后暂停，等待第二轮完成再发布。"""
            with lock:
                paths.append(path)
                first = len(paths) == 1
            write_xlsx(transcript, path, **metadata)
            if first:
                ready.set()
                self.assertTrue(release.wait(5), "测试未释放首轮导出")

        with patch("asr_runtime.application.delivery.write_xlsx", side_effect=pause_first_xlsx), \
                ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(export_job, self.runtime, self.job_id)
            try:
                self.assertTrue(ready.wait(5), "首轮Excel尚未生成")
                second = pool.submit(export_job, self.runtime, self.job_id).result(timeout=5)
            finally:
                release.set()
            first_report = first.result(timeout=5)
        self.assertNotEqual(paths[0], paths[1])
        for report in (first_report, second):
            self.assertEqual(report["delivery"]["status"], "COMPLETE")
            self.assertTrue(report["documents_ready"])
        destination = Path(self.config["document_directory"])
        self.assertEqual({path.name for path in destination.iterdir()},
                         {"transcription.xlsx", "transcription.docx", "transcription.md"})
        self.cloud.assert_not_called()

    def test_overlapping_records_keep_their_own_temporary_files(self):
        """验证同一JSON目标的交错发布不删除另一调用的临时记录。"""
        destination = self.root / "audit-record.json"
        ready, release = threading.Event(), threading.Event()
        lock = threading.Lock()
        paths = []
        replace = Path.replace

        def pause_first_replace(path, target):
            """暂停首轮记录替换，让第二轮先完成发布。"""
            with lock:
                paths.append(path)
                first = len(paths) == 1
            if first:
                ready.set()
                self.assertTrue(release.wait(5), "测试未释放首轮记录")
            return replace(path, target)

        with patch.object(Path, "replace", autospec=True, side_effect=pause_first_replace), \
                ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(write_json_atomic, destination, {"writer": "first"})
            try:
                self.assertTrue(ready.wait(5), "首轮记录尚未写入")
                second = pool.submit(write_json_atomic, destination, {"writer": "second"})
                second.result(timeout=5)
            finally:
                release.set()
            first.result(timeout=5)
        self.assertNotEqual(paths[0], paths[1])
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), {"writer": "first"})
        self.assertFalse(list(self.root.glob("audit-record.json.*.tmp")))

    def test_failed_record_replacement_preserves_target_and_cleans_its_temporary_file(self):
        """验证记录替换失败保留原内容并移除本次临时记录。"""
        destination = self.root / "audit-record.json"
        destination.write_text('{"writer":"original"}', encoding="utf-8")
        with patch.object(Path, "replace", side_effect=PermissionError("synthetic target locked")), \
                self.assertRaises(PermissionError):
            write_json_atomic(destination, {"writer": "new"})
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), {"writer": "original"})
        self.assertFalse(list(self.root.glob("audit-record.json.*.tmp")))

    def test_failed_reexport_preserves_the_existing_document(self):
        """验证重导写入失败时保留已有成品并完成其他格式。"""
        first = export_job(self.runtime, self.job_id)["delivery"]
        document = Path(first["files"]["docx"]["path"])
        original = document.read_bytes()

        def fail_docx(transcript, path, **metadata):
            """模拟临时Word写到一半时发生文件错误。"""
            path.write_bytes(b"synthetic incomplete document")
            raise OSError("synthetic write failure")

        with patch("asr_runtime.application.delivery.write_docx", side_effect=fail_docx) as writer:
            report = export_job(self.runtime, self.job_id)
        writer.assert_called_once()
        self.assertEqual(document.read_bytes(), original)
        self.assertEqual(report["delivery"]["status"], "PARTIAL")
        self.assertEqual(report["delivery"]["files"]["docx"]["status"], "FAILED")
        self.assertFalse(list(document.parent.glob("*.partial-*")))
        for extension in ("xlsx", "md"):
            self.assertEqual(report["delivery"]["files"][extension]["status"], "READY")
        self.assertNotIn("delivery", job_status(self.runtime, self.job_id))
        self.cloud.assert_not_called()

    def test_locked_target_preserves_the_existing_document(self):
        """验证同名文件被占用时报告替换失败并保留旧文件。"""
        first = export_job(self.runtime, self.job_id)["delivery"]
        document = Path(first["files"]["docx"]["path"])
        original = document.read_bytes()
        replace = Path.replace

        def refuse_word_replacement(source, target):
            """模拟目标Word被其他程序占用，其余文件照常发布。"""
            if Path(target) == document:
                raise PermissionError("synthetic file in use")
            return replace(source, target)

        with patch.object(Path, "replace", autospec=True, side_effect=refuse_word_replacement):
            report = export_job(self.runtime, self.job_id)
        self.assertEqual(document.read_bytes(), original)
        self.assertEqual(report["delivery"]["status"], "PARTIAL")
        self.assertEqual(report["delivery"]["files"]["docx"]["error_type"], "PermissionError")
        self.cloud.assert_not_called()

    def test_changed_json_after_recognition_is_rejected(self):
        """验证识别后JSON内容改变时拒绝导出。"""
        self.json_path.write_bytes(self.json_path.read_bytes() + b"\n")
        with self.assertRaisesRegex(SetupError, "发生变化"):
            export_job(self.runtime, self.job_id)
        self.assertFalse((self.root / "delivery").exists())

    def test_result_without_digest_is_not_exported_or_resubmitted(self):
        """验证结果摘要缺失时返回导出来源错误。"""
        self.save_execution(result={"audio_tracks": 2, "sentences": 3})
        with self.assertRaisesRegex(SetupError, "缺少结果JSON摘要"):
            export_job(self.runtime, self.job_id)
        self.assertFalse((self.root / "delivery").exists())
        self.cloud.assert_not_called()

    def test_no_export_when_recognition_did_not_finish(self):
        """验证识别进行中拒绝导出。"""
        self.save_execution(status="RUNNING")
        with self.assertRaisesRegex(SetupError, "尚无"):
            export_job(self.runtime, self.job_id)
        self.assertFalse((self.root / "delivery").exists())

    def test_unwritable_output_is_local_failure_and_preserves_json(self):
        """验证保存目录写入失败时保留JSON并报告导出失败。"""
        Path(self.config["document_directory"]).write_text("existing file", encoding="utf-8")
        report = export_job(self.runtime, self.job_id)
        self.assertEqual(report["delivery"]["status"], "FAILED")
        self.assertEqual(report["status"], "JSON_READY")
        self.assertFalse(report["documents_ready"])
        self.assertTrue(self.json_path.is_file())

    def test_export_destination_in_skill_is_rejected_and_json_is_preserved(self):
        """验证最终文档目录在Skill中时保留JSON并报告本地失败。"""
        destination = self.runtime.skill_root / self.job_id / "documents"
        self.config["document_directory"] = str(destination)
        self.save_config()
        before = self.json_path.read_bytes()
        report = export_job(self.runtime, self.job_id)
        self.assertEqual(report["status"], "JSON_READY")
        self.assertEqual(report["delivery"]["status"], "FAILED")
        self.assertEqual(report["delivery"]["error_type"], "SetupError")
        self.assertIn("Skill安装目录", report["delivery"]["message"])
        self.assertFalse(report["documents_ready"])
        self.assertFalse(destination.parent.exists())
        self.assertEqual(self.json_path.read_bytes(), before)
        self.cloud.assert_not_called()

    def test_saved_result_exports_with_its_recorded_model(self):
        """验证更新后的本地重导保留任务原模型，不改配置或重新识别。"""
        recorded_model = "qwen-audio-3.0-asr-flash-filetrans"
        self.config["model"] = recorded_model
        self.save_config()
        original_config = (self.root / "config.json").read_bytes()
        original_checksum = (self.root / "config.sha256").read_bytes()
        original_json = self.json_path.read_bytes()
        report = export_job(self.runtime, self.job_id)
        self.assertTrue(report["documents_ready"])
        self.assertNotIn("delivery", job_status(self.runtime, self.job_id))
        files = report["delivery"]["files"]
        with Path(files["xlsx"]["path"]).open("rb") as stream:
            workbook = load_workbook(stream, read_only=True)
            try:
                self.assertEqual(workbook["转写明细"]["A2"].value,
                                 f"模型：{recorded_model}    任务：{self.job_id}")
            finally:
                workbook.close()
        document = Document(files["docx"]["path"])
        self.assertEqual(document.paragraphs[1].text, f"模型：{recorded_model}")
        markdown_model = recorded_model.replace("-", "\\-").replace(".", "\\.")
        self.assertIn(f"模型：{markdown_model}",
                      Path(files["md"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual((self.root / "config.json").read_bytes(), original_config)
        self.assertEqual((self.root / "config.sha256").read_bytes(), original_checksum)
        self.assertEqual(self.json_path.read_bytes(), original_json)
        self.cloud.assert_not_called()

    def test_old_delivery_record_is_ignored_and_preserved(self):
        """验证旧成品记录即使不可读也不影响ASR查询、重导或一次执行约束。"""
        directory = self.root / "delivery"
        directory.mkdir()
        old_record = directory / "status.json"
        old_record.write_bytes(b"{")
        self.save_execution(documents_ready=False, message="BL已结束，转写JSON已保存并通过结构检查；等待本地导出。")
        read_text = Path.read_text

        def refuse_old_record(path, *args, **kwargs):
            """禁止读取历史导出记录，允许任务原数据正常读取。"""
            if path == old_record:
                raise AssertionError("不应读取旧导出记录")
            return read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", refuse_old_record):
            for report in (job_status(self.runtime, self.job_id), transcribe(self.runtime, self.job_id)):
                self.assertEqual(report["status"], "JSON_READY")
                self.assertNotIn("delivery", report)
                self.assertNotIn("documents_ready", report)
                self.assertNotIn("等待本地导出", report["message"])
            self.assertTrue(export_job(self.runtime, self.job_id)["documents_ready"])
        self.assertEqual(old_record.read_bytes(), b"{")
        self.cloud.assert_not_called()

    def test_exported_files_can_be_changed_without_affecting_asr_status(self):
        """验证用户改名、编辑或删除成品后，任务查询仍只描述原始识别结果。"""
        before = (self.root / "execution/status.json").read_bytes()
        result = export_job(self.runtime, self.job_id)
        files = result["delivery"]["files"]
        Path(files["md"]["path"]).write_text("用户自己的成品修改", encoding="utf-8")
        Path(files["docx"]["path"]).rename(self.runtime.workspace / "renamed.docx")
        Path(files["xlsx"]["path"]).unlink()
        observed = job_status(self.runtime, self.job_id)
        self.assertEqual(observed["status"], "JSON_READY")
        self.assertNotIn("delivery", observed)
        self.assertNotIn("documents_ready", observed)
        self.assertEqual((self.root / "execution/status.json").read_bytes(), before)
        self.cloud.assert_not_called()

    def test_interrupted_export_returns_only_known_files_without_changing_asr(self):
        """验证导出中断按已完成格式返回部分成功或失败，且不改写ASR记录。"""
        before = (self.root / "execution/status.json").read_bytes()
        for writer, expected, ready in (("write_xlsx", "FAILED", set()), ("write_docx", "PARTIAL", {"xlsx"})):
            with self.subTest(writer=writer), \
                    patch(f"asr_runtime.application.delivery.{writer}", side_effect=KeyboardInterrupt), \
                    patch("asr_runtime.application.delivery.write_markdown") as markdown:
                report = export_job(self.runtime, self.job_id)
            self.assertEqual(report["status"], "JSON_READY")
            self.assertEqual(report["delivery"]["status"], expected)
            self.assertEqual({name for name, item in report["delivery"]["files"].items() if item["status"] == "READY"}, ready)
            self.assertFalse(report["documents_ready"])
            markdown.assert_not_called()
        self.assertEqual((self.root / "execution/status.json").read_bytes(), before)
        self.assertFalse((self.root / "delivery").exists())
        self.cloud.assert_not_called()

    def test_interrupted_directory_preparation_returns_failed_export(self):
        """验证输出目录准备中断只影响本次导出，原始识别仍为成功。"""
        with patch("asr_runtime.application.delivery.prepare_documents", side_effect=KeyboardInterrupt):
            report = export_job(self.runtime, self.job_id)
        self.assertEqual(report["status"], "JSON_READY")
        self.assertEqual(report["delivery"]["status"], "FAILED")
        self.assertEqual(report["delivery"]["files"], {})
        self.assertEqual(report["delivery"]["error_type"], "KeyboardInterrupt")
        self.assertTrue(self.json_path.is_file())
        self.cloud.assert_not_called()

    def test_cli_status_succeeds_without_delivery_but_export_failure_returns_nonzero(self):
        """验证状态查询不要求成品就绪，实际导出失败仍给调用者非零退出码。"""
        self.save_execution(documents_ready=False)
        for command in ("job-status", "transcribe"):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--workspace", str(self.runtime.workspace), command, "--job", self.job_id]), 0)
            self.assertNotIn("delivery", json.loads(output.getvalue()))
        output = io.StringIO()
        with patch("asr_runtime.application.delivery.write_docx", side_effect=OSError("synthetic")), redirect_stdout(output):
            self.assertEqual(main(["--workspace", str(self.runtime.workspace), "export", "--job", self.job_id]), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "JSON_READY")
        self.cloud.assert_not_called()

    def test_cli_success_record_failure_returns_nonzero_without_delivery(self):
        """验证ASR成功记录未保存仍报告错误，不能因缺少成品跟踪误报成功。"""
        report = {"job_id": self.job_id, "status": "JSON_READY",
                  "record_error": {"source": "local", "explanation": "synthetic save failure"}}
        with patch("asr_runtime.application.transcription.transcribe", return_value=report), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--workspace", str(self.runtime.workspace), "transcribe", "--job", self.job_id]), 1)

    def test_loader_preserves_order_empty_sentence_ids_and_precise_milliseconds(self):
        """验证JSON解析保留原顺序、空句和毫秒时间。"""
        transcript = load_transcript(self.json_path)
        self.assertEqual([s.begin_ms for s in transcript.sentences], [1, 1501, 0])
        self.assertEqual([s.channel_id for s in transcript.sentences], [0, 0, 2])
        self.assertEqual([s.track_index for s in transcript.sentences], [1, 1, 2])
        self.assertEqual(transcript.sentences[1].text, "")
        self.assertIsNone(transcript.sentences[1].speaker_id)
        self.assertEqual(timestamp(25 * 3600000 + 1501), "25:00:01.501")

    def test_channel_or_sentence_schema_errors_are_not_guessed(self):
        """验证异常结果字段返回结构检查错误。"""
        for change in ({"channel_id": True, "sentences": []}, {"sentences": [None]},
                       {"sentences": [{"text": "text", "start": 0, "end": 1}]}):
            self.json_path.write_text(json.dumps({"transcripts": [change]}), encoding="utf-8")
            with self.assertRaises(SetupError):
                load_transcript(self.json_path)
