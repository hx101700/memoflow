"""验证人工回听的本机HTTP边界、音频读取和独立校对交付。"""

import http.client
import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import av
from docx import Document
from openpyxl import load_workbook

from asr_runtime import review_web
from asr_runtime.__main__ import main
from asr_runtime.application.recovery import finish_session
from asr_runtime.application.session import Session
from asr_runtime.application.transcription import export_job
from asr_runtime.utils.job_files import job_directory, result_path, save_record
from asr_runtime.utils.results import load_transcript
from tests.support import SKILL_ROOT
from tests.test_session import WebFixture
from tests.test_transcription import transcript_result


class ReviewFixture(WebFixture):
    def setUp(self) -> None:
        """以真实交接配置和合成JSON建立已完成任务，不调用云端。"""
        super().setUp()
        session = Session(self.runtime)
        try:
            preview = session.validate(self.payload_for(session))
            session.preview_ready(preview["validation_id"])
            receipt = session.confirm()
        finally:
            session.cleanup()
            finish_session(self.runtime, session.session_id)
        self.job_id = receipt["job_id"]
        self.job_root = job_directory(self.runtime, self.job_id)
        self.config_path = Path(receipt["config_path"])
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.json_path = result_path(self.config)
        self.json_path.parent.mkdir(parents=True)
        result = transcript_result("原始第一句。")
        result["transcripts"][0]["sentences"].append({
            "text": "原始第二句。", "begin_time": 900, "end_time": 1000, "speaker_id": 1,
        })
        self.json_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        execution = self.job_root / "execution"
        execution.mkdir()
        save_record(execution, {
            "job_id": self.job_id, "status": "JSON_READY", "cloud_outcome": "result_received",
            "json_path": str(self.json_path), "result": load_transcript(self.json_path).summary(),
        })
        self.original_json = self.json_path.read_bytes()
        self.original_config = self.config_path.read_bytes()
        self.original_audio = self.audio.read_bytes()
        cloud = patch("asr_runtime.application.transcription.run_recognition",
                      side_effect=AssertionError("人工回听不得调用云端识别"))
        self.cloud = cloud.start()
        self.addCleanup(cloud.stop)


