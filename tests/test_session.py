import io
import json
import wave
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from openpyxl import Workbook

from asr_runtime.application.rules import ValidationError
from asr_runtime.application.session import Session, output_directory
from tests.support import RuntimeTestCase


class WebFixture(RuntimeTestCase):
    def setUp(self):
        """准备供原生选择窗口读取的合成音频。"""
        super().setUp()
        self.audio = self.runtime.workspace / "recordings/录音.wav"
        self.audio.parent.mkdir(parents=True)
        with wave.open(str(self.audio), "wb") as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0" * 64000)

    def payload_for(self, session):
        """模拟原生窗口选中音频，并构造默认网页配置。"""
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=self.audio):
            selection = session.select_audio("test-audio")
        return {"auth_mode": "console", "audio_id": selection["audio_id"],
                        "diarization_enabled": True, "enhancement_mode": "none",
                        "hotword_rows": [], "context": "", "json_directory": "default",
                        "document_directory": "default"}


class SessionTests(WebFixture):
    def setUp(self):
        """准备会话及已选择原音频的默认配置。"""
        super().setUp()
        self.session = Session(self.runtime)
        self.addCleanup(self.session.cleanup)
        self.payload = self.payload_for(self.session)

    def test_preview_performs_no_conversion_or_job_write(self):
        """验证预览生成内存快照和用户核对信息。"""
        result = self.session.validate(self.payload)
        self.assertEqual(result["summary"]["audio"]["channels"], 2)
        self.assertTrue(any("单声道" in warning["zh"] for warning in result["summary"]["warnings"]))
        self.assertFalse(self.runtime.path(".state/jobs").exists())
        self.assertFalse(self.runtime.output_root.exists())

    def test_hotword_import_errors_target_the_editable_table(self):
        """验证导入前的文件错误与等待提示指向当前热词表格字段。"""
        with self.assertRaises(ValidationError) as caught:
            self.session.receive_hotwords("words.xlsx", io.BytesIO(), 0)
        self.assertEqual(caught.exception.field, "hotword_rows")
        self.session._receiving_hotwords = True
        try:
            with self.assertRaises(ValidationError) as caught:
                self.session.validate(self.payload)
            self.assertEqual(caught.exception.field, "hotword_rows")
        finally:
            self.session._receiving_hotwords = False

    def test_hotword_only_upload_reads_excel_in_memory_and_preserves_the_source(self):
        """验证只导入热词时始终使用内存，原Excel及运行目录保持原样。"""
        session = Session(self.runtime)
        self.addCleanup(session.cleanup)
        source = self.runtime.workspace / "original-hotwords.xlsx"
        workbook = Workbook()
        workbook.active.append(["text", "weight"])
        for row in (["术语", 99], ["术语", 4], ["=1+1", 4]):
            workbook.active.append(row)
        workbook.save(source)
        workbook.close()
        content = source.read_bytes()
        files_before = set(self.runtime.root.rglob("*"))

        with patch.object(Path, "open", side_effect=AssertionError("热词导入只接收内存字节")), \
                patch("asr_runtime.application.rules.build_vocabulary", side_effect=AssertionError("预览才检查词条")):
            imported = session.receive_hotwords(source.name, io.BytesIO(content), len(content))

        self.assertEqual(imported["rows"], [
            {"text": "术语", "weight": 99}, {"text": "术语", "weight": 4},
            {"text": "=1+1", "weight": 4, "invalid_fields": ["text"]},
        ])
        self.assertNotIn("issues", imported)
        self.assertEqual(set(self.runtime.root.rglob("*")), files_before)
        self.assertEqual(source.read_bytes(), content)
        self.assertFalse(session._receiving_hotwords)

    def test_failed_hotword_receive_or_parse_leaves_no_disk_copy(self):
        """验证热词传输截断或文件损坏时释放登记且不创建暂存目录。"""
        session = Session(self.runtime)
        self.addCleanup(session.cleanup)
        content = b"synthetic invalid Excel"
        files_before = set(self.runtime.root.rglob("*"))
        for declared_size in (len(content), len(content) + 1):
            with self.subTest(declared_size=declared_size), self.assertRaises(ValidationError):
                session.receive_hotwords("invalid.xlsx", io.BytesIO(content), declared_size)
            self.assertEqual(set(self.runtime.root.rglob("*")), files_before)
            self.assertFalse(session._receiving_hotwords)

    def test_confirm_is_idempotent_even_with_concurrent_requests(self):
        """验证并发确认共用同一配置回执。"""
        preview = self.session.validate(self.payload)
        self.session.preview_ready(preview["validation_id"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.session.confirm)
            second = pool.submit(self.session.confirm)
            receipts = [first.result(), second.result()]
        self.assertEqual(receipts[0], receipts[1])
        self.assertEqual(len(list(self.runtime.path(".state/jobs").iterdir())), 1)
        with open(receipts[0]["config_path"], encoding="utf-8") as file:
            config = json.load(file)
        self.assertTrue(config["execution_authorized"])
        self.assertFalse(receipts[0]["execution_started"])
        self.assertEqual(config["region"], "cn-beijing")

    def test_failed_revalidation_invalidates_old_preview(self):
        """验证再次校验失败使旧预览失效。"""
        previous = self.session.validate(self.payload)
        with self.assertRaises(ValidationError):
            self.session.validate({**self.payload, "audio_id": "missing"})
        with self.assertRaises(ValidationError):
            self.session.preview_ready(previous["validation_id"])
        with self.assertRaises(ValidationError):
            self.session.confirm()

    def test_file_changed_after_preview_cannot_be_confirmed(self):
        """验证预览后文件变化时拒绝确认。"""
        preview = self.session.validate(self.payload)
        self.session.preview_ready(preview["validation_id"])
        self.audio.write_bytes(self.audio.read_bytes() + b"changed")
        with self.assertRaises(ValidationError):
            self.session.confirm()
        self.assertFalse(self.runtime.path(".state/jobs").exists())

    def test_confirmation_uses_metadata_without_reading_audio_again(self):
        """验证确认通过文件元信息复用预览快照。"""
        preview = self.session.validate(self.payload)
        self.session.preview_ready(preview["validation_id"])
        with patch("asr_runtime.application.inputs.file_fingerprint", side_effect=AssertionError("must not hash again")), \
             patch("asr_runtime.application.inputs.probe_audio", side_effect=AssertionError("must not probe again")):
            self.assertTrue(self.session.confirm()["ok"])

    def test_api_key_is_not_written_to_config(self):
        """验证确认配置与凭据保持分离。"""
        secret = "synthetic-local-key"
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=" + secret, encoding="utf-8")
        preview = self.session.validate({**self.payload, "auth_mode": "api_key"})
        self.session.preview_ready(preview["validation_id"])
        receipt = self.session.confirm()
        with open(receipt["config_path"], encoding="utf-8") as file:
            text = file.read()
        self.assertNotIn(secret, text)
        self.assertNotIn(secret, json.dumps(preview))

    def test_api_key_change_does_not_invalidate_configuration(self):
        """验证Key改变后配置仍能正常确认。"""
        path = self.runtime.path(".env")
        path.write_text("DASHSCOPE_API_KEY=synthetic-key", encoding="utf-8")
        preview = self.session.validate({**self.payload, "auth_mode": "api_key"})
        self.session.preview_ready(preview["validation_id"])
        path.write_text("DASHSCOPE_API_KEY=another-synthetic-key", encoding="utf-8")
        with patch("asr_runtime.application.session.read_api_key", side_effect=AssertionError("must not read credentials")):
            self.assertTrue(self.session.confirm()["ok"])

    def test_description_and_configuration_do_not_read_dotenv(self):
        """验证页面说明与配置流程独立于运行凭据。"""
        with patch("asr_runtime.application.session.read_api_key", side_effect=AssertionError("must not read credentials")):
            self.assertNotIn("auth", self.session.description())
            preview = self.session.validate({**self.payload, "auth_mode": "api_key"})
            self.session.preview_ready(preview["validation_id"])
            self.assertTrue(self.session.confirm()["ok"])

    def test_confirmation_uses_edited_rows_after_excel_is_removed(self):
        """验证词表导入后可编辑，确认阶段复用已校验词典。"""
        path = self.runtime.workspace / "热词.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "热词"
        sheet.append(["text", "weight"])
        sheet.append(["术语", 50])
        workbook.save(path)
        workbook.close()
        content = path.read_bytes()
        uploaded = self.session.receive_hotwords(path.name, io.BytesIO(content), len(content))
        path.unlink()
        uploaded["rows"][0]["weight"] = "4"
        payload = {**self.payload, "enhancement_mode": "both", "hotword_rows": uploaded["rows"],
                   "context": "会议涉及测试术语"}
        preview = self.session.validate(payload)
        self.session.preview_ready(preview["validation_id"])
        self.assertEqual(preview["summary"]["enhancement"]["count"], 1)
        self.assertEqual(preview["summary"]["enhancement"]["context_chars"], len(payload["context"]))
        with patch("asr_runtime.application.session.import_hotwords", side_effect=AssertionError("must not parse Excel again")):
            receipt = self.session.confirm()
        config = json.loads(Path(receipt["config_path"]).read_text(encoding="utf-8"))
        self.assertEqual(config["enhancement"]["hotwords"]["vocabulary"], {"术语": 4})

    def test_browser_rejects_unapproved_output_paths(self):
        """验证客户端提交源码或其他路径时被拒绝。"""
        for path in ("data/audio", "../outside", "transcriptions/meeting", "transcriptions/../.git", "transcriptions/.private"):
            with self.subTest(path=path), self.assertRaises(ValidationError):
                output_directory(self.runtime, path, "json_directory")

    def test_unknown_fields_and_multiple_audio_values_are_rejected(self):
        """验证未知字段和多音频输入被拒绝。"""
        with self.assertRaises(ValidationError):
            self.session.validate({**self.payload, "model": "other-model"})
        with self.assertRaises(ValidationError):
            self.session.validate({**self.payload, "audio_id": ["a", "b"]})

    def test_reselection_invalidates_preview_and_preserves_both_original_files(self):
        """验证重选更新选择编号并使旧预览失效，两份原始录音保持不变。"""
        preview = self.session.validate(self.payload)
        content = self.audio.read_bytes()
        another = self.runtime.workspace / "another.wav"
        another.write_bytes(content)
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=another):
            selection = self.session.select_audio("another-audio")
        self.assertNotEqual(selection["audio_id"], self.payload["audio_id"])
        self.assertEqual(selection["path"], str(another))
        self.assertEqual(self.audio.read_bytes(), content)
        self.assertEqual(another.read_bytes(), content)
        with self.assertRaises(ValidationError):
            self.session.preview_ready(preview["validation_id"])
        with self.assertRaises(ValidationError):
            self.session.confirm()

    def test_cancelled_selection_keeps_original_selection_and_preview(self):
        """验证取消文件窗口保留原选择和已检查的配置。"""
        preview = self.session.validate(self.payload)
        before = self.session.selected_audio.copy()
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=None):
            self.assertEqual(self.session.select_audio("cancel-audio"), {"ok": True, "cancelled": True})
        self.assertEqual(self.session.selected_audio, before)
        self.assertEqual(self.session.draft["id"], preview["validation_id"])

    def test_audio_selection_and_session_cleanup_preserve_original_without_copy(self):
        """验证所选原音频直接进入快照，关闭会话保留文件且不生成副本。"""
        original = self.audio.read_bytes()
        before = set(self.runtime.root.rglob("*"))
        preview = self.session.validate(self.payload)
        self.assertEqual(preview["summary"]["audio"]["path"], str(self.audio))
        self.assertEqual(self.session.draft["config"]["audio"]["path"], str(self.audio))
        self.session.cleanup()
        self.assertEqual(self.audio.read_bytes(), original)
        self.assertEqual(set(self.runtime.root.rglob("*")), before)

    def test_audio_id_cannot_be_used_by_another_session(self):
        """验证跨会话音频选择编号被拒绝。"""
        with self.assertRaises(ValidationError):
            Session(self.runtime).validate(self.payload)
