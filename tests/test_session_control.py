"""验证本机代码交接、终态通知及服务退出后的任务回执。"""

import http.client
import io
import json
import threading
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from asr_runtime.__main__ import main
from asr_runtime.application.session import Session
from asr_runtime.utils.environment import SetupError
from asr_runtime.utils.session_files import read_receipt, session_directory
from asr_runtime.web import control_session, create_server
from tests.test_session import WebFixture


class SessionControlTests(WebFixture):
    def setUp(self):
        """创建可控制时间的真实HTTP服务及合成输入。"""
        super().setUp()
        self.now = [1_800_000_000.0]
        session = Session(self.runtime, clock=lambda: self.now[0])
        with patch("asr_runtime.web.Session", return_value=session):
            self.server = create_server(self.runtime)
        self.session = session
        self.payload = self.payload_for(session)
        self.thread = threading.Thread(target=self.run_server, daemon=True)
        self.thread.start()

    def run_server(self):
        """运行服务并在会话结束后释放连接和临时副本。"""
        try:
            self.server.serve_forever()
        finally:
            self.server.server_close()

    def tearDown(self):
        """等待本例服务和请求线程退出，再移除测试工作目录。"""
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())
        super().tearDown()

    def ready(self):
        """模拟网页完成校验和预览展示登记。"""
        preview = self.session.validate(self.payload)
        self.session.preview_ready(preview["validation_id"])
        return preview

    def event_stream(self):
        """建立终态事件通道并返回响应连接。"""
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request("GET", "/api/events", headers={"X-ASR-Token": self.session.token})
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "text/event-stream; charset=utf-8")
        self.addCleanup(connection.close)
        return response

    def terminal_event(self, stream):
        """读取单次事件并核对服务端正常结束流。"""
        self.assertEqual(stream.readline(), b"event: ended\n")
        payload = stream.readline().decode("utf-8")
        self.assertTrue(payload.startswith("data: "))
        self.assertEqual(stream.readline(), b"\n")
        self.assertEqual(stream.read(), b"")
        return json.loads(payload[6:])

    def test_confirm_requires_ready_preview_and_uses_explicit_session(self):
        """验证填写中和未展示预览均无法创建任务。"""
        with self.assertRaisesRegex(SetupError, "进入预览页"):
            control_session(self.runtime, self.session.session_id, "confirm")
        self.session.validate(self.payload)
        with self.assertRaisesRegex(SetupError, "进入预览页"):
            control_session(self.runtime, self.session.session_id, "confirm")
        with self.assertRaises(SetupError):
            control_session(self.runtime, "b" * 32, "confirm")
        self.assertFalse(self.runtime.path(".state/jobs").exists())

    def test_confirm_notifies_page_stops_service_and_preserves_one_job(self):
        """验证交接通知、服务退出、输入保留及重复确认的同一回执。"""
        self.ready()
        stream = self.event_stream()
        receipt = control_session(self.runtime, self.session.session_id, "confirm")
        terminal = self.terminal_event(stream)
        self.assertEqual(terminal, {"state": "handed_off", "receipt": receipt})
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())
        self.assertFalse((session_directory(self.runtime, self.session.session_id) / "connection.json").exists())
        config = json.loads(Path(receipt["config_path"]).read_text(encoding="utf-8"))
        self.assertTrue(config["execution_authorized"])
        self.assertTrue(Path(config["audio"]["path"]).is_file())
        self.assertEqual(control_session(self.runtime, self.session.session_id, "confirm"), receipt)
        self.assertEqual(len(list(self.runtime.path(".state/jobs").iterdir())), 1)
        self.now[0] += 10_000
        self.assertEqual(self.session.expire()["state"], "handed_off")
        self.assertTrue(Path(config["audio"]["path"]).is_file())

    def test_fixed_expiry_ends_page_and_preserves_original_inputs(self):
        """验证操作不延长两小时有效期，到期结束页面并保留原文件和凭据。"""
        key = self.runtime.path(".env")
        key.write_text("DASHSCOPE_API_KEY=synthetic-key", encoding="utf-8")
        self.ready()
        stream = self.event_stream()
        initial_deadline = self.session.deadline
        self.now[0] += 7_199
        self.assertEqual(self.session.description()["phase"], "preview")
        self.assertEqual(self.session.deadline, initial_deadline)
        self.now[0] += 1
        self.server.expire_session()
        self.assertEqual(self.terminal_event(stream), {"state": "expired", "receipt": None})
        self.thread.join(timeout=5)
        self.assertTrue(self.audio.exists())
        self.assertFalse(self.runtime.path(".state/jobs").exists())
        self.assertTrue(key.exists())

    def test_cancel_sends_terminal_event_without_creating_a_job(self):
        """验证显式取消结束编辑服务并清理会话暂存。"""
        stream = self.event_stream()
        result = control_session(self.runtime, self.session.session_id, "cancel")
        self.assertEqual(result, {"state": "cancelled", "receipt": None})
        self.assertEqual(self.terminal_event(stream), result)
        self.thread.join(timeout=5)
        self.assertTrue(self.audio.exists())
        self.assertFalse(self.runtime.path(".state/jobs").exists())

    def test_lost_http_response_recovers_persisted_receipt(self):
        """验证响应中断后直接读取本次会话回执，不发送第二次交接请求。"""
        self.ready()
        with patch("asr_runtime.web.http.client.HTTPConnection.getresponse", side_effect=http.client.RemoteDisconnected), \
             patch("asr_runtime.web.http.client.HTTPConnection.request") as request:
            request.side_effect = lambda *args, **kwargs: self.session.confirm()
            result = control_session(self.runtime, self.session.session_id, "confirm")
        self.assertEqual(result, read_receipt(self.runtime, self.session.session_id))
        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(list(self.runtime.path(".state/jobs").iterdir())), 1)

    def test_failed_confirmation_still_closes_event_stream_and_cleans_audio(self):
        """验证交接写盘失败后正常关闭仍结束事件流并保留原始音频并清理会话记录。"""
        self.ready()
        stream = self.event_stream()
        with patch("asr_runtime.application.session.write_receipt", side_effect=OSError("synthetic write failure")):
            with self.assertRaisesRegex(SetupError, "本地文件操作未完成"):
                control_session(self.runtime, self.session.session_id, "confirm")
        self.assertIsNone(read_receipt(self.runtime, self.session.session_id))
        self.server.shutdown()
        self.assertEqual(self.terminal_event(stream), {"state": "cancelled", "receipt": None})
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())
        self.assertTrue(self.audio.exists())

    def test_cli_confirm_returns_same_job_after_web_service_exits(self):
        """验证公开命令按复制的会话编号交接，网页服务结束后也能恢复回执。"""
        self.ready()
        outputs = []
        for _ in range(2):
            output = io.StringIO()
            with redirect_stdout(output):
                status = main(["--workspace", str(self.runtime.workspace), "confirm", "--session", self.session.session_id])
            self.assertEqual(status, 0)
            outputs.append(json.loads(output.getvalue()))
        self.assertEqual(outputs[0], outputs[1])
        self.assertNotIn(self.session.token, json.dumps(outputs))

    def test_invalid_session_id_is_rejected_before_network_access(self):
        """验证缺失或路径形式的会话编号不能定位其他文件。"""
        with patch("asr_runtime.web.http.client.HTTPConnection") as connect:
            for value in ("", "../escape", "A" * 32):
                with self.subTest(value=value), self.assertRaises(SetupError):
                    control_session(self.runtime, value, "confirm")
        connect.assert_not_called()