class ReviewWebTests(ReviewFixture):
    def setUp(self) -> None:
        """启动回听HTTP服务并通过本机页面取得浏览器Cookie。"""
        super().setUp()
        picker = patch("asr_runtime.utils.path_picker.choose_path",
                       side_effect=AssertionError("HTTP测试必须替代原生路径窗口"))
        picker.start()
        self.addCleanup(picker.stop)
        self.start_server()

    def start_server(self) -> None:
        """为同一任务创建回听服务并取得当前连接的页面Cookie。"""
        self.server = review_web.create_review_server(self.runtime, self.job_id)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        self.cookie = ""
        status, headers, _ = self.request("GET", "/review", authenticated=False)
        self.assertEqual(status, 200)
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]

    def tearDown(self) -> None:
        """停止本例服务并释放连接，再清理合成任务。"""
        try:
            self.stop_server()
        finally:
            super().tearDown()

    def stop_server(self) -> None:
        """关闭当前服务并等待线程释放，保留任务供重开测试。"""
        if self.worker.is_alive():
            self.server.shutdown()
        self.worker.join(timeout=5)
        self.server.server_close()

    def request(self, method: str, path: str, payload: object = None, *,
                authenticated: bool = True, headers: dict[str, str | None] | None = None,
                body: bytes | None = None) -> tuple[int, dict[str, str], bytes]:
        """请求本机回听接口，返回状态、响应头和原始正文。"""
        supplied = {"Origin": self.origin}
        if authenticated:
            supplied["Cookie"] = self.cookie
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            supplied["Content-Type"] = "application/json"
        for key, value in (headers or {}).items():
            if value is None:
                supplied.pop(key, None)
            else:
                supplied[key] = value
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=supplied)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def description(self) -> dict[str, object]:
        """读取并核对当前任务的回听页面描述。"""
        status, _, body = self.request("GET", "/api/review")
        self.assertEqual(status, 200)
        return json.loads(body)

    def test_review_page_uses_local_assets_and_private_cookie(self) -> None:
        """验证回听页使用共享构建资源，并以受限Cookie访问内容。"""
        status, headers, body = self.request("GET", "/review", authenticated=False)
        self.assertEqual(status, 200)
        self.assertIn(b'<div id="app"></div>', body)
        self.assertIn(b'/app.js', body)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        for path in ("/app.js", "/app.css", "/favicon.svg"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path, authenticated=False)[0], 200)
        self.assertEqual(self.request("GET", "/.env")[0], 404)
        self.assertEqual(self.request("GET", "/api/review/audio/../../config.json")[0], 404)
        self.assertEqual(self.description()["job_id"], self.job_id)

    def test_content_and_audio_require_cookie_or_code_token(self) -> None:
        """验证任务正文与音频不能由没有当前连接权限的请求读取。"""
        for method, path in (("GET", "/api/review"), ("GET", "/api/review/audio"),
                             ("HEAD", "/api/review/audio")):
            with self.subTest(method=method, path=path):
                self.assertEqual(self.request(method, path, authenticated=False)[0], 403)
                self.assertEqual(self.request(method, path, authenticated=False,
                                              headers={"X-ASR-Token": "invalid-token"})[0], 403)
        token = self.cookie.split("=", 1)[1]
        status, _, body = self.request("GET", "/api/review", authenticated=False,
                                       headers={"X-ASR-Token": token})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["job_id"], self.job_id)

    def test_wrong_host_and_cross_origin_requests_are_rejected(self) -> None:
        """验证Host与跨源限制同时保护页面、音频和修改入口。"""
        for path in ("/review", "/api/review", "/api/review/audio"):
            for headers in ({"Host": "evil.example"}, {"Origin": "https://evil.example"}):
                with self.subTest(path=path, headers=headers):
                    self.assertEqual(self.request("GET", path, headers=headers)[0], 403)
        previous = self.description()
        for path in ("save", "export", "select-audio", "prepare-audio", "close"):
            for origin in ("https://evil.example", None):
                with self.subTest(path=path, origin=origin):
                    # 先等待来源拒绝，不向已经拒绝的连接继续发送正文。
                    status, _, _ = self.request("POST", "/api/review/" + path, headers={
                        "Origin": origin, "Content-Type": "application/json", "Content-Length": "2",
                    })
                    self.assertEqual(status, 403)
            self.assertEqual(self.request("POST", "/api/review/" + path, authenticated=False, headers={
                "Content-Type": "application/json", "Content-Length": "2",
            })[0], 403)
        self.assertEqual(self.description()["revision"], previous["revision"])
        self.assertEqual(self.json_path.read_bytes(), self.original_json)

    def test_audio_full_get_and_head_preserve_exact_source_bytes(self) -> None:
        """验证完整回听响应读取原录音，HEAD只提供等长元信息。"""
        status, headers, body = self.request("GET", "/api/review/audio")
        self.assertEqual(status, 200)
        self.assertEqual(body, self.original_audio)
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        self.assertEqual(int(headers["Content-Length"]), len(self.original_audio))
        status, head, body = self.request("HEAD", "/api/review/audio")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(head["Content-Length"], headers["Content-Length"])
        self.assertEqual(head["Content-Type"], headers["Content-Type"])
        self.assertEqual(self.audio.read_bytes(), self.original_audio)

    def test_audio_range_supports_bounded_open_and_suffix_requests(self) -> None:
        """验证播放器常用的起止、开放结尾和末尾字节读取。"""
        size = len(self.original_audio)
        cases = (("bytes=0-15", 0, 15), ("bytes=31-", 31, size - 1),
                 ("bytes=-29", size - 29, size - 1), (f"bytes={size - 11}-{size + 100}", size - 11, size - 1))
        for value, start, end in cases:
            with self.subTest(range=value):
                status, headers, body = self.request("GET", "/api/review/audio", headers={"Range": value})
                self.assertEqual(status, 206)
                self.assertEqual(headers["Content-Range"], f"bytes {start}-{end}/{size}")
                self.assertEqual(int(headers["Content-Length"]), end - start + 1)
                self.assertEqual(body, self.original_audio[start:end + 1])

    def test_aborted_playback_read_finishes_without_a_second_response(self) -> None:
        """浏览器跳转中止旧音频读取时正常收尾，覆盖Windows的10053中断。"""
        handler_type = self.server.RequestHandlerClass
        for error_type in (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            with self.subTest(error=error_type.__name__):
                handler = object.__new__(handler_type)
                handler.headers = {"Range": "bytes=0-15"}
                handler.wfile = Mock()
                handler.wfile.write.side_effect = error_type(10053, "synthetic playback cancellation")
                with patch.object(handler, "send_response") as response, \
                     patch.object(handler, "send_header"), patch.object(handler, "end_headers"):
                    handler.send_audio()
                response.assert_called_once_with(206)
                handler.wfile.write.assert_called_once()
        self.assertEqual(self.audio.read_bytes(), self.original_audio)

    def test_audio_unsatisfied_range_returns_total_size_without_recording(self) -> None:
        """验证越界和空后缀范围返回416而不泄漏完整音频。"""
        size = len(self.original_audio)
        for value in (f"bytes={size}-", f"bytes={size + 10}-{size + 20}", "bytes=-0"):
            with self.subTest(range=value):
                status, headers, body = self.request("GET", "/api/review/audio", headers={"Range": value})
                self.assertEqual(status, 416)
                self.assertEqual(headers["Content-Range"], f"bytes */{size}")
                self.assertNotEqual(body, self.original_audio)

    def test_audio_head_range_reports_partial_length_without_body(self) -> None:
        """验证带范围的HEAD返回播放器所需区间信息但不传音频正文。"""
        status, headers, body = self.request("HEAD", "/api/review/audio", headers={"Range": "bytes=4-19"})
        self.assertEqual(status, 206)
        self.assertEqual(headers["Content-Range"], f"bytes 4-19/{len(self.original_audio)}")
        self.assertEqual(headers["Content-Length"], "16")
        self.assertEqual(body, b"")

    def test_save_reload_and_export_keep_original_json_and_documents(self) -> None:
        """验证HTTP校对持久化后只导出校对副本，保留原结果及三种原稿。"""
        original_delivery = export_job(self.runtime, self.job_id)["delivery"]
        originals = {Path(record["path"]): Path(record["path"]).read_bytes()
                     for record in original_delivery["files"].values()}
        description = self.description()
        edited = [{"index": row["index"], "text": "人工修订第一句。" if number == 0 else row["text"],
                   "speaker_id": row["speaker_id"]}
                  for number, row in enumerate(description["sentences"])]
        status, _, body = self.request("POST", "/api/review/save", {
            "revision": description["revision"], "sentences": edited,
            "speakers": [{"id": 0, "name": "主持人"}, {"id": 1, "name": "嘉宾"}],
        })
        self.assertEqual(status, 200)
        saved = json.loads(body)
        self.assertTrue(saved["ok"])
        restored = self.description()
        self.assertEqual(restored["revision"], saved["revision"])
        self.assertGreater(restored["revision"], description["revision"])
        self.assertEqual(restored["sentences"][0]["text"], "人工修订第一句。")
        self.assertEqual(restored["sentences"][0]["original_text"], "原始第一句。")
        self.assertEqual(restored["sentences"][0]["original_speaker_id"], 0)
        self.assertEqual(restored["sentences"][0]["begin_ms"], description["sentences"][0]["begin_ms"])
        self.assertEqual(restored["speakers"], [{"id": 0, "name": "主持人"}, {"id": 1, "name": "嘉宾"}])
        destination = self.runtime.workspace / "用户选择的校验稿目录"
        destination.mkdir()
        with patch.object(self.server.session._picker, "select", return_value=destination) as picker:
            status, _, body = self.request("POST", "/api/review/export", {
                "revision": restored["revision"], "picker_id": "export-reviewed",
            })
        self.assertEqual(status, 200)
        exported = json.loads(body)
        self.assertFalse(exported["cancelled"])
        self.assertEqual(exported["delivery"]["status"], "COMPLETE")
        self.assertNotIn("revision", exported)
        self.assertNotIn("export_revision", exported)
        self.assertEqual(self.description()["revision"], restored["revision"])
        picker.assert_called_once_with(Path(self.config["document_directory"]), "export-reviewed", mode="directory")
        reviewed = {kind: Path(record["path"]) for kind, record in exported["delivery"]["files"].items()}
        self.assertEqual(set(reviewed), {"xlsx", "docx", "md"})
        self.assertTrue(set(reviewed.values()).isdisjoint(originals))
        self.assertEqual(reviewed, {kind: destination / f"{self.audio.stem}-reviewed-{self.job_id}.{kind}"
                                    for kind in ("xlsx", "docx", "md")})
        workbook = load_workbook(reviewed["xlsx"], read_only=True, data_only=False)
        try:
            self.assertEqual(workbook["转写明细"]["F4"].value, "人工修订第一句。")
            self.assertEqual(workbook["转写明细"]["E4"].value, "主持人")
        finally:
            workbook.close()
        with reviewed["docx"].open("rb") as stream:
            paragraphs = [paragraph.text for paragraph in Document(stream).paragraphs]
        self.assertIn("人工修订第一句。", paragraphs)
        self.assertIn("人工修订第一句。", reviewed["md"].read_text(encoding="utf-8"))
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)
        self.assertEqual(self.json_path.read_bytes(), self.original_json)
        self.assertEqual(self.config_path.read_bytes(), self.original_config)
        self.assertEqual(self.audio.read_bytes(), self.original_audio)
        with patch.object(self.server.session._picker, "select", return_value=None) as picker:
            status, _, body = self.request("POST", "/api/review/export", {
                "revision": restored["revision"], "picker_id": "cancel-next-export",
            })
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["cancelled"])
        picker.assert_called_once_with(Path(self.config["document_directory"]), "cancel-next-export", mode="directory")
        self.cloud.assert_not_called()

    def test_cancelled_export_does_not_create_documents_or_change_revision(self) -> None:
        """验证取消导出目录选择不生成文件，也不改写草稿版本或原结果。"""
        original_directory = Path(self.config["document_directory"])
        original_directory.mkdir(parents=True)
        description = self.description()
        files_before = {path: path.read_bytes() for path in self.runtime.workspace.rglob("*") if path.is_file()}
        with patch.object(self.server.session._picker, "select", return_value=None) as picker:
            status, _, body = self.request("POST", "/api/review/export", {
                "revision": description["revision"], "picker_id": "cancel-export",
            })
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["cancelled"])
        picker.assert_called_once_with(original_directory, "cancel-export", mode="directory")
        self.assertEqual(self.description()["revision"], description["revision"])
        self.assertNotIn("delivery", self.description())
        self.assertEqual({path: path.read_bytes() for path in self.runtime.workspace.rglob("*") if path.is_file()},
                         files_before)
        self.cloud.assert_not_called()

    def test_export_accepts_only_revision_and_picker_identifier(self) -> None:
        """验证导出先拒绝缺失或额外字段，不能从请求正文指定任意输出路径。"""
        revision = self.description()["revision"]
        for payload in ({"revision": revision},
                        {"revision": revision, "picker_id": "export", "directory": str(self.runtime.workspace)}):
            with self.subTest(payload=payload), \
                 patch.object(self.server.session._picker, "select") as picker:
                self.assertEqual(self.request("POST", "/api/review/export", payload)[0], 422)
                picker.assert_not_called()

    def test_original_sentence_fields_support_reset_through_save(self) -> None:
        """验证原句字段保持不变，并可通过已有保存入口恢复正文和说话人。"""
        initial = self.description()
        original = initial["sentences"][0]
        self.assertEqual(original["original_text"], original["text"])
        self.assertEqual(original["original_speaker_id"], original["speaker_id"])
        status, _, body = self.request("POST", "/api/review/save", {
            "revision": initial["revision"], "sentences": [
                {"index": original["index"], "text": "改动后再恢复。", "speaker_id": 1},
            ],
        })
        self.assertEqual(status, 200)
        changed = self.description()
        self.assertEqual(changed["sentences"][0]["original_text"], original["text"])
        self.assertEqual(changed["sentences"][0]["original_speaker_id"], original["speaker_id"])
        status, _, _ = self.request("POST", "/api/review/save", {
            "revision": json.loads(body)["revision"], "sentences": [
                {"index": original["index"], "text": original["original_text"],
                 "speaker_id": original["original_speaker_id"]},
            ],
        })
        self.assertEqual(status, 200)
        restored = self.description()["sentences"][0]
        self.assertEqual(restored["text"], restored["original_text"])
        self.assertEqual(restored["speaker_id"], restored["original_speaker_id"])
        self.assertEqual(self.json_path.read_bytes(), self.original_json)

    def test_stale_revision_cannot_overwrite_saved_edits(self) -> None:
        """验证旧标签页的保存被拒绝，已经保存的修订保持。"""
        description = self.description()
        index = description["sentences"][0]["index"]
        first = {"revision": description["revision"], "sentences": [
            {"index": index, "text": "先保存的人工内容。", "speaker_id": 0},
        ]}
        self.assertEqual(self.request("POST", "/api/review/save", first)[0], 200)
        stale = {**first, "sentences": [{"index": index, "text": "旧页面覆盖。", "speaker_id": 0}]}
        self.assertEqual(self.request("POST", "/api/review/save", stale)[0], 409)
        self.assertEqual(self.description()["sentences"][0]["text"], "先保存的人工内容。")

    def test_saved_edits_survive_service_restart_with_new_cookie(self) -> None:
        """验证关闭再打开后从磁盘恢复草稿，旧页面令牌不再读取新服务。"""
        description = self.description()
        status, _, body = self.request("POST", "/api/review/save", {
            "revision": description["revision"], "sentences": [
                {"index": 1, "text": "重新打开仍保留。", "speaker_id": 1},
            ],
        })
        self.assertEqual(status, 200)
        revision = json.loads(body)["revision"]
        previous_token = self.cookie.split("=", 1)[1]
        self.stop_server()
        self.start_server()
        restored = self.description()
        self.assertEqual(restored["revision"], revision)
        self.assertEqual(restored["sentences"][0]["text"], "重新打开仍保留。")
        self.assertEqual(restored["sentences"][0]["speaker_id"], 1)
        self.assertEqual(self.request("GET", "/api/review", authenticated=False,
                                      headers={"X-ASR-Token": previous_token})[0], 403)
        self.assertEqual(self.json_path.read_bytes(), self.original_json)

    def test_reselected_audio_must_match_original_content(self) -> None:
        """验证原文件移动后可重选相同内容，其他录音不能冒充原始来源。"""
        moved = self.audio.with_name("移动后的原录音.wav")
        self.audio.rename(moved)
        wrong = self.audio.with_name("不同录音.wav")
        content = bytearray(self.original_audio)
        content[-1] ^= 1
        wrong.write_bytes(content)
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=wrong):
            status, _, body = self.request("POST", "/api/review/select-audio", {"picker_id": "wrong-audio"})
        self.assertEqual(status, 422)
        self.assertIn("error", json.loads(body))
        self.assertEqual(self.config_path.read_bytes(), self.original_config)
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=moved):
            status, _, body = self.request("POST", "/api/review/select-audio", {"picker_id": "original-audio"})
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["cancelled"])
        self.assertTrue(json.loads(body)["audio"]["available"])
        status, _, body = self.request("GET", "/api/review/audio")
        self.assertEqual(status, 200)
        self.assertEqual(body, self.original_audio)
        self.assertEqual(self.config_path.read_bytes(), self.original_config)
        self.cloud.assert_not_called()

    def test_cancelled_audio_picker_leaves_current_recording_available(self) -> None:
        """验证取消重选不改变原录音和已保存修订。"""
        previous = self.description()
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=None):
            status, _, body = self.request("POST", "/api/review/select-audio", {"picker_id": "cancel-selection"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["cancelled"])
        self.assertEqual(self.description()["revision"], previous["revision"])
        self.assertEqual(self.request("GET", "/api/review/audio")[2], self.original_audio)

    def test_audio_reselection_does_not_advance_stale_page_revision(self) -> None:
        """验证旧页重选后不能取得新文字版本，后续旧姓名保存被拒绝。"""
        stale = self.description()
        status, _, _ = self.request("POST", "/api/review/save", {
            "revision": 0, "speakers": [{"id": 0, "name": "另一页已保存"}],
        })
        self.assertEqual(status, 200)
        before = self.description()
        with patch("asr_runtime.utils.path_picker.PathPicker.select", return_value=self.audio):
            status, _, body = self.request("POST", "/api/review/select-audio", {"picker_id": "reselect"})
        self.assertEqual(status, 200)
        self.assertNotIn("revision", json.loads(body))
        self.assertEqual(self.description(), before)
        status, _, body = self.request("POST", "/api/review/save", {
            "revision": stale["revision"], "speakers": stale["speakers"],
        })
        self.assertEqual(status, 409)
        self.assertIn("error", json.loads(body))
        self.assertEqual(self.description(), before)
        self.assertEqual(self.request("GET", "/api/review/audio")[2], self.original_audio)

    def test_close_service_releases_waiting_audio_selection(self) -> None:
        """验证结束回听服务会释放录音选择窗口，并保留原录音。"""
        entered = threading.Event()

        def choose(_initial, *, cancel_event, **_options):
            """等待服务收尾触发PathPicker关闭，不打开原生窗口。"""
            entered.set()
            if not cancel_event.wait(3):
                raise AssertionError("选择窗口未收到取消信号")
            return None

        with patch("asr_runtime.utils.path_picker.choose_path", side_effect=choose), \
             ThreadPoolExecutor(max_workers=1) as pool:
            selection = pool.submit(self.request, "POST", "/api/review/select-audio", {"picker_id": "waiting"})
            self.assertTrue(entered.wait(3))
            status, _, body = self.request("POST", "/api/review/close", {})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["closed"])
            status, _, body = selection.result(timeout=5)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["cancelled"])
        self.worker.join(timeout=5)
        self.assertFalse(self.worker.is_alive())
        self.assertTrue(self.server.session.description()["closed"])
        self.assertEqual(self.audio.read_bytes(), self.original_audio)

    def test_prepare_audio_serves_playable_copy_without_changing_recording(self) -> None:
        """验证浏览器兼容副本可经HTTP播放，重复准备复用副本并保留原文件。"""
        status, _, body = self.request("POST", "/api/review/prepare-audio", {})
        self.assertEqual(status, 200)
        audio = json.loads(body)["audio"]
        self.assertTrue(audio["available"])
        self.assertEqual(audio["kind"], "preview")
        status, headers, body = self.request("GET", "/api/review/audio")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "audio/mpeg")
        with av.open(io.BytesIO(body)) as media:
            self.assertGreater(sum(frame.samples for frame in media.decode(audio=0)), 0)
        with patch("asr_runtime.application.review.prepare_playback",
                   side_effect=AssertionError("已准备的播放副本不重复转换")):
            self.assertEqual(self.request("POST", "/api/review/prepare-audio", {})[0], 200)
        self.assertEqual(self.audio.read_bytes(), self.original_audio)
        self.assertEqual(self.json_path.read_bytes(), self.original_json)
        self.assertEqual(self.config_path.read_bytes(), self.original_config)
        self.cloud.assert_not_called()

    def test_reopened_review_serves_existing_playback_when_original_is_unavailable(self) -> None:
        """验证重开HTTP页面直接提供已有播放副本，不要求再次选择原录音或转码。"""
        self.request("POST", "/api/review/save", {"revision": 0, "sentences": [
            {"index": 1, "text": "已保存的校对", "speaker_id": 0}]})
        self.assertEqual(self.request("POST", "/api/review/prepare-audio", {})[0], 200)
        playback = (self.job_root / "review/playback.mp3").read_bytes()
        draft = (self.job_root / "review/draft.json").read_bytes()
        self.stop_server()
        moved = self.audio.with_name("moved.wav")
        self.audio.rename(moved)
        with patch("asr_runtime.application.review.prepare_playback", side_effect=AssertionError("重开不转码")):
            self.start_server()
            self.assertEqual(self.description()["audio"]["kind"], "preview")
            status, headers, body = self.request("GET", "/api/review/audio", headers={"Range": "bytes=0-31"})
            self.assertEqual(status, 206)
            self.assertEqual(headers["Content-Type"], "audio/mpeg")
            self.assertEqual(body, playback[:32])
        self.assertEqual(self.description()["revision"], 1)
        self.assertEqual((self.job_root / "review/draft.json").read_bytes(), draft)
        self.assertEqual(moved.read_bytes(), self.original_audio)
        self.assertEqual(self.json_path.read_bytes(), self.original_json)
        self.assertEqual(self.config_path.read_bytes(), self.original_config)
        self.cloud.assert_not_called()

    def test_close_command_stops_server_without_altering_originals(self) -> None:
        """验证本机关闭入口结束回听服务，原任务和结果仍可保留。"""
        report = review_web.control_review(self.runtime, self.job_id)
        self.assertTrue(report["closed"])
        self.assertEqual(report["job_id"], self.job_id)
        self.worker.join(timeout=5)
        self.assertFalse(self.worker.is_alive())
        self.server.server_close()
        self.assertFalse((self.job_root / "review/connection.json").exists())
        self.assertTrue(review_web.control_review(self.runtime, self.job_id)["closed"])
        self.assertEqual(self.json_path.read_bytes(), self.original_json)
        self.assertEqual(self.config_path.read_bytes(), self.original_config)
        self.cloud.assert_not_called()

    def test_reopening_active_job_reuses_server_without_exposing_token(self) -> None:
        """验证同一任务再次打开时复用原服务，回执不包含私有连接令牌。"""
        output = io.StringIO()
        with patch.object(review_web, "create_review_server", side_effect=AssertionError("不应重复创建服务")), \
             patch.object(review_web.webbrowser, "open") as launch, redirect_stdout(output):
            review_web.serve_review(self.runtime, self.job_id, open_browser=False)
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt["event"], "listening")
        self.assertEqual(receipt["url"], self.origin + "/review")
        self.assertTrue(receipt["reused"])
        self.assertEqual(receipt["browser_request"], "skipped")
        self.assertNotIn(self.cookie.split("=", 1)[1], output.getvalue())
        self.assertTrue(self.worker.is_alive())
        self.assertEqual(self.description()["job_id"], self.job_id)
        launch.assert_not_called()


