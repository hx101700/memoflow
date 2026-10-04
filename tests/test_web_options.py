import http.client
import io
import json
import threading
import tempfile
import wave
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from openpyxl import Workbook

from asr_runtime.application.rules import ValidationError
from asr_runtime.utils.environment import Runtime
from asr_runtime.web import create_server
from asr_runtime.application.session import Session
from tests.support import RuntimeTestCase


class OptionsFixture(RuntimeTestCase):
    def setUp(self):
        """准备项目及模拟用户选择的外部保存目录。"""
        super().setUp()
        # 用工作区内同一临时根的兄弟目录模拟用户选中项目外的保存位置。
        temporary_root = self.temporary_root
        self.selected = temporary_root / "selected"
        self.selected.mkdir()
        self.other = temporary_root / "other"
        self.other.mkdir()

    def payload_for(self, session):
        """上传合成音频并生成默认会话配置。"""
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0" * 32000)
        content = buffer.getvalue()
        uploaded = session.upload("audio", "synthetic.wav", io.BytesIO(content), len(content))
        return {
            "auth_mode": "console", "audio_upload_id": uploaded["upload_id"],
            "diarization_enabled": True, "enhancement_mode": "none",
            "hotword_rows": [], "context": "",
            "json_directory": "default", "document_directory": "default",
        }

    def confirm(self, session, validation_id):
        """登记已呈现的预览，再由代码交接执行任务。"""
        session.preview_ready(validation_id)
        return session.confirm()

    def select(self, session, kind, destination):
        """模拟原生目录选择并返回登记结果。"""
        with patch("asr_runtime.utils.directory_picker.choose_directory", return_value=destination) as picker:
            result = session.select_directory(kind, "test-picker")
        picker.assert_called_once()
        return result


