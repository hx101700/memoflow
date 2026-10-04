"""验证编辑会话的预览、一次性交接、截止时间和输入保留。"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from asr_runtime.application.rules import ValidationError
from asr_runtime.application.inputs import validate_audio
from asr_runtime.application.session import Session, SESSION_LIFETIME_SECONDS
from asr_runtime.application.recovery import finish_session
from asr_runtime.application.transcription import job_status
from asr_runtime.utils.bailian import check_recognition_command
from asr_runtime.utils.job_files import publish_config
from asr_runtime.utils.session_files import read_receipt
from tests.test_session import WebFixture


class SessionHandoffTests(WebFixture):
    def setUp(self):
        """准备可控制时钟的编辑会话及带增强内容的合成表单。"""
        super().setUp()
        self.now = 1_800_000_000.0
        self.session = Session(self.runtime, clock=lambda: self.now)
        self.addCleanup(self.session.cleanup)
        self.form = {**self.payload_for(self.session), "enhancement_mode": "both",
                     "hotword_rows": [{"text": "Kubernetes", "weight": "4"}],
                     "context": "录音讨论 Kubernetes。"}

    def show_preview(self):
        """校验表单并登记页面已经展示的预览版本。"""
        preview = self.session.validate(self.form)
        self.session.preview_ready(preview["validation_id"])
        return preview

    def test_only_acknowledged_preview_can_create_a_job(self):
        """验证填写和未展示的预览都不能被接管，也不产生任务编号。"""
        with self.assertRaisesRegex(ValidationError, "进入预览页"):
            self.session.confirm()
        preview = self.session.validate(self.form)
        self.assertNotIn("job_id", preview)
        self.assertNotIn("job_id", self.session.draft["config"])
        with self.assertRaisesRegex(ValidationError, "进入预览页"):
            self.session.confirm()
        self.assertFalse(self.runtime.path(".state/jobs").exists())
        self.session.preview_ready(preview["validation_id"])
        receipt = self.session.confirm()
        self.assertEqual(receipt["session_id"], self.session.session_id)
        self.assertEqual(read_receipt(self.runtime, self.session.session_id), receipt)
        self.assertEqual(self.session.description()["phase"], "handed_off")
        self.assertEqual(job_status(self.runtime, receipt["job_id"])["status"], "CONFIGURED")

    def test_oversized_valid_hotwords_keep_preview_editable_before_handoff(self):
        """验证合法大词表超出命令长度时保留预览，缩短后同会话可交接。"""
        self.form["hotword_rows"] = [
            {"text": "术语" + str(index).zfill(4) + "甲" * 9, "weight": 4}
            for index in range(2000)
        ]
        preview = self.show_preview()
        self.assertEqual(preview["summary"]["enhancement"]["count"], 2000)
        with patch("asr_runtime.utils.bailian.installed_bl_version", side_effect=AssertionError("交接不检查BL安装")), \
                patch("asr_runtime.utils.auth.read_api_key", side_effect=AssertionError("交接不读取Key")), \
                patch("asr_runtime.utils.bailian.subprocess.Popen", side_effect=AssertionError("交接不启动BL")):
            with self.assertRaises(ValidationError) as caught:
                self.session.confirm()
            self.assertEqual(caught.exception.field, "form")
            self.assertIn("32767", caught.exception.message["zh"])
            self.assertIn("exceeding the Windows limit", caught.exception.message["en"])
            self.assertEqual(self.session.description()["phase"], "preview")
            self.assertEqual(self.session.draft["id"], preview["validation_id"])
            self.assertIsNone(self.session.receipt)
            self.assertIsNone(read_receipt(self.runtime, self.session.session_id))
            self.assertFalse(self.session.terminal_event.is_set())
            self.assertFalse(self.runtime.path(".state/jobs").exists())
            self.session.edit(preview["validation_id"])
            self.form["hotword_rows"] = self.form["hotword_rows"][:1]
            self.show_preview()
            receipt = self.session.confirm()
        self.assertEqual(receipt["session_id"], self.session.session_id)
        self.assertEqual(len(list(self.runtime.path(".state/jobs").iterdir())), 1)
        self.assertFalse(self.runtime.path(f'.state/jobs/{receipt["job_id"]}/execution').exists())

    def test_handoff_length_check_uses_actual_original_or_mono_paths(self):
        """验证长度检查使用正式任务编号及实际原音频或混音副本的路径。"""
        for diarization in (False, True):
            with self.subTest(diarization=diarization):
                session = Session(self.runtime)
                self.addCleanup(session.cleanup)
                form = {**self.payload_for(session), "diarization_enabled": diarization}
                preview = session.validate(form)
                session.preview_ready(preview["validation_id"])
                with patch("asr_runtime.application.session.check_recognition_command", wraps=check_recognition_command) as check:
                    receipt = session.confirm()
                arguments = check.call_args.args[1]
                directory = self.runtime.path(f'.state/jobs/{receipt["job_id"]}')
                expected_source = directory / "execution/mono.flac" if diarization else self.audio
                self.assertEqual(arguments[arguments.index("--url") + 1], str(expected_source))
                self.assertEqual(arguments[arguments.index("--out") + 1],
                                 str(Path(receipt["json_directory"]) / "transcription.json"))
                self.assertFalse((directory / "execution").exists())

    def test_return_to_edit_invalidates_old_preview_without_creating_jobs(self):
        """验证多次返回修改保持同一会话，最终交接只生成一个任务。"""
        for text in ("第一次修改", "第二次修改"):
            preview = self.show_preview()
            restored = self.session.edit(preview["validation_id"])
            self.assertEqual(restored["configuration"], self.form)
            self.assertEqual(restored["audio"]["audio_id"], self.form["audio_id"])
            self.assertEqual(restored["audio"]["path"], str(self.audio))
            self.assertEqual(self.session.description()["phase"], "editing")
            self.assertIsNone(self.session.description()["preview"])
            self.assertFalse(self.runtime.path(".state/jobs").exists())
            with self.assertRaises(ValidationError):
                self.session.preview_ready(preview["validation_id"])
            with self.assertRaises(ValidationError):
                self.session.confirm()
            self.form["context"] = text
        self.show_preview()
        receipt = self.session.confirm()
        config = json.loads(Path(receipt["config_path"]).read_text(encoding="utf-8"))
        self.assertEqual(config["enhancement"]["context"], "第二次修改")
        self.assertEqual(len(list(self.runtime.path(".state/jobs").iterdir())), 1)

    def test_refresh_restores_current_preview_without_exposing_key(self):
        """验证刷新可读取预览输入，返回的数据与服务端快照相互独立。"""
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=synthetic-secret", encoding="utf-8")
        preview = self.show_preview()
        description = self.session.description()
        self.assertEqual(description["preview"]["validation_id"], preview["validation_id"])
        self.assertEqual(description["preview"]["configuration"], self.form)
        self.assertNotIn("synthetic-secret", json.dumps(description))
        description["preview"]["configuration"]["hotword_rows"][0]["text"] = "outside change"
        self.form["hotword_rows"][0]["text"] = "later local edit"
        receipt = self.session.confirm()
        config = json.loads(Path(receipt["config_path"]).read_text(encoding="utf-8"))
        self.assertEqual(config["enhancement"]["hotwords"]["vocabulary"], {"Kubernetes": 4})

    def test_preview_rejects_mutation_until_returned_to_edit(self):
        """验证预览期间只接受返回修改，不能悄悄替换已展示内容。"""
        self.show_preview()
        actions = (lambda: self.session.validate(self.form),
                   lambda: self.session.save_api_key("synthetic-key"),
                   lambda: self.session.select_audio("preview-audio"),
                   lambda: self.session.select_directory("json", "preview-picker"))
        for action in actions:
            with self.assertRaisesRegex(ValidationError, "返回修改"):
                action()
        self.assertFalse(self.runtime.path(".state/jobs").exists())

    def test_confirm_and_return_to_edit_have_one_winner(self):
        """验证同一预览的交接与返回修改竞争时只有一方成功。"""
        preview = self.show_preview()
        barrier = threading.Barrier(2)

        def confirm():
            """与编辑请求同步发起交接并报告是否成功。"""
            barrier.wait(timeout=5)
            try:
                self.session.confirm()
                return True
            except ValidationError:
                return False

        def edit():
            """与确认请求同步退出预览并报告是否成功。"""
            barrier.wait(timeout=5)
            try:
                self.session.edit(preview["validation_id"])
                return True
            except ValidationError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            confirmed = pool.submit(confirm)
            edited = pool.submit(edit)
            self.assertEqual(sum((confirmed.result(timeout=5), edited.result(timeout=5))), 1)

    def test_expiry_uses_fixed_deadline_and_preserves_original_inputs(self):
        """验证操作不延长时限，到期收尾保留原音频和Key。"""
        deadline = self.session.deadline
        self.session.save_api_key("synthetic-saved-key")
        self.now += SESSION_LIFETIME_SECONDS - 1
        self.show_preview()
        self.assertEqual(self.session.deadline, deadline)
        self.assertEqual(self.session.remaining_seconds(), 1)
        self.assertIsNone(self.session.expire())
        self.now += 1
        result = self.session.expire()
        self.assertEqual(result, {"state": "expired", "receipt": None})
        self.assertTrue(self.session.terminal_event.is_set())
        with self.assertRaisesRegex(ValidationError, "失效"):
            self.session.confirm()
        self.session.cleanup()
        finish_session(self.runtime, self.session.session_id)
        self.assertTrue(self.audio.is_file())
        self.assertTrue(self.audio.exists())
        self.assertIn("synthetic-saved-key", self.runtime.path(".env").read_text(encoding="utf-8"))
        self.assertFalse(self.runtime.path(".state/jobs").exists())

    def test_confirm_checks_deadline_even_when_timer_has_not_run(self):
        """验证截止时间之后的确认由状态锁直接拒绝，不依赖计时器先执行。"""
        self.show_preview()
        self.now = self.session.deadline
        barrier = threading.Barrier(2)

        def confirm():
            """在截止点尝试确认并保存可观察的拒绝结果。"""
            barrier.wait(timeout=5)
            with self.assertRaisesRegex(ValidationError, "失效"):
                self.session.confirm()

        def expire():
            """在相同截止点触发计时器操作。"""
            barrier.wait(timeout=5)
            return self.session.expire()

        with ThreadPoolExecutor(max_workers=2) as pool:
            confirming = pool.submit(confirm)
            expiring = pool.submit(expire)
            confirming.result(timeout=5)
            self.assertEqual(expiring.result(timeout=5)["state"], "expired")
        self.assertFalse(self.runtime.path(".state/jobs").exists())

    def test_validation_crossing_deadline_cannot_publish_a_new_preview(self):
        """验证音频检查跨过截止时间后结束会话，停止发布迟到的预览。"""
        def finish_at_deadline(*args):
            """完成实际媒体校验后将受控时钟推进到截止点。"""
            audio = validate_audio(*args)
            self.now = self.session.deadline
            return audio

        with patch("asr_runtime.application.session.validate_audio", side_effect=finish_at_deadline):
            with self.assertRaisesRegex(ValidationError, "失效"):
                self.session.validate(self.form)
        self.assertIsNone(self.session.draft)
        self.assertEqual(self.session.terminal_result(), {"state": "expired", "receipt": None})

    def test_handoff_survives_deadline_and_service_cleanup(self):
        """验证交接后的任务不受网页到期或关闭影响，重复确认找回同一编号。"""
        preview = self.show_preview()
        receipt = self.session.confirm()
        self.now += SESSION_LIFETIME_SECONDS * 2
        self.assertEqual(self.session.expire(), {"state": "handed_off", "receipt": receipt})
        self.assertEqual(self.session.cancel(), {"state": "handed_off", "receipt": receipt})
        self.session.cleanup()
        finish_session(self.runtime, self.session.session_id)
        self.assertEqual(self.session.confirm(), receipt)
        self.assertEqual(read_receipt(self.runtime, self.session.session_id), receipt)
        config = json.loads(Path(receipt["config_path"]).read_text(encoding="utf-8"))
        self.assertTrue(Path(config["audio"]["path"]).exists())
        with self.assertRaises(ValidationError):
            self.session.edit(preview["validation_id"])

    def test_cancel_creates_no_job_and_never_changes_completed_handoff(self):
        """验证取消结束编辑但不能撤回已交接任务。"""
        self.show_preview()
        self.assertEqual(self.session.cancel(), {"state": "cancelled", "receipt": None})
        self.assertTrue(self.session.terminal_event.is_set())
        self.session.cleanup()
        finish_session(self.runtime, self.session.session_id)
        self.assertTrue(self.audio.is_file())
        self.assertFalse(self.runtime.path(".state/jobs").exists())
        with self.assertRaises(ValidationError):
            self.session.confirm()

    def test_receipt_write_failure_creates_no_job_and_can_retry(self):
        """验证回执写入失败时没有任务，之后明确重试可完成一次交接。"""
        self.show_preview()
        with patch("asr_runtime.application.session.write_receipt", side_effect=OSError("synthetic write error")):
            with self.assertRaises(OSError):
                self.session.confirm()
        self.assertFalse(self.session.terminal_event.is_set())
        self.assertIsNone(read_receipt(self.runtime, self.session.session_id))
        self.assertFalse(self.runtime.path(".state/jobs").exists())
        receipt = self.session.confirm()
        self.assertEqual(len(list(self.runtime.path(".state/jobs").iterdir())), 1)
        self.assertEqual(self.session.confirm(), receipt)
        self.assertEqual(read_receipt(self.runtime, self.session.session_id), receipt)

    def test_failed_config_publication_never_activates_candidate_receipt(self):
        """验证配置尚未原子发布时回执无效，失败会话仍按原定时间结束。"""
        preview = self.show_preview()
        replace = Path.replace

        def fail_config_publish(path, target):
            """模拟配置最终发布失败。"""
            if path.name == "config.json.tmp":
                raise OSError("synthetic config publication failure")
            return replace(path, target)

        with patch.object(Path, "replace", fail_config_publish):
            with self.assertRaises(OSError):
                self.session.confirm()
        self.assertIsNone(read_receipt(self.runtime, self.session.session_id))
        self.assertFalse(list(self.runtime.path(".state/jobs").iterdir()))
        self.assertFalse(self.session.terminal_event.is_set())
        self.assertEqual(self.session.edit(preview["validation_id"])["configuration"], self.form)
        self.now = self.session.deadline
        self.assertEqual(self.session.expire(), {"state": "expired", "receipt": None})
        self.session.cleanup()
        finish_session(self.runtime, self.session.session_id)
        self.assertTrue(self.audio.is_file())

    def test_successful_publication_can_recover_receipt_before_http_returns(self):
        """验证配置文件成为可见提交点后，代码已可恢复同一交接回执。"""
        self.show_preview()
        recovered = []

        def observe_publication(runtime, config):
            """观察配置发布前后同一个候选回执的可用性。"""
            self.assertIsNone(read_receipt(runtime, self.session.session_id))
            destination = publish_config(runtime, config)
            recovered.append(read_receipt(runtime, self.session.session_id))
            return destination

        with patch("asr_runtime.application.session.publish_config", side_effect=observe_publication):
            receipt = self.session.confirm()
        self.assertEqual(recovered, [receipt])

    def test_cleanup_after_receipt_failure_wakes_terminal_subscriber(self):
        """验证回执写盘失败后正常关闭唤醒事件读取者并保留用户原文件。"""
        self.show_preview()
        with patch("asr_runtime.application.session.write_receipt", side_effect=OSError("synthetic write error")):
            with self.assertRaises(OSError):
                self.session.confirm()
        self.session.cleanup()
        finish_session(self.runtime, self.session.session_id)
        self.assertTrue(self.session.terminal_event.is_set())
        self.assertEqual(self.session.terminal_result(), {"state": "cancelled", "receipt": None})
        self.assertTrue(self.audio.is_file())
