"""通过真实BL和本机模拟服务验证识别流程合约。"""

import json
import io
import subprocess
import threading
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from asr_runtime import MODEL
from asr_runtime.utils.auth import bailian_environment
from asr_runtime.utils.bailian import bl_command
from scripts.probe_bl import SYNTHETIC_AUDIO_URL
from asr_runtime.utils.bailian import PreparedCommand, run_recognition
from asr_runtime.application.session import Session
from asr_runtime.application.transcription import job_status, transcribe
from tests.support import RuntimeTestCase, CONTRACT_BL_ENTRY, contract_runtime


@unittest.skipUnless(CONTRACT_BL_ENTRY.is_file(), "需要在专用测试工作区安装 BL 才能运行合约测试")
class BailianContractTests(RuntimeTestCase):
    def setUp(self):
        """启动本机模拟服务并准备CLI合约场景。"""
        super().setUp()
        self.calls = []
        self.mode = "success"
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                """关闭模拟服务的访问日志。"""
                pass

            def reply(self, status, payload):
                """向测试客户端发送指定状态的JSON响应。"""
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                """模拟识别提交成功或指定HTTP错误。"""
                owner.authorization = self.headers.get("Authorization")
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.calls.append(("POST", self.path, body))
                if owner.mode in ("submit_401", "submit_500"):
                    self.reply(int(owner.mode[-3:]), {"code": "TestFailure", "message": "synthetic failure"})
                else:
                    self.reply(200, {"output": {"task_id": "local-test-task", "task_status": "PENDING"}})

            def do_GET(self):
                """模拟任务查询状态及转写结果下载。"""
                owner.calls.append(("GET", self.path, None))
                if self.path == "/result.json":
                    self.reply(200, {"transcripts": [{"text": "本地模拟转写", "sentences": [{
                        "text": "本地模拟转写", "begin_time": 0, "end_time": 1000, "speaker_id": 0,
                    }]}]})
                    return
                if owner.mode == "query_500":
                    self.reply(500, {"code": "TestFailure", "message": "synthetic failure"})
                    return
                status = {"task_failed": "FAILED", "canceled": "CANCELED", "unknown": "UNKNOWN"}.get(owner.mode, "SUCCEEDED")
                result = {
                    "subtask_status": "FAILED" if owner.mode == "subtask_failed" else "SUCCEEDED",
                    "transcription_url": f"{owner.base_url}/result.json",
                    "file_url": SYNTHETIC_AUDIO_URL,
                    "message": "synthetic subtask failure",
                }
                self.reply(200, {"output": {"task_id": "local-test-task", "task_status": status,
                    "message": "synthetic task status", "results": [result]}})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        """关闭模拟服务、等待线程并清理临时项目。"""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        super().tearDown()

    def invoke(self, mode="success", *, diarization=True):
        """以指定模拟场景调用真实BL并返回结果文件。"""
        self.mode = mode
        self.runtime.prepare()
        self.runtime.path(".env").write_text(
            "DASHSCOPE_API_KEY=asr-transcription-synthetic-test-key\n", encoding="utf-8")
        env = bailian_environment(self.runtime, "api_key")
        output = self.runtime.path("result.json")
        arguments = [
            "speech", "recognize", "--model", MODEL, "--url", SYNTHETIC_AUDIO_URL,
            "--base-url", self.base_url, "--out", str(output),
            "--timeout", "1", "--poll-interval", "0.1", "--output", "json",
        ]
        if diarization:
            arguments.append("--diarization")
        # 这里运行真实CLI；Python HTTP代码仅为测试fixture，不属于产品运行路径。
        result = subprocess.run(
            bl_command(contract_runtime(), arguments), cwd=self.runtime.root, env=env,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
            timeout=30, shell=False, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result, output

    def test_full_cli_flow_saves_json_without_exposing_task_id(self):
        """验证完整CLI流程保存JSON并检查公开输出。"""
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        transcript = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(transcript["transcripts"][0]["text"], "本地模拟转写")
        self.assertNotIn("local-test-task", result.stdout)
        self.assertEqual([call[0] for call in self.calls], ["POST", "GET", "GET"])
        submitted = self.calls[0][2]
        self.assertEqual(submitted["model"], MODEL)
        self.assertTrue(submitted["parameters"]["diarization_enabled"])
        self.assertEqual(self.authorization, "Bearer " + "asr-transcription-synthetic-test-key")

    def test_submit_401_is_not_retried(self):
        """验证提交401错误返回失败且请求次数为一。"""
        result, output = self.invoke("submit_401")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(output.exists())

    def test_minimal_recognition_still_sends_parameters(self):
        """验证所有可选项关闭时真实BL仍传模型要求的parameters对象。"""
        result, output = self.invoke(diarization=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.is_file())
        self.assertEqual([call[0] for call in self.calls], ["POST", "GET", "GET"])
        submitted = self.calls[0][2]
        self.assertEqual(submitted["model"], "qwen-audio-3.1-asr-flash-filetrans")
        self.assertEqual(submitted["parameters"], {"channel_id": [0]})

    def test_submit_500_is_not_retried(self):
        """验证提交500错误返回失败且请求次数为一。"""
        result, output = self.invoke("submit_500")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(output.exists())

    def test_query_error_stops_without_resubmission(self):
        """验证查询失败返回停止结果并保留单次提交。"""
        result, output = self.invoke("query_500")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([call[0] for call in self.calls], ["POST", "GET"])
        self.assertFalse(output.exists())

    def test_task_failure_stops(self):
        """验证云端任务失败后停止。"""
        result, output = self.invoke("task_failed")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(output.exists())

    def test_subtask_failure_can_exit_zero_with_empty_result(self):
        """验证子任务失败时CLI退出零并保存空结果。"""
        result, output = self.invoke("subtask_failed")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), [])
        self.assertIn("[FAILED]", result.stdout)
        self.assertEqual(len(self.calls), 2)

    def test_canceled_task_times_out_without_resubmission(self):
        """验证取消状态等待超时并保留单次提交。"""
        result, output = self.invoke("canceled")
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertGreaterEqual(sum(call[0] == "GET" for call in self.calls), 2)
        self.assertEqual(sum(call[0] == "POST" for call in self.calls), 1)
        self.assertFalse(output.exists())

    def test_unknown_task_times_out_without_resubmission(self):
        """验证未知状态等待超时并保留单次提交。"""
        result, output = self.invoke("unknown")
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertGreaterEqual(sum(call[0] == "GET" for call in self.calls), 2)
        self.assertEqual(sum(call[0] == "POST" for call in self.calls), 1)
        self.assertFalse(output.exists())

    def invoke_saved_job(self, mode, *, context="本机合约验证", vocabulary=None):
        """保存合成任务并通过本机服务执行真实CLI。"""
        self.mode = mode
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=asr-transcription-synthetic-test-key\n", encoding="utf-8")
        content = io.BytesIO()
        with wave.open(content, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 16000)
        data = content.getvalue()
        session = Session(self.runtime)
        self.addCleanup(session.cleanup)
        source = self.runtime.workspace / "合成样本.wav"
        source.write_bytes(data)
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=source):
            selection = session.select_audio("fixture-audio")
        hotword_rows = []
        if vocabulary is not None:
            workbook = Workbook()
            workbook.active.append(["text", "weight"])
            for row, (term, weight) in enumerate(vocabulary.items(), start=2):
                workbook.active.append([term, weight])
                workbook.active.cell(row, 1).data_type = "s"
            excel = io.BytesIO()
            workbook.save(excel)
            workbook.close()
            content = excel.getvalue()
            hotword_rows = session.receive_hotwords("合成热词.xlsx", io.BytesIO(content), len(content))["rows"]
        preview = session.validate({
            "auth_mode": "api_key", "audio_id": selection["audio_id"],
            "diarization_enabled": True, "language_hint": "zh", "speaker_count": 3,
            "enhancement_mode": "both" if vocabulary is not None else "context",
            "context": context, "hotword_rows": hotword_rows,
            "json_directory": "default", "document_directory": "default",
        })
        session.preview_ready(preview["validation_id"])
        job_id = session.confirm()["job_id"]

        def local_recognition(runtime, command, private):
            # 仅fixture改端点和输入URL；产品入口不开放端点覆盖，也不使用真实音频URL。
            """将测试命令的音频URL和端点指向本机替身。"""
            arguments = list(command.argv)
            for flag, value in (("--url", SYNTHETIC_AUDIO_URL), ("--base-url", self.base_url),
                                ("--timeout", "1"), ("--poll-interval", "0.1")):
                arguments[arguments.index(flag) + 1] = value
            run_recognition(runtime, PreparedCommand(tuple(arguments), command.env), private)

        def installed_command(runtime, arguments):
            """使用开发环境中已安装的BL构造测试命令。"""
            return bl_command(contract_runtime(), arguments)

        with patch("asr_runtime.utils.bailian.bl_command", side_effect=installed_command), \
                patch("asr_runtime.application.transcription.run_recognition", side_effect=local_recognition):
            report = transcribe(self.runtime, job_id)
            calls = len(self.calls)
            repeated = transcribe(self.runtime, job_id)
        self.assertEqual(len(self.calls), calls)
        self.assertEqual(repeated, job_status(self.runtime, job_id))
        return report

    def test_enhancement_text_survives_excel_snapshot_and_windows_cli(self):
        """逐字核对增强内容经过Excel、确认快照和真实BL后的请求值。"""
        vocabulary = {
            '中文"引号': 4, "O'Reilly": 3, "C++": 4, "A&B|C": 2,
            "C:\\voice files\\": 3, '斜杠\\"组合': 4, r"字面\n\t": 3,
            "%PATH%": 2, "$HOME": 2, "`命令`": 1, "<tag>": 1,
            "𠮷野家😀": 5, "cafe\u0301": 3, "__proto__": 2,
            "constructor": 2, "toString": 2, "toJSON": 2,
        }
        context = '  中文"双引号"与\'单引号\'；C:\\voice files\\\r\n下一行\t😀𠮷 cafe\u0301\n字面\\n、\\t；&|<>^%! $HOME `内容` = {} []，尾部\\  '
        report = self.invoke_saved_job("success", context=context, vocabulary=vocabulary)
        self.assertEqual(report["status"], "JSON_READY", report)
        submitted = next(call[2] for call in self.calls if call[0] == "POST")
        self.assertEqual(submitted["parameters"]["vocabulary"], vocabulary)
        self.assertEqual(submitted["input"]["context"][0]["content"][0]["text"], context)
        self.assertEqual(sum(call[0] == "POST" for call in self.calls), 1)

    def test_context_option_like_text_reaches_bl_as_literal_content(self):
        """验证选项及文件引用形态的上下文按原文进入识别请求。"""
        for context in ("--help", "--version", "--术语=中文", "---\n下一行", "@missing-context.txt",
                        "-", "a=b=c", "A\nB", "A\r\nB", '尾部带空格路径 C:\\audio files\\',
                        '{"参考":"原样保留"}'):
            with self.subTest(context=context):
                self.calls.clear()
                report = self.invoke_saved_job("success", context=context)
                self.assertEqual(report["status"], "JSON_READY", report)
                submitted = next(call[2] for call in self.calls if call[0] == "POST")
                self.assertEqual(submitted["input"]["context"][0]["content"][0]["text"], context)
                self.assertEqual(sum(call[0] == "POST" for call in self.calls), 1)

    def test_saved_config_runs_once_through_real_cli_and_checks_json(self):
        """验证配置对应一次CLI执行并检查JSON。"""
        report = self.invoke_saved_job("success")
        self.assertEqual(report["status"], "JSON_READY")
        self.assertTrue(report["documents_ready"])
        self.assertTrue(Path(report["json_path"]).is_file())
        self.assertNotIn("本地模拟转写", json.dumps(report, ensure_ascii=False))
        self.assertEqual([call[0] for call in self.calls], ["POST", "GET", "GET"])
        parameters = self.calls[0][2]["parameters"]
        self.assertEqual(parameters["language_hints"], ["zh"])
        self.assertEqual(parameters["speaker_count"], 3)

    def test_saved_config_rejects_cli_zero_exit_with_no_transcript(self):
        """验证CLI空结果返回停止状态。"""
        report = self.invoke_saved_job("subtask_failed")
        self.assertEqual(report["status"], "STOPPED")
        self.assertEqual(report["cloud_outcome"], "unknown")
        self.assertEqual(json.loads(Path(report["json_path"]).read_text(encoding="utf-8")), [])
        self.assertEqual(len(self.calls), 2)

    def test_saved_config_preserves_structured_cli_failure_without_resubmitting(self):
        """验证CLI失败返回结构化错误并保留单次提交。"""
        report = self.invoke_saved_job("submit_401")
        self.assertEqual(report["status"], "STOPPED")
        self.assertEqual(report["error"]["http_status"], 401)
        self.assertEqual(report["error"]["code"], "TestFailure")
        self.assertNotIn("asr-transcription-synthetic-test-key", json.dumps(report))
        self.assertEqual(len(self.calls), 1)
