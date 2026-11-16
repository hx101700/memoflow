"""验证人工回听的草稿版本、原件保留、独立导出和媒体复用。"""

import json
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from docx import Document
from openpyxl import load_workbook

from asr_runtime import MODEL
from asr_runtime.application.inputs import validate_audio
from asr_runtime.application.review import ReviewConflict, ReviewError, ReviewSession, read_review_status
from asr_runtime.utils.documents import write_xlsx
from asr_runtime.utils.files import write_json_atomic
from asr_runtime.utils.job_files import job_directory, publish_config, save_record
from asr_runtime.utils.media import convert_to_mono, prepare_playback, probe_audio
from asr_runtime.models import AudioInfo
from asr_runtime.review_web import create_review_server
from asr_runtime.utils.results import load_transcript
from tests.support import RuntimeTestCase


class ReviewTests(RuntimeTestCase):
    def setUp(self):
        """保存合成录音、已验收JSON和原始成品标记。"""
        super().setUp()
        self.job_id = "b" * 32
        self.audio = self.runtime.workspace / "合成录音.wav"
        with wave.open(str(self.audio), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\0\0" * 32000)
        base = self.runtime.output_root / self.job_id
        self.config = {
            "schema_version": 1, "job_id": self.job_id, "model": MODEL, "region": "cn-beijing",
            "auth_mode": "console", "audio": validate_audio(self.audio, True), "diarization_enabled": True,
            "recognition_options": {"language_hints": [], "speaker_count": None},
            "enhancement": {"mode": "none", "hotwords": None, "context": None},
            "json_directory": str(base / "json"), "document_directory": str(base / "documents"),
            "status": "CONFIGURED", "execution_authorized": True, "confirmed_at": "synthetic-time",
        }
        publish_config(self.runtime, self.config)
        self.root = job_directory(self.runtime, self.job_id)
        (self.root / "execution").mkdir()
        self.json_path = base / "json/transcription.json"
        self.json_path.parent.mkdir(parents=True)
        write_json_atomic(self.json_path, {"transcripts": [{"channel_id": 0, "sentences": [
            {"begin_time": 0, "end_time": 500, "text": "原文第一句", "speaker_id": 0},
            {"begin_time": 500, "end_time": 1000, "text": "原文第二句"},
        ]}]})
        self.execution = {"job_id": self.job_id, "status": "JSON_READY", "cloud_outcome": "result_received",
                          "result": load_transcript(self.json_path).summary()}
        save_record(self.root / "execution", self.execution)
        self.original_files = {self.json_path: self.json_path.read_bytes(),
                               self.root / "config.json": (self.root / "config.json").read_bytes()}
        documents = Path(self.config["document_directory"])
        documents.mkdir()
        for extension in ("docx", "xlsx", "md"):
            path = documents / f"transcription.{extension}"
            path.write_bytes(b"original document")
            self.original_files[path] = path.read_bytes()
        cloud = patch("asr_runtime.utils.bailian.run_recognition", side_effect=AssertionError("回听不能调用BL"))
        self.cloud = cloud.start()
        self.addCleanup(cloud.stop)

    def open_review(self):
        """打开本例任务的回听会话，并登记测试结束后的关闭动作。"""
        review = ReviewSession(self.runtime, self.job_id)
        self.addCleanup(review.close)
        return review

    def edit_first(self, review, revision=0, text="已校对第一句"):
        """提交第一句正文、归属及新说话人姓名。"""
        return review.save({"revision": revision,
                            "sentences": [{"index": 1, "text": text, "speaker_id": 3}],
                            "speakers": [{"id": 3, "name": "张老师"}]})

    def export_review(self, review, revision=1, directory=None):
        """模拟用户选择现有目录，执行真实三格式校对导出。"""
        selected = directory if directory is not None else Path(self.config["document_directory"])
        with patch.object(review._picker, "select", return_value=selected):
            return review.export({"revision": revision, "picker_id": "export-directory"})

    def test_open_requires_verified_result_and_matching_source(self):
        """验证尚未成功或原JSON已修改时拒绝打开，并保留现有文件。"""
        save_record(self.root / "execution", {**self.execution, "status": "STOPPED"})
        with self.assertRaises(ReviewError):
            self.open_review()
        save_record(self.root / "execution", self.execution)
        self.json_path.write_bytes(self.json_path.read_bytes() + b"\n")
        with self.assertRaises(ReviewError):
            self.open_review()
        self.assertFalse((self.root / "review").exists())

    def test_save_and_reopen_preserve_order_timing_and_original_files(self):
        """验证草稿可恢复且只覆盖可编辑字段，原JSON和原稿保持不变。"""
        review = self.open_review()
        self.assertEqual(self.edit_first(review), {"ok": True, "revision": 1})
        review.close()
        restored = self.open_review().description()
        self.assertEqual(restored["revision"], 1)
        self.assertEqual(restored["sentences"][0], {"index": 1, "begin_ms": 0, "end_ms": 500,
                                                  "text": "已校对第一句", "speaker_id": 3,
                                                  "original_text": "原文第一句", "original_speaker_id": 0})
        self.assertEqual(restored["sentences"][1]["text"], "原文第二句")
        self.assertIn({"id": 3, "name": "张老师"}, restored["speakers"])
        for path, original in self.original_files.items():
            self.assertEqual(path.read_bytes(), original)
        draft = json.loads((self.root / "review/draft.json").read_bytes())
        self.assertEqual(draft["source_sha256"], self.execution["result"]["sha256"])
        self.assertNotIn("begin_ms", draft["sentences"][0])
        self.cloud.assert_not_called()

    def test_stale_save_and_immutable_fields_are_rejected(self):
        """验证旧版本、伪造句子和时间改动均不能覆盖已保存草稿。"""
        review = self.open_review()
        self.edit_first(review)
        with self.assertRaises(ReviewConflict):
            self.edit_first(review, text="过期改动")
        for row in ({"index": 1, "text": "text", "speaker_id": 0, "begin_ms": 20},
                    {"index": 3, "text": "text", "speaker_id": 0},
                    {"index": 1, "text": "text", "speaker_id": True}):
            with self.subTest(row=row), self.assertRaises(ReviewError):
                review.save({"revision": 1, "sentences": [row]})
        self.assertEqual(review.description()["revision"], 1)

    def test_failed_save_keeps_memory_and_disk_revision(self):
        """验证磁盘保存失败不会让内存版本领先或丢掉已保存输入。"""
        review = self.open_review()
        self.edit_first(review)
        path = self.root / "review/draft.json"
        original = path.read_bytes()
        with patch("asr_runtime.application.review.write_json_atomic", side_effect=OSError("private location")), \
                self.assertRaises(ReviewError) as caught:
            self.edit_first(review, revision=1, text="尚未保存")
        self.assertNotIn("private location", str(caught.exception))
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(review.description()["revision"], 1)
        self.assertEqual(review.description()["sentences"][0]["text"], "已校对第一句")

    def test_concurrent_saves_have_one_winner(self):
        """验证同一版本的两个标签页保存只有一个能成功。"""
        review = self.open_review()
        ready = threading.Barrier(2)

        def save(text):
            """同时提交相同旧版本的两份输入。"""
            ready.wait(timeout=5)
            try:
                self.edit_first(review, text=text)
                return True
            except ReviewConflict:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            left, right = pool.submit(save, "甲"), pool.submit(save, "乙")
            self.assertEqual(sum((left.result(timeout=5), right.result(timeout=5))), 1)
        self.assertEqual(review.description()["revision"], 1)

    def test_export_uses_selected_directory_and_distinct_names_without_touching_originals(self):
        """验证三格式写入所选目录，即使选择原稿目录也不覆盖原文件。"""
        review = self.open_review()
        self.edit_first(review, text='=HYPERLINK("https://example.invalid")')
        report = self.export_review(review)
        self.assertFalse(report["cancelled"])
        self.assertEqual(report["export_revision"], 1)
        self.assertEqual(report["delivery"]["status"], "COMPLETE")
        files = report["delivery"]["files"]
        for extension, record in files.items():
            self.assertEqual(Path(record["path"]), Path(self.config["document_directory"]) / f"transcription-reviewed.{extension}")
        with Path(files["xlsx"]["path"]).open("rb") as stream:
            workbook = load_workbook(stream)
            try:
                self.assertEqual(workbook.active["E4"].value, "张老师")
                self.assertEqual(workbook.active["F4"].data_type, "s")
            finally:
                workbook.close()
        self.assertIn("张老师", "\n".join(paragraph.text for paragraph in Document(files["docx"]["path"]).paragraphs))
        self.assertIn("张老师", Path(files["md"]["path"]).read_text(encoding="utf-8"))
        for path, original in self.original_files.items():
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(read_review_status(self.runtime, self.job_id)["export_revision"], 1)
        self.assertEqual(self.open_review().description()["delivery"], report["delivery"])
        self.cloud.assert_not_called()

    def test_export_cancel_keeps_previous_delivery_and_creates_no_files(self):
        """验证取消选择不启动导出，已有导出记录和文件保持原样。"""
        review = self.open_review()
        self.edit_first(review)
        with patch.object(review._picker, "select", return_value=None), \
                patch("asr_runtime.application.review.export_documents", side_effect=AssertionError("取消不能导出")):
            self.assertEqual(review.export({"revision": 1, "picker_id": "cancelled"}), {"ok": True, "cancelled": True})
        self.assertFalse((self.root / "review/status.json").exists())
        self.assertFalse(list(Path(self.config["document_directory"]).glob("transcription-reviewed.*")))
        completed = self.export_review(review)
        status = (self.root / "review/status.json").read_bytes()
        with patch.object(review._picker, "select", return_value=None):
            self.assertTrue(review.export({"revision": 1, "picker_id": "cancelled-again"})["cancelled"])
        self.assertEqual((self.root / "review/status.json").read_bytes(), status)
        self.assertEqual(review.description()["delivery"], completed["delivery"])

    def test_export_picker_starts_at_last_successful_directory_after_reopen(self):
        """验证重开后目录选择从最近成功成品位置开始，初次使用原稿目录。"""
        review = self.open_review()
        self.edit_first(review)
        selected = self.runtime.workspace / "人工选择目录"
        selected.mkdir()
        with patch.object(review._picker, "select", return_value=selected) as picker:
            report = review.export({"revision": 1, "picker_id": "first-export"})
        picker.assert_called_once_with(Path(self.config["document_directory"]), "first-export", mode="directory")
        self.assertEqual(report["delivery"]["status"], "COMPLETE")
        review.close()
        reopened = self.open_review()
        with patch.object(reopened._picker, "select", return_value=None) as picker:
            reopened.export({"revision": 1, "picker_id": "next-export"})
        picker.assert_called_once_with(selected, "next-export", mode="directory")

    def test_directory_selection_does_not_block_saves_and_rechecks_revision(self):
        """验证选择目录时可以保存，但过期导出请求不能悄悄导出新版本。"""
        review = self.open_review()
        self.edit_first(review)
        started, release = threading.Event(), threading.Event()

        def select(*args, **kwargs):
            """暂停目录选择，让另一标签页先保存新版本。"""
            started.set()
            if not release.wait(5):
                raise AssertionError("未释放目录选择")
            return Path(self.config["document_directory"])

        with patch.object(review._picker, "select", side_effect=select), ThreadPoolExecutor(max_workers=2) as pool:
            exporting = pool.submit(review.export, {"revision": 1, "picker_id": "waiting"})
            try:
                self.assertTrue(started.wait(5))
                self.assertEqual(pool.submit(self.edit_first, review, 1, "新版本").result(timeout=2)["revision"], 2)
            finally:
                release.set()
            with self.assertRaises(ReviewConflict):
                exporting.result(timeout=5)
        self.assertFalse((self.root / "review/status.json").exists())

    def test_close_session_releases_waiting_export_picker(self):
        """验证关闭会话会释放等待中的目录窗口，不创建校对成品。"""
        review = self.open_review()
        self.edit_first(review)
        started = threading.Event()

        def wait_for_cancel(initial, *, mode, audio_suffixes, cancel_event):
            """模拟原生目录窗口，收到会话关闭信号后结束。"""
            self.assertEqual(mode, "directory")
            started.set()
            if not cancel_event.wait(5):
                raise AssertionError("未收到取消信号")
            return None

        with patch("asr_runtime.utils.path_picker.choose_path", side_effect=wait_for_cancel), ThreadPoolExecutor(max_workers=1) as pool:
            exporting = pool.submit(review.export, {"revision": 1, "picker_id": "cancel-export"})
            self.assertTrue(started.wait(5))
            review.close()
            self.assertEqual(exporting.result(timeout=5), {"ok": True, "cancelled": True})
        self.assertTrue(review.description()["closed"])
        self.assertEqual(review.description()["revision"], 1)
        self.assertFalse((self.root / "review/status.json").exists())

    def test_reset_sentence_removes_override_but_keeps_global_names(self):
        """验证恢复原文和归属会删除句子覆盖项，姓名与原时间保持独立。"""
        review = self.open_review()
        self.edit_first(review)
        original = review.description()["sentences"][0]
        self.assertIn({"id": 0, "name": ""}, review.description()["speakers"])
        result = review.save({"revision": 1, "sentences": [{"index": 1,
            "text": original["original_text"], "speaker_id": original["original_speaker_id"]}]})
        self.assertEqual(result["revision"], 2)
        draft = json.loads((self.root / "review/draft.json").read_bytes())
        self.assertEqual(draft["sentences"], [])
        self.assertEqual(draft["speakers"], [{"id": 3, "name": "张老师"}])
        restored = self.open_review().description()["sentences"][0]
        self.assertEqual((restored["text"], restored["speaker_id"]), ("原文第一句", 0))
        self.assertEqual((restored["begin_ms"], restored["end_ms"]), (0, 500))

    def test_partial_export_preserves_other_formats_and_draft(self):
        """验证一种格式失败不阻止其余成品，也不改动校对草稿。"""
        review = self.open_review()
        self.edit_first(review)
        with patch("asr_runtime.application.delivery.write_docx", side_effect=ValueError("private sentence")):
            report = self.export_review(review)
        self.assertEqual(report["delivery"]["status"], "PARTIAL")
        self.assertNotIn("private sentence", json.dumps(report))
        self.assertEqual(report["delivery"]["files"]["xlsx"]["status"], "READY")
        self.assertEqual(report["delivery"]["files"]["md"]["status"], "READY")
        self.assertEqual(review.description()["revision"], 1)

    def test_saves_can_continue_during_export_but_overlapping_export_is_rejected(self):
        """验证导出固定旧快照，后续保存不阻塞且导出版本不会被误标为最新。"""
        review = self.open_review()
        self.edit_first(review)
        started, release = threading.Event(), threading.Event()

        def paused_writer(*args, **kwargs):
            """在首个文档生成前暂停，使测试能提交下一版校对。"""
            started.set()
            if not release.wait(5):
                raise AssertionError("未释放导出")
            write_xlsx(*args, **kwargs)

        with patch("asr_runtime.application.delivery.write_xlsx", side_effect=paused_writer), \
                patch.object(review._picker, "select", return_value=Path(self.config["document_directory"])), \
                ThreadPoolExecutor(max_workers=2) as pool:
            exporting = pool.submit(review.export, {"revision": 1, "picker_id": "exporting"})
            try:
                self.assertTrue(started.wait(5))
                self.assertEqual(pool.submit(self.edit_first, review, 1, "最新正文").result(timeout=2)["revision"], 2)
                with self.assertRaises(ReviewError):
                    review.export({"revision": 2, "picker_id": "duplicate"})
            finally:
                release.set()
            report = exporting.result(timeout=10)
        self.assertEqual((report["export_revision"], report["revision"]), (1, 2))
        self.assertEqual(review.description()["sentences"][0]["text"], "最新正文")
        markdown = Path(report["delivery"]["files"]["md"]["path"]).read_text(encoding="utf-8")
        self.assertIn("已校对第一句", markdown)
        self.assertNotIn("最新正文", markdown)

    def test_missing_original_uses_existing_mono_copy(self):
        """验证原文件不可读时绑定任务已有单声道副本。"""
        mono = self.root / "execution/mono.flac"
        convert_to_mono(self.audio, mono, AudioInfo(**self.config["audio"]["metadata"]))
        self.audio.unlink()
        review = self.open_review()
        self.assertEqual(review.description()["audio"]["kind"], "mono")
        self.assertEqual(review.audio_path(), mono)

    def test_missing_audio_can_rebind_only_identical_original(self):
        """验证录音移动后可按摘要重新绑定，错误文件不会改变草稿。"""
        moved = self.audio.with_name("moved.wav")
        self.audio.rename(moved)
        review = self.open_review()
        self.assertFalse(review.description()["audio"]["available"])
        wrong = self.audio.with_name("wrong.wav")
        wrong.write_bytes(b"different recording")
        with patch.object(review._picker, "select", return_value=wrong), self.assertRaises(ReviewError):
            review.select_audio("wrong")
        self.assertEqual(review.description()["revision"], 0)
        with patch.object(review._picker, "select", return_value=moved):
            selected = review.select_audio("moved")
        self.assertEqual(selected["revision"], 1)
        self.assertEqual(review.audio_path(), moved)
        self.assertEqual(self.open_review().audio_path(), moved)
        self.assertEqual((self.root / "config.json").read_bytes(), self.original_files[self.root / "config.json"])

    def test_playback_conversion_runs_once_and_keeps_original(self):
        """验证完整MP3可播放并复用，不因重复准备再次转码。"""
        original = self.audio.read_bytes()
        review = self.open_review()
        with patch("asr_runtime.application.review.prepare_playback", wraps=prepare_playback) as convert:
            self.assertEqual(review.prepare_audio()["audio"]["kind"], "preview")
            playback = review.audio_path()
            self.assertEqual(review.prepare_audio()["audio"]["kind"], "preview")
            self.open_review().prepare_audio()
        convert.assert_called_once()
        self.assertEqual(playback, self.root / "review/playback.mp3")
        self.assertGreater(probe_audio(playback).duration_seconds, 0)
        self.assertEqual(self.audio.read_bytes(), original)

    def test_playback_preparation_does_not_block_saves(self):
        """验证音频转码在状态锁外执行，页面可以继续自动保存。"""
        review = self.open_review()
        started, release = threading.Event(), threading.Event()

        def paused_conversion(source, target):
            """等待测试保存校对后再执行真实媒体转换。"""
            started.set()
            if not release.wait(5):
                raise AssertionError("未释放音频转换")
            prepare_playback(source, target)

        with patch("asr_runtime.application.review.prepare_playback", side_effect=paused_conversion), \
                ThreadPoolExecutor(max_workers=2) as pool:
            converting = pool.submit(review.prepare_audio)
            try:
                self.assertTrue(started.wait(5))
                self.assertEqual(pool.submit(self.edit_first, review).result(timeout=2)["revision"], 1)
            finally:
                release.set()
            self.assertTrue(converting.result(timeout=10)["audio"]["available"])

    def test_closed_session_rejects_writes_and_keeps_saved_draft(self):
        """验证关闭只释放会话，不删除可恢复草稿或重新生成原稿。"""
        review = self.open_review()
        self.edit_first(review)
        review.close()
        self.assertTrue(review.description()["closed"])
        with self.assertRaises(ReviewError):
            self.edit_first(review, revision=1)
        with self.assertRaises(ReviewError):
            review.export({"revision": 1, "picker_id": "closed"})
        self.assertTrue((self.root / "review/draft.json").is_file())

    def test_corrupt_draft_is_not_reset_or_overwritten(self):
        """验证损坏草稿需要检查，打开失败不静默丢失人工改动。"""
        self.edit_first(self.open_review())
        path = self.root / "review/draft.json"
        path.write_bytes(b"{")
        with self.assertRaises(ReviewError):
            self.open_review()
        self.assertEqual(path.read_bytes(), b"{")

    def test_incomplete_delivery_record_is_not_reported_complete(self):
        """验证校对导出记录缺少成品时返回未知，不误报三格式已就绪。"""
        self.open_review()
        save_record(self.root / "review", {"job_id": self.job_id, "status": "COMPLETE", "files": {},
                                           "export_revision": 0, "message": "synthetic"})
        self.assertEqual(read_review_status(self.runtime, self.job_id)["delivery"]["status"], "OUTCOME_UNKNOWN")

    def test_missing_result_checksum_stops_review(self):
        """验证已标记成功但缺少摘要的旧记录不能打开校对。"""
        self.execution.pop("result")
        save_record(self.root / "execution", self.execution)
        with self.assertRaises(ReviewError):
            self.open_review()

    def test_close_response_failure_still_stops_service_and_allows_reopen(self):
        """验证关闭回执写入断管后仍停止服务，后续可以重开已保存校对。"""
        server = create_review_server(self.runtime, self.job_id)
        try:
            self.edit_first(server.session)
            handler = object.__new__(server.RequestHandlerClass)
            handler.server = server
            handler.headers = Message()
            handler.path = "/api/review/close"
            with patch.object(handler, "allowed", return_value=True), \
                    patch.object(handler, "read_json", return_value={}), \
                    patch.object(handler, "json", side_effect=BrokenPipeError("closed browser")), \
                    patch.object(handler, "error_response"), patch.object(server, "shutdown") as shutdown:
                handler.do_POST()
            shutdown.assert_called_once()
            self.assertTrue(server.session.description()["closed"])
        finally:
            server.server_close()
        self.assertFalse((self.root / "review/connection.json").exists())
        self.assertEqual(self.open_review().description()["revision"], 1)
