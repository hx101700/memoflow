"""用事件控制热词接收和路径选择，验证会话的真实并发边界。"""

import io
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from openpyxl import Workbook

from asr_runtime.application.session import Session
from asr_runtime.application.recovery import finish_session
from asr_runtime.application.rules import ValidationError
from asr_runtime.application.inputs import validate_audio
from tests.support import RuntimeTestCase


class PausedInput(io.BytesIO):
    def __init__(self, content):
        """创建可由事件暂停读取的合成输入流。"""
        super().__init__(content)
        self.read_started = threading.Event()
        self.release = threading.Event()

    def read(self, size=-1):
        """发出读取事件并等待测试允许继续。"""
        self.read_started.set()
        if not self.release.wait(timeout=5):
            raise AssertionError("测试未释放文件读取")
        return super().read(size)


class SessionConcurrencyTests(RuntimeTestCase):
    def setUp(self):
        """准备已选择的原音频和仅在内存中的热词样本。"""
        super().setUp()
        self.session = Session(self.runtime)
        self.audio_path = self.runtime.workspace / "original.wav"
        with wave.open(str(self.audio_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0" * 32000)
        self.audio = self.audio_path.read_bytes()
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=self.audio_path):
            selected = self.session.select_audio("fixture-audio")
        self.payload = {
            "auth_mode": "console", "audio_id": selected["audio_id"],
            "diarization_enabled": True, "enhancement_mode": "none",
            "hotword_rows": [], "context": "",
            "json_directory": "default", "document_directory": "default",
        }
        workbook = Workbook()
        workbook.active.append(["text", "weight"])
        workbook.active.append(["fixture", 4])
        content = io.BytesIO()
        workbook.save(content)
        workbook.close()
        self.hotwords = content.getvalue()

    def tearDown(self):
        """关闭会话并清理测试记录，验证原音频保持完整。"""
        self.session.cleanup()
        finish_session(self.runtime, self.session.session_id)
        self.assertEqual(self.audio_path.read_bytes(), self.audio)
        super().tearDown()

    def test_cancel_picker_completes_while_hotword_receive_is_paused(self):
        """验证热词接收暂停时仍能取消原生窗口。"""
        source = PausedInput(self.hotwords)
        picker_started = threading.Event()
        picker_events = []

        def wait_for_cancel(_initial, *, mode, audio_suffixes, cancel_event):
            """等待取消事件并结束模拟目录窗口。"""
            picker_events.append(cancel_event)
            picker_started.set()
            if not cancel_event.wait(timeout=5):
                raise AssertionError("目录选择未收到取消")
            return None

        with patch("asr_runtime.utils.path_picker.choose_path", side_effect=wait_for_cancel), \
                ThreadPoolExecutor(max_workers=3) as pool:
            selecting = pool.submit(self.session.select_directory, "json", "during-import")
            try:
                self.assertTrue(picker_started.wait(timeout=2))
                receiving = pool.submit(self.session.receive_hotwords, "words.xlsx", source, len(self.hotwords))
                self.assertTrue(source.read_started.wait(timeout=2))
                cancelling = pool.submit(self.session.cancel_picker, "during-import")
                self.assertTrue(cancelling.result(timeout=1)["ok"])
                self.assertTrue(picker_events[0].is_set())
                self.assertTrue(selecting.result(timeout=1)["cancelled"])
                self.assertFalse(receiving.done())
            finally:
                source.release.set()
                self.session.cancel_picker("during-import")
            self.assertTrue(receiving.result(timeout=2)["ok"])

    def test_concurrent_hotword_import_is_rejected_before_reading(self):
        """验证同一会话只接收一份热词，后来的请求保持未读取。"""
        source = PausedInput(self.hotwords)
        other = io.BytesIO(self.hotwords)
        with ThreadPoolExecutor(max_workers=2) as pool:
            receiving = pool.submit(self.session.receive_hotwords, "words.xlsx", source, len(self.hotwords))
            try:
                self.assertTrue(source.read_started.wait(timeout=2))
                duplicate = pool.submit(self.session.receive_hotwords, "duplicate.xlsx", other, len(self.hotwords))
                with self.assertRaisesRegex(ValidationError, "正在添加"):
                    duplicate.result(timeout=1)
                self.assertEqual(other.tell(), 0)
            finally:
                source.release.set()
            self.assertTrue(receiving.result(timeout=2)["ok"])
        self.assertFalse(self.session._receiving_hotwords)

    def test_audio_selection_can_change_while_hotwords_receive(self):
        """验证原音频选择与热词内存接收相互独立。"""
        source = PausedInput(self.hotwords)
        with ThreadPoolExecutor(max_workers=1) as pool:
            receiving = pool.submit(self.session.receive_hotwords, "words.xlsx", source, len(self.hotwords))
            try:
                self.assertTrue(source.read_started.wait(timeout=2))
                with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=self.audio_path):
                    selected = self.session.select_audio("reselect-audio")
                self.assertNotEqual(selected["audio_id"], self.payload["audio_id"])
                self.assertEqual(selected["path"], str(self.audio_path))
                self.assertFalse(receiving.done())
            finally:
                source.release.set()
            self.assertEqual(receiving.result(timeout=2)["rows"], [{"text": "fixture", "weight": 4}])

    def test_pending_hotwords_block_preview_and_confirmation(self):
        """验证热词接收完成前拒绝预览和交接。"""
        self.session.validate(self.payload)
        source = PausedInput(self.hotwords)
        with ThreadPoolExecutor(max_workers=3) as pool:
            receiving = pool.submit(self.session.receive_hotwords, "words.xlsx", source, len(self.hotwords))
            try:
                self.assertTrue(source.read_started.wait(timeout=2))
                validating = pool.submit(self.session.validate, self.payload)
                confirming = pool.submit(self.session.confirm)
                for action in (validating, confirming):
                    with self.assertRaisesRegex(ValidationError, "仍在添加"):
                        action.result(timeout=1)
                self.assertIsNone(self.session.draft)
                self.assertIsNone(self.session.receipt)
                self.assertFalse(self.runtime.path(".state/jobs").exists())
            finally:
                source.release.set()
            receiving.result(timeout=2)

    def test_close_rejects_late_hotword_result_without_writing_files(self):
        """验证关闭会话后拒绝迟到热词结果，全程没有输入副本落盘。"""
        source = PausedInput(self.hotwords)
        files_before = set(self.runtime.root.rglob("*"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            receiving = pool.submit(self.session.receive_hotwords, "words.xlsx", source, len(self.hotwords))
            try:
                self.assertTrue(source.read_started.wait(timeout=2))
                self.assertEqual(set(self.runtime.root.rglob("*")), files_before)
                pool.submit(self.session.cleanup).result(timeout=1)
                self.assertFalse(receiving.done())
            finally:
                source.release.set()
            with self.assertRaisesRegex(ValidationError, "会话已关闭"):
                receiving.result(timeout=2)
        self.assertEqual(set(self.runtime.root.rglob("*")), files_before)
        self.assertFalse(self.session._receiving_hotwords)
        with self.assertRaisesRegex(ValidationError, "会话已关闭"):
            self.session.validate(self.payload)

    def test_failed_import_keeps_audio_and_invalidates_previous_preview(self):
        """验证热词文件解析失败保留音频选择并使旧预览失效。"""
        preview = self.session.validate(self.payload)
        selected = self.session.selected_audio.copy()
        with self.assertRaises(ValidationError):
            self.session.receive_hotwords("broken.xlsx", io.BytesIO(b"broken"), 6)
        self.assertEqual(self.session.selected_audio, selected)
        self.assertIsNone(self.session.draft)
        self.assertFalse(self.session._receiving_hotwords)
        self.assertNotEqual(self.session.validate(self.payload)["validation_id"], preview["validation_id"])

    def test_cancel_picker_does_not_wait_for_audio_validation(self):
        """验证原音频校验期间仍可及时取消目录窗口。"""
        picker_started = threading.Event()
        validation_started = threading.Event()
        release_validation = threading.Event()
        picker_events = []

        def wait_for_cancel(_initial, *, mode, audio_suffixes, cancel_event):
            """等待取消信号以模拟正在打开的目录窗口。"""
            picker_events.append(cancel_event)
            picker_started.set()
            if not cancel_event.wait(timeout=5):
                raise AssertionError("目录选择未收到取消")
            return None

        def paused_validation(*args):
            """暂停音频校验直到测试事件放行。"""
            validation_started.set()
            if not release_validation.wait(timeout=5):
                raise AssertionError("测试未释放音频校验")
            return validate_audio(*args)

        with patch("asr_runtime.utils.path_picker.choose_path", side_effect=wait_for_cancel), \
                patch("asr_runtime.application.session.validate_audio", side_effect=paused_validation), \
                ThreadPoolExecutor(max_workers=3) as pool:
            selecting = pool.submit(self.session.select_directory, "json", "during-validation")
            try:
                self.assertTrue(picker_started.wait(timeout=2))
                validating = pool.submit(self.session.validate, self.payload)
                self.assertTrue(validation_started.wait(timeout=2))
                cancelling = pool.submit(self.session.cancel_picker, "during-validation")
                self.assertTrue(cancelling.result(timeout=1)["ok"])
                self.assertTrue(picker_events[0].is_set())
                self.assertTrue(selecting.result(timeout=1)["cancelled"])
                self.assertFalse(validating.done())
            finally:
                release_validation.set()
                self.session.cancel_picker("during-validation")
            self.assertTrue(validating.result(timeout=5)["ok"])