class ReviewCommandTests(ReviewFixture):
    def test_review_command_forwards_job_port_and_browser_choice(self) -> None:
        """验证命令行按用户指定任务与端口启动回听，并保留不开浏览器选项。"""
        with patch.object(review_web, "serve_review") as serve:
            code = main(["--workspace", str(self.runtime.workspace), "review", "--job", self.job_id,
                         "--port", "12345", "--no-browser"])
        self.assertEqual(code, 0)
        serve.assert_called_once()
        runtime, job_id = serve.call_args.args
        self.assertEqual(runtime.workspace, self.runtime.workspace)
        self.assertEqual(runtime.skill_root, SKILL_ROOT)
        self.assertEqual(job_id, self.job_id)
        self.assertEqual(serve.call_args.kwargs, {"port": 12345, "open_browser": False})
        self.cloud.assert_not_called()

    def test_review_close_command_returns_control_result(self) -> None:
        """验证关闭命令只操作指定任务的本机服务并返回原回执。"""
        expected = {"ok": True, "closed": True, "job_id": self.job_id}
        output = io.StringIO()
        with patch.object(review_web, "control_review", return_value=expected) as close, redirect_stdout(output):
            code = main(["--workspace", str(self.runtime.workspace), "review-close", "--job", self.job_id])
        self.assertEqual(code, 0)
        close.assert_called_once()
        runtime, job_id = close.call_args.args
        self.assertEqual(runtime.workspace, self.runtime.workspace)
        self.assertEqual(runtime.skill_root, SKILL_ROOT)
        self.assertEqual(job_id, self.job_id)
        self.assertEqual(json.loads(output.getvalue()), expected)
        self.cloud.assert_not_called()
