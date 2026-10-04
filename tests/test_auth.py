import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from asr_runtime.utils.auth import api_key_status, bailian_environment, read_api_key, write_api_key
from asr_runtime.utils.environment import SetupError
from tests.support import RuntimeTestCase


class ApiKeyTests(RuntimeTestCase):
    def setUp(self):
        """创建用于凭据写入的会话暂存位置。"""
        super().setUp()
        self.staging = self.runtime.path(".state/sessions/" + "a" * 32)

    def test_key_is_read_only_from_the_private_runtime_directory(self):
        """验证凭据仅从当前工作区的私有运行目录读取。"""
        for root in (self.runtime.workspace, self.runtime.skill_root):
            (root / ".env").write_text("DASHSCOPE_API_KEY=unrelated-synthetic-key\n", encoding="utf-8")
        self.assertFalse(api_key_status(self.runtime)["configured"])
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=current-synthetic-key\n", encoding="utf-8")
        self.assertEqual(read_api_key(self.runtime), "current-synthetic-key")

    def test_missing_and_empty_key_are_local_errors(self):
        """验证缺失或空Key返回配置缺失状态。"""
        self.assertFalse(api_key_status(self.runtime)["configured"])
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=\n", encoding="utf-8")
        self.assertFalse(api_key_status(self.runtime)["configured"])

    def test_status_never_returns_key_or_claims_online_verification(self):
        """验证状态报告使用本地配置标记并隐藏密钥。"""
        self.runtime.path(".env").write_text('DASHSCOPE_API_KEY="synthetic-secret"\n', encoding="utf-8")
        status = api_key_status(self.runtime)
        self.assertTrue(status["configured"])
        self.assertFalse(status["verified_online"])
        self.assertNotIn("synthetic-secret", json.dumps(status))

    def test_key_only_reaches_explicit_api_key_environment(self):
        """验证指定Key与控制台模式的凭据环境隔离。"""
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=synthetic-secret\n", encoding="utf-8")
        self.assertNotIn("DASHSCOPE_API_KEY", bailian_environment(self.runtime, "console"))
        self.assertEqual(bailian_environment(self.runtime, "api_key")["DASHSCOPE_API_KEY"], "synthetic-secret")

    def test_does_not_use_process_key_or_expand_variables(self):
        """验证.env值按原文读取并保持进程环境。"""
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=${UNRELATED_SECRET}\n", encoding="utf-8")
        with patch.dict(os.environ, {"UNRELATED_SECRET": "outside-secret", "DASHSCOPE_API_KEY": "outside-key"}):
            self.assertEqual(read_api_key(self.runtime), "${UNRELATED_SECRET}")
            self.assertEqual(os.environ["DASHSCOPE_API_KEY"], "outside-key")

    def test_console_does_not_read_dotenv(self):
        """验证控制台模式使用独立凭据环境。"""
        with patch("asr_runtime.utils.auth.read_api_key", side_effect=AssertionError("must not read")):
            bailian_environment(self.runtime, "console")

    def test_multiline_key_is_rejected_without_echo(self):
        """验证含换行Key返回脱敏配置错误。"""
        self.runtime.path(".env").write_text('DASHSCOPE_API_KEY="synthetic\nsecret"\n', encoding="utf-8")
        report = api_key_status(self.runtime)
        self.assertFalse(report["configured"])
        self.assertNotIn("synthetic", json.dumps(report))

    def test_unknown_mode_is_rejected(self):
        """验证拒绝未知鉴权方式。"""
        with self.assertRaises(SetupError):
            bailian_environment(self.runtime, "unknown")

    def test_page_read_can_return_empty_while_execution_requires_key(self):
        """验证未填写凭据时页面可编辑，而执行仍要求有效Key。"""
        self.assertEqual(read_api_key(self.runtime, required=False), "")
        with self.assertRaises(SetupError):
            read_api_key(self.runtime)

    def test_save_preserves_other_settings_and_roundtrips_literal_key(self):
        """验证修改Key保留注释和其他设置，并按原文保存特殊字符。"""
        path = self.runtime.path(".env")
        path.write_text("# local settings\nOTHER_VALUE=keep\nDASHSCOPE_API_KEY=old-synthetic-key\n", encoding="utf-8")
        write_api_key(self.runtime, "  synthetic-${VALUE}-'quoted'  ", staging_directory=self.staging)
        text = path.read_text(encoding="utf-8")
        self.assertIn("# local settings", text)
        self.assertIn("OTHER_VALUE=keep", text)
        self.assertNotIn("old-synthetic-key", text)
        self.assertEqual(read_api_key(self.runtime), "synthetic-${VALUE}-'quoted'")
        self.assertFalse((self.runtime.skill_root / ".env").exists())
        self.assertFalse((self.runtime.workspace / ".env").exists())
        self.assertEqual(list(self.staging.iterdir()), [])

    def test_invalid_save_keeps_previous_key_and_hides_input(self):
        """验证无效输入不覆盖已有Key，错误说明不包含输入。"""
        write_api_key(self.runtime, "previous-synthetic-key", staging_directory=self.staging)
        before = self.runtime.path(".env").read_bytes()
        for value in (None, "", "synthetic secret", "synthetic\nsecret"):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(SetupError) as error:
                write_api_key(self.runtime, value, staging_directory=self.staging)
            self.assertNotIn("synthetic", str(error.exception))
            self.assertEqual(self.runtime.path(".env").read_bytes(), before)

    def test_dotenv_temporary_file_belongs_to_the_editing_session(self):
        """验证第三方凭据临时文件写入会话目录并在成功后清理。"""
        with patch("dotenv.main.tempfile.NamedTemporaryFile", wraps=tempfile.NamedTemporaryFile) as temporary:
            write_api_key(self.runtime, "synthetic-key", staging_directory=self.staging)
        self.assertEqual(Path(temporary.call_args.kwargs["dir"]), self.staging)
        self.assertEqual(read_api_key(self.runtime), "synthetic-key")
        self.assertEqual(list(self.staging.iterdir()), [])
        self.assertFalse(list(self.runtime.root.glob(".tmp_*")))

    def test_failed_key_publication_preserves_previous_key_and_cleans_working_copy(self):
        """验证最终替换失败时保留原Key并删除会话工作副本。"""
        destination = self.runtime.path(".env")
        destination.write_bytes(b"# original\nDASHSCOPE_API_KEY=synthetic-original\n")
        original = destination.read_bytes()
        with patch.object(Path, "replace", side_effect=PermissionError("synthetic locked target")), \
                self.assertRaises(PermissionError):
            write_api_key(self.runtime, "synthetic-new", staging_directory=self.staging)
        self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(list(self.staging.iterdir()), [])

    def test_dotenv_error_preserves_previous_key_and_cleans_working_copy(self):
        """验证凭据编码或写入失败时保留正式文件并回收工作副本。"""
        destination = self.runtime.path(".env")
        destination.write_bytes(b"DASHSCOPE_API_KEY=synthetic-original\n")
        original = destination.read_bytes()
        with patch("dotenv.set_key", side_effect=OSError("synthetic write failure")), \
                self.assertRaises(OSError):
            write_api_key(self.runtime, "synthetic-new", staging_directory=self.staging)
        self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(list(self.staging.iterdir()), [])
