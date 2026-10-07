"""验证对话录音带入网页、共享登记与预览校验边界。"""

import http.client
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from asr_runtime.__main__ import main
from asr_runtime.application.rules import ValidationError
from asr_runtime.application.session import Session
from asr_runtime.utils.files import file_fingerprint
from asr_runtime.utils.media import probe_audio
from asr_runtime.web import control_session
from tests.support import SKILL_ROOT
from tests.test_session import WebFixture


class InitialAudioTests(WebFixture):
    def session(self, audio: Path | None = None) -> Session:
        """创建可在测试结束时释放的附件配置会话。"""
        session = Session(self.runtime, audio=audio)
        self.addCleanup(session.cleanup)
        return session

    def form(self, session: Session) -> dict[str, object]:
        """从会话已登记录音构造默认转写表单。"""
        assert session.selected_audio is not None
        return {"auth_mode": "console", "audio_id": session.selected_audio["audio_id"],
                "diarization_enabled": True, "enhancement_mode": "none", "hotword_rows": [],
                "context": "", "json_directory": "default", "document_directory": "default"}

    def test_no_attachment_returns_empty_audio_fields(self):
        """验证普通开页提供空音频及空错误字段。"""
        description = self.session().description()
        self.assertIsNone(description["audio"])
        self.assertIsNone(description["audio_error"])

    def test_attachment_is_registered_before_media_validation(self):
        """验证开页只登记原文件，预览时才探测媒体和完整摘要。"""
        original = self.audio.read_bytes()
        with patch("asr_runtime.application.inputs.probe_audio", wraps=probe_audio) as probe, \
             patch("asr_runtime.application.inputs.file_fingerprint", wraps=file_fingerprint) as fingerprint:
            session = self.session(self.audio)
            description = session.description()
            selected = description["audio"]
            self.assertEqual(selected["path"], str(self.audio))
            self.assertEqual(selected["size_bytes"], len(original))
            self.assertEqual(session.description()["audio"]["audio_id"], selected["audio_id"])
            probe.assert_not_called()
            fingerprint.assert_not_called()
            self.assertIsNone(description["preview"])
            self.assertFalse(self.runtime.path(".state/jobs").exists())
            session.validate(self.form(session))
            probe.assert_called_once_with(self.audio)
            fingerprint.assert_called_once_with(self.audio)
        self.assertEqual(self.audio.read_bytes(), original)
        self.assertFalse(self.runtime.output_root.exists())

    def test_invalid_attachment_keeps_editing_and_explains_error(self):
        """验证无效附件仍可填写，错误含中英文并可用原生选择修复。"""
        wrong_type = self.runtime.workspace / "worksheet.xlsx"
        wrong_type.write_bytes(b"not audio")
        for value in (self.audio.parent / "missing.wav", self.audio.parent, Path("relative.wav"), wrong_type):
            with self.subTest(path=value):
                session = self.session(value)
                description = session.description()
                self.assertEqual(description["phase"], "editing")
                self.assertIsNone(description["audio"])
                self.assertIsNotNone(description["audio_error"])
                self.assertNotEqual(description["audio_error"]["zh"], description["audio_error"]["en"])
                with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=self.audio):
                    selection = session.select_audio("replace")
                self.assertEqual(selection["path"], str(self.audio))
                self.assertIsNone(session.description()["audio_error"])

    def test_replace_attachment_resets_preview_and_selection_id(self):
        """验证返回修改后替换录音更新编号及原路径，并清除旧预览。"""
        session = self.session(self.audio)
        old_id = session.selected_audio["audio_id"]
        preview = session.validate(self.form(session))
        session.preview_ready(preview["validation_id"])
        session.edit(preview["validation_id"])
        replacement = self.audio.parent / "另一段 录音.wav"
        replacement.write_bytes(self.audio.read_bytes())
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=replacement):
            selection = session.select_audio("replace")
        self.assertNotEqual(selection["audio_id"], old_id)
        self.assertEqual(selection["path"], str(replacement))
        self.assertIsNone(session.description()["preview"])
        self.assertTrue(self.audio.exists())

    def test_attachment_removed_before_preview_is_reported(self):
        """验证已带入文件消失时，预览错误指向录音且可继续编辑。"""
        session = self.session(self.audio)
        form = self.form(session)
        self.audio.unlink()
        with self.assertRaises(ValidationError) as caught:
            session.validate(form)
        self.assertEqual(caught.exception.field, "audio_id")
        self.assertEqual(session.description()["phase"], "editing")
        self.assertIsNone(session.draft)

    def test_cli_forwards_audio_path_to_web(self):
        """验证CLI把指定附件路径交给网页服务，并使用既有工作目录。"""
        with patch("asr_runtime.web.serve") as serve:
            result = main(["--workspace", str(self.runtime.workspace), "serve", "--no-browser", "--audio", str(self.audio)])
        self.assertEqual(result, 0)
        self.assertEqual(serve.call_args.args[0].workspace, self.runtime.workspace)
        self.assertEqual(serve.call_args.kwargs, {"port": 0, "open_browser": False, "audio": self.audio})

    def test_real_cli_opens_page_with_spaced_unicode_attachment(self):
        """验证实际CLI服务回传附件及同一选择编号，取消后正常退出。"""
        attachment = self.audio.parent / "会议 [复盘] 录音.wav"
        attachment.write_bytes(self.audio.read_bytes())
        process = subprocess.Popen(
            [sys.executable, "-B", "-X", "utf8", str(SKILL_ROOT / "scripts/asr.py"),
             "--workspace", str(self.runtime.workspace), "serve", "--no-browser", "--audio", str(attachment)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        )
        receipt = None
        try:
            assert process.stdout is not None
            receipt = json.loads(process.stdout.readline())
            port = int(receipt["url"].split(":")[-1].rstrip("/"))
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                connection.request("GET", "/")
                response = connection.getresponse()
                response.read()
                cookie = response.getheader("Set-Cookie").split(";", 1)[0]
                descriptions = []
                for _ in range(2):
                    connection.request("GET", "/api/session", headers={"Cookie": cookie})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    descriptions.append(json.loads(response.read()))
            finally:
                connection.close()
            self.assertEqual(descriptions[0]["audio"]["path"], str(attachment))
            self.assertEqual(descriptions[0]["audio"], descriptions[1]["audio"])
            self.assertEqual(descriptions[0]["phase"], "editing")
            self.assertIsNone(descriptions[0]["audio_error"])
            self.assertIsNone(descriptions[0]["preview"])
            self.assertFalse(self.runtime.path(".state/jobs").exists())
            self.assertEqual(control_session(self.runtime, receipt["session_id"], "cancel")["state"], "cancelled")
            self.assertEqual(process.wait(timeout=15), 0)
        finally:
            if process.poll() is None:
                if receipt:
                    control_session(self.runtime, receipt["session_id"], "cancel")
                else:
                    process.kill()
                process.wait(timeout=15)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
