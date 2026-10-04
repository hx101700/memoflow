"""验证BL适配器的参数、进程生命周期和错误报告。"""

import io
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from asr_runtime import BAILIAN_VERSION, MODEL
from asr_runtime.utils.auth import read_api_key
from asr_runtime.utils.bailian import BailianFailure, PreparedCommand, check_command_length, check_recognition_command, console_status, explain_cli_error, login_console, prepare_command, redact_message, run_recognition
from asr_runtime.utils.environment import SetupError, find_node
from asr_runtime.utils.bailian import bl_command
from tests.support import RuntimeTestCase, CONTRACT_BL_ENTRY, contract_runtime


_REAL_POPEN = subprocess.Popen


class BailianTests(RuntimeTestCase):
    def setUp(self):
        """准备项目内BL入口、参数和进程替身。"""
        super().setUp()
        self.runtime.prepare()
        # 仅创建假入口供命令构造使用，所有BL进程均由测试替身接管。
        self.runtime.bl_entry.parent.mkdir(parents=True)
        self.runtime.bl_entry.touch()
        manifest = self.runtime.bl_entry.parent.parent / "package.json"
        manifest.write_text(json.dumps({"version": BAILIAN_VERSION}), encoding="utf-8")
        self.key = "asr-transcription-synthetic-process-key"
        self.runtime.path(".env").write_text(f"DASHSCOPE_API_KEY={self.key}\n", encoding="utf-8")
        self.node = self.runtime.root / "node.exe"
        self.arguments = [
            "speech", "recognize", "--model", MODEL,
            "--url", str(self.runtime.root / "本地 audio.wav"),
            "--out", str(self.runtime.root / "result.json"),
            "--base-url", "https://dashscope.aliyuncs.com", "--config", "default",
            "--output", "json", "--diarization", "--speaker-count", "3",
            "--context", "本地合成上下文", "--vocabulary", '{"合成词":4}',
        ]
        self.process = Mock()
        self.process.returncode = 0
        self.process.communicate.return_value = (None, "")
        node_patch = patch("asr_runtime.utils.bailian.find_node", return_value=self.node)
        process_patch = patch("asr_runtime.utils.bailian.subprocess.Popen", return_value=self.process)
        node_patch.start()
        self.popen = process_patch.start()
        self.addCleanup(node_patch.stop)
        self.addCleanup(process_patch.stop)

    def test_recognition_uses_local_entry_and_public_arguments_without_shell(self):
        """验证识别通过本地CLI入口及参数数组启动。"""
        command = prepare_command(self.runtime, self.arguments, "api_key")
        run_recognition(self.runtime, command, [])
        self.popen.assert_called_once()
        argv = self.popen.call_args.args[0]
        self.assertEqual(argv, (str(self.node), str(self.runtime.bl_entry), *self.arguments, "--quiet"))
        self.assertNotIn("--file", argv)
        self.assertNotIn("--async", argv)
        self.assertFalse(self.popen.call_args.kwargs["shell"])
        self.assertEqual(self.popen.call_args.kwargs["cwd"], self.runtime.workspace)

    def test_api_key_only_reaches_child_environment_and_transcript_is_not_captured(self):
        """验证Key注入识别子进程并配置输出通道。"""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "unrelated-synthetic-key",
                                     "NODE_OPTIONS": "--require unwanted.cjs"}):
            command = prepare_command(self.runtime, self.arguments, "api_key")
            result = run_recognition(self.runtime, command, [])
        self.assertIsNone(result)
        kwargs = self.popen.call_args.kwargs
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stderr"], subprocess.PIPE)
        self.assertEqual(kwargs["env"]["DASHSCOPE_API_KEY"], self.key)
        self.assertEqual(kwargs["env"]["DO_NOT_TRACK"], "1")
        self.assertNotIn("NODE_OPTIONS", kwargs["env"])
        self.assertNotIn(self.key, repr(self.popen.call_args.args))

    def test_console_mode_does_not_inherit_api_key(self):
        """验证控制台模式使用隔离的子进程环境。"""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "unrelated-synthetic-key"}):
            command = prepare_command(self.runtime, self.arguments, "console")
            run_recognition(self.runtime, command, [])
        self.assertNotIn("DASHSCOPE_API_KEY", self.popen.call_args.kwargs["env"])
        self.assertEqual(self.popen.call_args.kwargs["env"]["BAILIAN_CONFIG_DIR"],
                         str(self.runtime.path(".state/bailian")))

    def test_prepare_and_run_use_one_checked_snapshot_without_rereading_secrets(self):
        """验证识别执行复用一次准备的参数和凭据快照。"""
        with patch("asr_runtime.utils.auth.read_api_key", wraps=read_api_key) as read_key, \
             patch("asr_runtime.utils.bailian.bl_command", wraps=bl_command) as build_command, \
             patch("asr_runtime.utils.bailian.check_command_length", wraps=check_command_length) as check_length:
            command = prepare_command(self.runtime, self.arguments, "api_key")
            self.assertIsInstance(command, PreparedCommand)
            self.assertIsInstance(command.argv, tuple)
            original_context = self.arguments[self.arguments.index("--context") + 1]
            # 准备后源配置变化，执行必须使用已经校验过的参数与凭据快照。
            self.arguments[self.arguments.index("--context") + 1] = "准备后的合成变更"
            self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=changed-synthetic-key\n", encoding="utf-8")
            run_recognition(self.runtime, command, [])
        read_key.assert_called_once_with(self.runtime)
        build_command.assert_called_once()
        check_length.assert_called_once()
        self.popen.assert_called_once()
        self.assertIs(self.popen.call_args.args[0], command.argv)
        self.assertIs(self.popen.call_args.kwargs["env"], command.env)
        self.assertEqual(command.env["DASHSCOPE_API_KEY"], self.key)
        self.assertEqual(command.argv[command.argv.index("--context") + 1], original_context)
        for private in (self.key, original_context, "合成词", str(self.runtime.root)):
            self.assertNotIn(private, repr(command))

    def test_command_length_includes_terminating_nul(self):
        """验证命令长度包含末尾NUL字符。"""
        check_command_length(["a" * 32766])
        with self.assertRaisesRegex(SetupError, "32768"):
            check_command_length(["a" * 32767])

    def test_handoff_length_check_matches_execution_argv_without_credentials_or_installation(self):
        """验证交接检查与执行共用完整参数，交接阶段只检查命令长度。"""
        with patch("asr_runtime.utils.bailian.installed_bl_version", side_effect=AssertionError("不能查询安装")), \
                patch("asr_runtime.utils.auth.read_api_key", side_effect=AssertionError("不能读取凭据")), \
                patch("asr_runtime.utils.bailian.check_command_length", wraps=check_command_length) as check:
            check_recognition_command(self.runtime, self.arguments)
        checked_argv = check.call_args.args[0]
        prepared = prepare_command(self.runtime, self.arguments, "api_key")
        self.assertEqual(tuple(checked_argv), prepared.argv)
        self.popen.assert_not_called()

    def test_command_length_counts_surrogate_pairs(self):
        """验证命令长度按UTF-16计算代理对。"""
        check_command_length(["😀" * 16383])
        with self.assertRaises(SetupError):
            check_command_length(["😀" * 16383 + "a"])

    def test_command_length_includes_windows_quotes_and_escaped_trailing_slash(self):
        # 空格触发外层引号，末尾反斜线在结束引号前必须翻倍。
        """验证命令长度包含Windows引号和末尾反斜杠。"""
        argument = "prefix " + "a" * 32755 + "\\"
        self.assertEqual(len(subprocess.list2cmdline([argument])), 32766)
        check_command_length([argument])
        with self.assertRaises(SetupError):
            check_command_length([argument + "\\"])

    def test_oversized_command_stops_before_loading_credentials_or_starting_bl(self):
        """验证超长命令在读凭据或启动BL前停止。"""
        with patch("asr_runtime.utils.bailian.bailian_environment") as environment:
            with self.assertRaises(SetupError):
                prepare_command(self.runtime, [*self.arguments, "--context", "a" * 32767], "api_key")
        self.popen.assert_not_called()
        environment.assert_not_called()

    def test_process_start_failure_is_distinct_from_unknown_cloud_result(self):
        """验证启动失败与已启动后的云端未知结果分开。"""
        self.popen.side_effect = OSError("synthetic process start failure")
        command = prepare_command(self.runtime, self.arguments, "api_key")
        with self.assertRaises(BailianFailure) as caught:
            run_recognition(self.runtime, command, [])
        self.assertFalse(caught.exception.started)
        self.assertEqual(caught.exception.report["code"], "LOCAL_PROCESS_START_FAILED")
        self.popen.assert_called_once()

    def test_failed_recognition_is_not_retried_and_redacts_key_from_error(self):
        """验证识别失败返回脱敏错误且调用次数为一。"""
        self.process.returncode = 1
        self.process.communicate.return_value = (None, json.dumps({"error": {
            "code": 1, "api_code": "InvalidApiKey", "http_status": 401,
            "message": f"rejected {self.key}", "request_id": "synthetic-request",
        }}))
        command = prepare_command(self.runtime, self.arguments, "api_key")
        with self.assertRaises(BailianFailure) as caught:
            run_recognition(self.runtime, command, [])
        self.assertTrue(caught.exception.started)
        self.assertEqual(caught.exception.report["http_status"], 401)
        self.assertEqual(caught.exception.report["code"], "InvalidApiKey")
        self.assertNotIn(self.key, json.dumps(caught.exception.report))
        self.popen.assert_called_once()
        self.process.communicate.assert_called_once()
        self.process.kill.assert_not_called()

    def test_interrupted_wait_kills_and_reaps_the_existing_process_without_retry(self):
        """验证中断等待时终止并回收原进程。"""
        command = prepare_command(self.runtime, self.arguments, "api_key")
        for failure in (subprocess.TimeoutExpired("synthetic", 1), KeyboardInterrupt(),
                        OSError("synthetic pipe failure")):
            with self.subTest(failure=type(failure).__name__):
                self.process.reset_mock()
                self.popen.reset_mock()
                self.process.communicate.side_effect = [failure, (None, "private output")]
                with self.assertRaises(BailianFailure) as caught:
                    run_recognition(self.runtime, command, [])
                self.assertTrue(caught.exception.started)
                self.assertEqual(caught.exception.report["code"], "LOCAL_WAIT_INTERRUPTED")
                self.assertIn("中断", str(caught.exception))
                self.assertNotIn("private output", json.dumps(caught.exception.report))
                self.popen.assert_called_once()
                self.process.kill.assert_called_once()
                self.assertEqual(self.process.communicate.call_count, 2)
                self.assertEqual(self.process.communicate.call_args.kwargs, {})

    def test_timeout_reaps_an_actual_local_waiting_process(self):
        # 真进程只等待，不读凭据、不访问网络，验证超时处理确实回收Windows进程。
        """验证超时能回收真实本机等待进程。"""
        children = []

        def start_waiter(*args, **kwargs):
            """启动本机等待进程作为超时回收测试替身。"""
            child = _REAL_POPEN([sys.executable, "-c", "import time; time.sleep(30)"],
                               cwd=self.runtime.root, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8",
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            children.append(child)
            return child

        self.popen.side_effect = start_waiter
        command = prepare_command(self.runtime, self.arguments, "console")
        try:
            with patch("asr_runtime.utils.bailian.PROCESS_SECONDS", 0.05):
                with self.assertRaises(BailianFailure) as caught:
                    run_recognition(self.runtime, command, [])
            self.assertTrue(caught.exception.started)
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll())
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.communicate()

    def test_error_report_separates_cli_exit_code_from_api_error(self):
        """验证报告区分CLI退出码和API错误码。"""
        payload = {"error": {"code": 999, "api_code": "InvalidParameter", "http_status": 400,
                             "request_id": "synthetic-request", "message": "bad parameter",
                             "cause": {"message": "private detail"}, "hint": "private hint"}}
        report = explain_cli_error(1, json.dumps(payload), [])
        self.assertEqual(report["cli_exit_code"], 1)
        self.assertEqual(report["code"], "InvalidParameter")
        self.assertEqual(report["request_id"], "synthetic-request")
        self.assertIn("参数", report["explanation"])
        self.assertTrue(report["source_url"].startswith("https://"))
        self.assertNotIn("cause", report)
        self.assertNotIn("hint", report)

    def test_unknown_api_code_preserves_scalar_evidence_without_inventing_meaning(self):
        """验证未知API码保留标量证据并标记字典范围。"""
        report = explain_cli_error(91, json.dumps({"error": {
            "api_code": "Synthetic.NewError", "http_status": 599,
            "request_id": "synthetic-request", "message": "synthetic problem",
        }}), [])
        self.assertEqual(report["code"], "Synthetic.NewError")
        self.assertEqual(report["http_status"], 599)
        self.assertEqual(report["message"], "synthetic problem")
        self.assertIn("未收录", report["explanation"])
        self.assertIsNone(report["source_url"])

    def test_malformed_stderr_is_not_forwarded(self):
        """验证异常标准错误返回固定解析说明。"""
        for payload in ("raw private stderr", "null", "[]", '{"error": []}',
                        '{"error":{"api_code":[],"request_id":{},"http_status":true,"message":{}}}'):
            with self.subTest(payload=payload):
                report = explain_cli_error(1, payload, [])
                self.assertIsNone(report["code"])
                self.assertIsNone(report["request_id"])
                self.assertIsNone(report["http_status"])
                self.assertIn("未提供可解析", report["message"])

    def test_redaction_covers_private_values_urls_tokens_and_all_visible_error_fields(self):
        """验证私有输入、URL和令牌在错误字段中隐藏。"""
        private = ["synthetic-token", "合成私密上下文", "合成词"]
        text = ("synthetic-token 合成私密上下文 合成词 "
                "https://example.invalid/result?signature=secret oss://synthetic/audio "
                "sk-synthetic-key LTAIsyntheticAK Bearer opaqueSyntheticToken\nline")
        redacted = redact_message(text, private)
        for fragment in (*private, "example.invalid", "oss://", "sk-synthetic-key",
                         "LTAIsyntheticAK", "opaqueSyntheticToken"):
            self.assertNotIn(fragment, redacted)
        self.assertNotIn("\n", redacted)
        report = explain_cli_error(1, json.dumps({"error": {
            "message": text, "api_code": "synthetic-token", "request_id": "合成私密上下文",
        }}), private)
        self.assertEqual(report["code"], "[已隐藏]")
        self.assertEqual(report["request_id"], "[已隐藏]")
        self.assertLessEqual(len(redact_message("a" * 1000, [])), 800)

    def test_console_status_requires_model_key_not_just_authenticated(self):
        """验证模型Key存在才表示可执行识别。"""
        for status, configured in (({"authenticated": True, "console": {"masked": "masked"}}, False),
                                   ({"authenticated": True, "openapi": {"source": "config"}}, False),
                                   ({"authenticated": True, "api_key": "invalid"}, False),
                                   ({"authenticated": False}, False),
                                   ({"authenticated": True, "api_key": {"masked": "masked"}}, True)):
            with self.subTest(status=status):
                self.process.communicate.return_value = (json.dumps(status), "")
                report = console_status(self.runtime)
                self.assertEqual(report["configured"], configured)
                self.assertFalse(report["verified_online"])
                self.assertNotIn("masked", json.dumps(report))
        self.assertEqual(self.popen.call_args.kwargs["stdout"], subprocess.PIPE)
        argv = self.popen.call_args.args[0]
        self.assertEqual(argv[2:], ("auth", "status", "--config", "default", "--output", "json", "--quiet"))

    def test_console_status_rejects_nonobject_or_invalid_json(self):
        """验证控制台状态拒绝非对象或无效JSON。"""
        for output in ("not json", "[]", "null", "true"):
            with self.subTest(output=output):
                self.process.communicate.return_value = (output, "")
                with self.assertRaisesRegex(SetupError, "登录状态"):
                    console_status(self.runtime)

    def test_console_only_callback_is_reported_without_telling_user_to_login_again(self):
        """验证控制台凭据存在且模型Key缺失时返回配置说明。"""
        self.process.communicate.return_value = (json.dumps({
            "authenticated": True, "console": {"source": "config", "masked": "synthetic-masked"},
        }), "")
        report = console_status(self.runtime)
        self.assertTrue(report["console_configured"])
        self.assertFalse(report["configured"])
        self.assertFalse(report["verified_online"])
        self.assertIn("控制台凭据已保存", report["message"])
        self.assertIn("未配置模型 API Key", report["message"])
        self.assertNotIn("请先运行login", report["message"])
        self.assertNotIn("synthetic-masked", json.dumps(report))

    def test_successful_login_process_still_checks_public_status(self):
        """验证登录进程成功后仍检查公开状态。"""
        self.process.stdout = io.StringIO("")
        self.process.stderr = io.StringIO("")
        self.process.communicate.return_value = (json.dumps({"authenticated": False}), "")
        with patch("asr_runtime.utils.bailian.check_login_execution_context"):
            report = login_console(self.runtime)
        self.assertFalse(report["configured"])
        self.assertEqual(self.popen.call_count, 2)
        first, second = self.popen.call_args_list
        self.assertEqual(first.args[0][1:3], ("--require", str(self.runtime.resource("scripts/bailian/console-browser.cjs"))))
        self.assertEqual(first.args[0][4:], ("auth", "login", "--console", "--console-site", "domestic",
                                             "--config", "default", "--output", "json", "--quiet"))
        self.assertNotIn("--base-url", first.args[0])
        self.assertEqual(second.args[0][2:4], ("auth", "status"))
        self.assertNotIn("DASHSCOPE_API_KEY", first.kwargs["env"])
        self.process.wait.assert_called_once_with(timeout=None)

    def test_failed_login_does_not_repeat_login_or_request_status(self):
        """验证登录失败立即返回原进程错误。"""
        self.process.returncode = 6
        self.process.stdout = io.StringIO("")
        self.process.stderr = io.StringIO('{"error":{"code":6,"message":"synthetic network failure"}}')
        with patch("asr_runtime.utils.bailian.check_login_execution_context"), self.assertRaises(BailianFailure):
            login_console(self.runtime)
        self.popen.assert_called_once()

    @unittest.skipUnless(CONTRACT_BL_ENTRY.is_file(), "需要在专用测试工作区安装 BL 才能运行本机状态合约")
    def test_real_cli_status_reads_only_synthetic_workspace_configuration(self):
        """验证真实 CLI 返回合成工作区的登录状态。"""
        config = self.runtime.path(".state/bailian/config.json")
        config.write_text(json.dumps({"api_key": self.key,
                                     "base_url": "https://dashscope.aliyuncs.com"}), encoding="utf-8")
        self.popen.side_effect = _REAL_POPEN
        with patch("asr_runtime.utils.bailian.bl_command", side_effect=lambda runtime, args:
                   [str(find_node()), str(contract_runtime().bl_entry), *args, "--quiet"]):
            report = console_status(self.runtime)
        self.assertTrue(report["configured"])
        self.assertFalse(report["verified_online"])
        self.assertNotIn(self.key, json.dumps(report))
        self.assertEqual(self.popen.call_args.kwargs["env"]["BAILIAN_CONFIG_DIR"], str(config.parent))