class DirectoryOptionTests(OptionsFixture):
    def setUp(self):
        """准备目录选项测试会话。"""
        super().setUp()
        self.session = Session(self.runtime)
        self.payload = self.payload_for(self.session)

    def test_selected_external_directory_is_saved_without_producing_outputs(self):
        """验证外部目录确认生成配置并保留待执行状态。"""
        for kind in ("json", "document"):
            result = self.select(self.session, kind, self.selected)
            self.assertEqual(result["path"], str(self.selected))
            self.assertFalse(result["cancelled"])
        preview = self.session.validate({
            **self.payload, "json_directory": str(self.selected),
            "document_directory": str(self.selected),
        })
        receipt = self.confirm(self.session, preview["validation_id"])
        config = json.loads(Path(receipt["config_path"]).read_text(encoding="utf-8"))
        for field in ("json_directory", "document_directory"):
            self.assertTrue(Path(config[field]).is_relative_to(self.selected))
        self.assertTrue(config["execution_authorized"])
        self.assertFalse(receipt["execution_started"])
        self.assertEqual(list(self.selected.iterdir()), [])
        self.assertFalse(self.runtime.output_root.exists())

    def test_unavailable_initial_location_falls_back_to_workspace(self):
        """验证起始位置被文件占用或已删除时仍可打开窗口改选目录。"""
        for kind, initial, make_file in (
            ("json", self.runtime.output_root, True),
            ("document", self.other, True),
            ("document", self.temporary_root / "removed-folder", False),
        ):
            with self.subTest(initial=initial):
                if initial.is_dir():
                    initial.rmdir()
                if make_file:
                    initial.write_text("keep", encoding="utf-8")
                if kind == "document":
                    self.session.output_directories[kind] = initial
                with patch("asr_runtime.utils.directory_picker.subprocess.Popen") as start:
                    process = start.return_value
                    process.returncode = process.poll.return_value = 0
                    process.communicate.return_value = (json.dumps({"path": str(self.selected)}), "")
                    result = self.session.select_directory(kind, "choose-output")
                self.assertEqual(result["path"], str(self.selected))
                self.assertEqual(start.call_args.args[0][5], str(self.runtime.workspace))
                if make_file:
                    self.assertEqual(initial.read_text(encoding="utf-8"), "keep")

    def test_browser_cannot_register_external_directory_by_submitting_path(self):
        """验证外部保存位置必须来自原生目录登记。"""
        with self.assertRaises(ValidationError):
            self.session.validate({**self.payload, "json_directory": str(self.selected)})
        self.assertEqual(self.session.output_directories, {})
        self.assertEqual(list(self.selected.iterdir()), [])

    def test_skill_directories_are_rejected_before_write_probe(self):
        """验证原生选择Skill根或子目录时在写探针前拒绝。"""
        for kind in ("json", "document"):
            for selected in (self.runtime.skill_root, self.runtime.skill_root / "scripts"):
                with self.subTest(kind=kind, selected=selected), \
                     patch("asr_runtime.utils.directory_picker.choose_directory", return_value=selected), \
                     patch("asr_runtime.application.session.tempfile.TemporaryFile") as probe:
                    with self.assertRaisesRegex(ValidationError, "Skill安装目录") as caught:
                        self.session.select_directory(kind, "test-picker")
                    self.assertEqual(caught.exception.field, f"{kind}_directory")
                    probe.assert_not_called()
        self.assertEqual(self.session.output_directories, {})

    def test_preview_rejects_skill_as_default_output_directory(self):
        """验证默认保存目录与Skill重合时给出可修改的字段错误。"""
        skill = self.runtime.output_root
        skill.mkdir()
        session = Session(Runtime(self.runtime.workspace, skill))
        try:
            payload = self.payload_for(session)
            with self.assertRaisesRegex(ValidationError, "Skill安装目录") as caught:
                session.validate(payload)
            self.assertEqual(caught.exception.field, "json_directory")
            self.assertEqual(list(skill.iterdir()), [])
            self.assertIsNone(session.draft)
        finally:
            session.cleanup()

    def test_directory_approval_is_bound_to_kind_and_exact_directory(self):
        """验证目录授权绑定用途与精确位置。"""
        self.select(self.session, "json", self.selected)
        for changes in (
            {"document_directory": str(self.selected)},
            {"json_directory": str(self.other)},
            {"json_directory": str(self.selected / "child")},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.session.validate({**self.payload, **changes})

    def test_cancel_keeps_selected_directory_and_existing_preview(self):
        """验证取消保留原目录和已有预览。"""
        self.select(self.session, "json", self.selected)
        preview = self.session.validate({**self.payload, "json_directory": str(self.selected)})
        result = self.select(self.session, "json", None)
        self.assertTrue(result["cancelled"])
        self.assertEqual(self.session.output_directories["json"], self.selected)
        self.assertEqual(self.session.draft["id"], preview["validation_id"])
        self.assertTrue(self.confirm(self.session, preview["validation_id"])["ok"])

    def test_directory_write_probe_runs_only_when_user_selects_directory(self):
        """验证目录选择检查一次可写性并供预览确认复用。"""
        with patch("asr_runtime.application.session.tempfile.TemporaryFile", wraps=tempfile.TemporaryFile) as probe:
            self.select(self.session, "json", self.selected)
            preview = self.session.validate({**self.payload, "json_directory": str(self.selected)})
            self.confirm(self.session, preview["validation_id"])
        probe.assert_called_once_with(dir=self.selected)
        self.assertEqual(list(self.selected.iterdir()), [])

    def test_switching_directory_invalidates_existing_preview(self):
        """验证改变保存目录使旧预览失效。"""
        self.select(self.session, "json", self.selected)
        preview = self.session.validate({**self.payload, "json_directory": str(self.selected)})
        self.select(self.session, "json", self.other)
        self.assertEqual(self.session.output_directories["json"], self.other)
        with self.assertRaises(ValidationError):
            self.confirm(self.session, preview["validation_id"])
        self.assertFalse(self.runtime.path(".state/jobs").exists())

    def test_cancel_waiting_picker_keeps_previous_preview_and_releases_lock(self):
        """验证取消等待中的窗口保留预览并释放状态。"""
        preview = self.session.validate(self.payload)
        started = threading.Event()
        cancellation_events = []

        def blocked_picker(_initial, *, cancel_event):
            """等待取消事件以模拟正在选择目录的窗口。"""
            cancellation_events.append(cancel_event)
            started.set()
            self.assertTrue(cancel_event.wait(timeout=3))
            return self.selected  # 即使同时收到结果，也不能把已取消的选择登记下来。

        with patch("asr_runtime.utils.directory_picker.choose_directory", side_effect=blocked_picker):
            with ThreadPoolExecutor(max_workers=1) as pool:
                selected = pool.submit(self.session.select_directory, "json", "picker-current")
                self.assertTrue(started.wait(timeout=3))
                self.session.cancel_directory("picker-old")
                self.assertFalse(cancellation_events[0].is_set())
                self.session.cancel_directory("picker-current")
                self.assertTrue(selected.result(timeout=3)["cancelled"])
        self.assertEqual(self.session.output_directories, {})
        self.assertEqual(self.session.draft["id"], preview["validation_id"])
        self.assertFalse(self.select(self.session, "json", self.selected)["cancelled"])

    def test_cancel_arriving_before_open_prevents_window_but_not_next_request(self):
        """验证提前取消作用于对应请求且后续选择正常。"""
        self.session.cancel_directory("early-cancel")
        with patch("asr_runtime.utils.directory_picker.choose_directory", return_value=self.selected) as picker:
            self.assertTrue(self.session.select_directory("json", "early-cancel")["cancelled"])
            picker.assert_not_called()
            self.assertFalse(self.session.select_directory("json", "next-request")["cancelled"])
            picker.assert_called_once()

    def test_language_speakers_and_combined_enhancement_survive_confirmation(self):
        """验证语言、人数和双增强在确认后保持一致。"""
        workbook = Workbook()
        workbook.active.append(["text", "weight"])
        workbook.active.append(["测试术语", 4])
        buffer = io.BytesIO()
        workbook.save(buffer)
        workbook.close()
        content = buffer.getvalue()
        uploaded = self.session.upload("hotwords", "synthetic.xlsx", io.BytesIO(content), len(content))
        preview = self.session.validate({
            **self.payload, "language_hint": "zh", "speaker_count": 3,
            "enhancement_mode": "both", "hotword_rows": uploaded["rows"],
            "context": "本次会议讨论测试术语。",
        })
        expected = {"language_hints": ["zh"], "speaker_count": 3}
        self.assertEqual(preview["summary"]["enhancement"]["mode"], "both")
        receipt = self.confirm(self.session, preview["validation_id"])
        config = json.loads(Path(receipt["config_path"]).read_text(encoding="utf-8"))
        self.assertEqual(config["recognition_options"], expected)
        self.assertEqual(config["enhancement"]["hotwords"]["count"], 1)
        self.assertEqual(config["enhancement"]["context"], "本次会议讨论测试术语。")
        self.assertTrue(config["execution_authorized"])
        self.assertFalse(list(self.session.upload_directory.glob("*.xlsx*")))
        self.session.cleanup()
        self.assertTrue(Path(config["audio"]["path"]).is_file())
        self.assertEqual(config["enhancement"]["hotwords"]["vocabulary"], {"测试术语": 4})


class ProtectedOptionsEndpointTests(OptionsFixture):
    def setUp(self):
        """启动目录选项HTTP测试服务。"""
        super().setUp()
        self.server = create_server(self.runtime)
        self.payload = self.payload_for(self.server.session)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        """关闭HTTP服务并清理临时目录。"""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        super().tearDown()

    def request(self, method, path, payload=None, *, token=True, origin=None):
        """发送目录选项HTTP请求并解析响应。"""
        headers = {"Origin": origin or self.origin}
        if token:
            headers["X-ASR-Token"] = self.server.session.token
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_directory_route_uses_native_selection_and_ignores_browser_path(self):
        """验证目录接口使用原生选择且忽略客户端路径。"""
        with patch("asr_runtime.utils.directory_picker.choose_directory", return_value=self.selected) as picker:
            status, _, body = self.request("POST", "/api/select-directory", {
                "kind": "document", "picker_id": "select-document", "path": str(self.other),
            })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["path"], str(self.selected))
        self.assertEqual(self.server.session.output_directories["document"], self.selected)
        picker.assert_called_once()
        self.assertEqual(list(self.selected.iterdir()), [])
        self.assertEqual(list(self.other.iterdir()), [])

    def test_new_routes_require_token_and_correct_origin_before_any_action(self):
        """验证新增接口在操作前检查令牌和来源。"""
        with patch("asr_runtime.utils.directory_picker.choose_directory") as picker, \
             patch("asr_runtime.application.session.read_api_key") as read_key:
            # 鉴权在读取正文前完成；无正文请求可稳定检查HTTP拒绝和零副作用。
            for route in ("/api/select-directory", "/api/api-key", "/api/cancel-directory"):
                with self.subTest(route=route):
                    self.assertEqual(self.request("POST", route, token=False)[0], 403)
                    self.assertEqual(self.request("POST", route, origin="https://example.invalid")[0], 403)
        picker.assert_not_called()
        read_key.assert_not_called()

    def test_directory_request_requires_page_request_id(self):
        """验证缺少页面请求编号时拒绝打开不可关联取消操作的窗口。"""
        with patch("asr_runtime.utils.directory_picker.choose_directory") as picker:
            status, _, _ = self.request("POST", "/api/select-directory", {"kind": "json"})
        self.assertEqual(status, 422)
        picker.assert_not_called()

    def test_key_is_returned_only_by_dedicated_post_and_never_saved(self):
        """验证专用POST显示Key并保持配置与凭据分离。"""
        secret = "synthetic-display-key"
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=" + secret, encoding="utf-8")
        status, headers, body = self.request("POST", "/api/api-key", {})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["value"], secret)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.request("GET", "/api/api-key")[0], 404)

        status, _, body = self.request("GET", "/api/session")
        self.assertEqual(status, 200)
        self.assertNotIn(secret.encode("utf-8"), body)

        status, _, body = self.request("POST", "/api/validate", {**self.payload, "auth_mode": "api_key"})
        self.assertEqual(status, 200)
        self.assertNotIn(secret.encode("utf-8"), body)
        preview = json.loads(body)
        self.request("POST", "/api/preview-ready", {"validation_id": preview["validation_id"]})
        status, _, body = self.request("POST", "/api/confirm", {})
        self.assertEqual(status, 200)
        self.assertNotIn(secret.encode("utf-8"), body)
        config = Path(json.loads(body)["config_path"]).read_text(encoding="utf-8")
        self.assertNotIn(secret, config)
        self.assertNotIn(secret, json.dumps(self.server.session.description()))
