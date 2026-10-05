"""用合成进程和浏览器替身验证Windows登录链接转交。"""

import contextlib
import http.client
import io
import json
import os
import subprocess
import sys
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch

from asr_runtime.utils.bailian import BailianFailure, PreparedCommand, _communicate_login, _open_login_url, _run_bl, bl_command, login_console
from asr_runtime.utils.environment import SetupError, child_environment, check_login_execution_context, find_node
from tests.support import RuntimeTestCase, CONTRACT_BL_ENTRY, contract_runtime


STATE = "0123456789abcdef0123456789abcdef"
LOGIN_URL = ("https://bailian.console.aliyun.com/console-login?"
             f"notice=127.0.0.1:12345?state={STATE}&needapikey=true")


class ConsoleLoginTests(RuntimeTestCase):
    def setUp(self):
        """准备隔离登录环境并替换浏览器打开入口。"""
        super().setUp()
        self.runtime.prepare()
        browser_patch = patch("asr_runtime.utils.bailian.os.startfile")
        self.open_browser = browser_patch.start()
        self.addCleanup(browser_patch.stop)

    def start_process(self, script: str, *arguments: str):
        """启动合成登录子进程并登记清理回调。"""
        process = subprocess.Popen(
            [sys.executable, "-c", script, *arguments], cwd=self.runtime.root,
            env=child_environment(self.runtime), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        def cleanup():
            """终止测试登录进程并关闭输出管道。"""
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()

        self.addCleanup(cleanup)
        return process

    def assert_reaped_and_closed(self, process):
        """断言进程已结束且输出管道已关闭。"""
        self.assertIsNotNone(process.poll())
        self.assertTrue(process.stdout.closed)
        self.assertTrue(process.stderr.closed)

    def test_full_url_reaches_shell_execute_without_losing_needapikey(self):
        """验证完整登录URL及其参数传递给系统打开入口。"""
        _open_login_url(LOGIN_URL)
        self.open_browser.assert_called_once_with(LOGIN_URL)
        self.assertIn("&needapikey=true", self.open_browser.call_args.args[0])

    def test_official_url_without_optional_key_parameter_is_supported(self):
        """验证基础官方登录URL可传递给系统打开入口。"""
        url = LOGIN_URL.removesuffix("&needapikey=true")
        _open_login_url(url)
        self.open_browser.assert_called_once_with(url)

    def test_invalid_url_or_nonce_never_opens_or_leaks_to_public_output(self):
        """验证非法URL或状态值返回脱敏错误。"""
        invalid = [
            LOGIN_URL.replace("https://", "http://"),
            LOGIN_URL.replace("bailian.console.aliyun.com", "example.invalid"),
            LOGIN_URL.replace("bailian.console.aliyun.com", "bailian.console.aliyun.com.example.invalid"),
            LOGIN_URL.replace("bailian.console.aliyun.com", "synthetic@bailian.console.aliyun.com"),
            LOGIN_URL.replace("/console-login?", "/other?"),
            LOGIN_URL.replace("127.0.0.1", "127.0.0.2"),
            LOGIN_URL.replace(":12345?", ":0?"),
            LOGIN_URL.replace(":12345?", ":65536?"),
            LOGIN_URL.replace(STATE, "synthetic-short-state"),
            LOGIN_URL.replace(STATE, "g" * 32),
            LOGIN_URL.replace("needapikey=true", "needapikey=false"),
            LOGIN_URL + "&needapikey=true",
            LOGIN_URL + "&notice=127.0.0.1:12345?state=" + STATE,
            LOGIN_URL + "&unexpected=synthetic",
            LOGIN_URL + "#fragment",
            LOGIN_URL + " ",
            LOGIN_URL.replace("?notice=", "?notice"),
        ]
        for url in invalid:
            with self.subTest(url=url), contextlib.redirect_stdout(io.StringIO()) as stdout, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SetupError) as caught:
                    _open_login_url(url)
                self.assertNotIn(STATE, str(caught.exception))
                self.assertNotIn(url, str(caught.exception))
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "")
        self.open_browser.assert_not_called()

    def test_duplicate_login_urls_open_once(self):
        """验证重复登录链接对应一次页面打开。"""
        marker = self.runtime.path("opened.txt")
        script = (
            "import pathlib,sys,time\n"
            "print(sys.argv[1],flush=True); print(sys.argv[1],flush=True)\n"
            "while not pathlib.Path(sys.argv[2]).exists(): time.sleep(0.01)\n"
        )
        process = self.start_process(script, LOGIN_URL, str(marker))
        self.open_browser.side_effect = lambda url: marker.write_text("opened", encoding="utf-8")
        self.assertEqual(_communicate_login(process, 5), (None, ""))
        self.open_browser.assert_called_once_with(LOGIN_URL)
        self.assert_reaped_and_closed(process)

    def test_link_is_opened_while_process_waits_for_callback(self):
        """验证登录进程等待回调时及时打开链接。"""
        marker = self.runtime.path("opened.txt")
        script = (
            "import pathlib,sys,time\n"
            "marker=pathlib.Path(sys.argv[2])\n"
            "print(sys.argv[1],flush=True)\n"
            "deadline=time.monotonic()+3\n"
            "while not marker.exists() and time.monotonic()<deadline: time.sleep(0.01)\n"
            "sys.exit(0 if marker.exists() else 17)\n"
        )
        process = self.start_process(script, LOGIN_URL, str(marker))

        def open_marker(url):
            """写入标记以模拟浏览器完成登录回调。"""
            self.assertIsNone(process.poll())
            self.assertEqual(url, LOGIN_URL)
            marker.write_text("opened", encoding="utf-8")

        self.open_browser.side_effect = open_marker
        self.assertEqual(_communicate_login(process, 5), (None, ""))
        self.assertEqual(process.returncode, 0)
        self.assertTrue(marker.is_file())
        self.assert_reaped_and_closed(process)

    def test_large_stderr_is_drained_before_process_can_print_url(self):
        """验证大量标准错误及时排空并读取备用链接。"""
        size = 1024 * 1024
        marker = self.runtime.path("opened.txt")
        script = (
            "import pathlib,sys,time\n"
            "sys.stderr.write('x'*int(sys.argv[2])); sys.stderr.flush()\n"
            "print(sys.argv[1],flush=True)\n"
            "while not pathlib.Path(sys.argv[3]).exists(): time.sleep(0.01)\n"
        )
        process = self.start_process(script, LOGIN_URL, str(size), str(marker))
        self.open_browser.side_effect = lambda url: marker.write_text("opened", encoding="utf-8")
        stdout, stderr = _communicate_login(process, 5)
        self.assertIsNone(stdout)
        self.assertEqual(len(stderr), size)
        self.open_browser.assert_called_once_with(LOGIN_URL)
        self.assert_reaped_and_closed(process)

    def test_timeout_kills_waiter_and_closes_both_pipes(self):
        """验证超时终止登录进程并关闭两条管道。"""
        process = self.start_process("import time; time.sleep(30)")
        with self.assertRaises(subprocess.TimeoutExpired):
            _communicate_login(process, 0.05)
        self.open_browser.assert_not_called()
        self.assert_reaped_and_closed(process)

    def test_open_failure_stops_waiting_and_does_not_expose_url(self):
        """验证浏览器打开失败后返回脱敏停止错误。"""
        process = self.start_process("import sys,time; print(sys.argv[1],flush=True); time.sleep(30)", LOGIN_URL)
        self.open_browser.side_effect = OSError("synthetic browser failure " + LOGIN_URL)
        with self.assertRaises(SetupError) as caught:
            _communicate_login(process, 5)
        self.assertNotIn(LOGIN_URL, str(caught.exception))
        self.assertNotIn(STATE, str(caught.exception))
        self.open_browser.assert_called_once_with(LOGIN_URL)
        self.assert_reaped_and_closed(process)

    def test_invalid_link_stops_waiting_and_reaps_process(self):
        """验证非法登录链接停止等待并回收进程。"""
        process = self.start_process("import sys,time; print(sys.argv[1],flush=True); time.sleep(30)",
                                     LOGIN_URL.replace(STATE, "invalid-state"))
        with self.assertRaisesRegex(SetupError, "官方格式"):
            _communicate_login(process, 5)
        self.open_browser.assert_not_called()
        self.assert_reaped_and_closed(process)

    def test_login_timeout_is_translated_once_without_second_cleanup_or_restart(self):
        """验证登录超时转换为失败并完成一次进程清理。"""
        process = self.start_process("import time; time.sleep(30)")
        command = PreparedCommand(("synthetic-bl", "auth", "login", "--console"), {})
        with patch("asr_runtime.utils.bailian.subprocess.Popen", return_value=process) as start:
            with self.assertRaises(BailianFailure) as caught:
                _run_bl(self.runtime, command, [], timeout=0.05, console_login=True)
        self.assertTrue(caught.exception.started)
        self.assertEqual(caught.exception.report["code"], "LOCAL_WAIT_INTERRUPTED")
        start.assert_called_once()
        self.assertEqual(start.call_args.kwargs["stdout"], subprocess.PIPE)
        self.assert_reaped_and_closed(process)


class LoginPermissionTests(RuntimeTestCase):
    def test_restricted_process_stops_before_login_side_effects(self):
        """验证受限权限在BL、浏览器及运行目录准备之前返回可操作错误。"""
        with patch("asr_runtime.utils.bailian.check_login_execution_context",
                   side_effect=SetupError("需要桌面权限")), \
             patch.object(type(self.runtime), "prepare") as prepare, \
             patch("asr_runtime.utils.bailian._run_bl") as run, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(SetupError, "桌面权限"):
                login_console(self.runtime)
        prepare.assert_not_called()
        run.assert_not_called()
        self.assertEqual(output.getvalue(), "")

    def test_windows_token_check_closes_handle_and_distinguishes_restrictions(self):
        """验证Windows令牌检查区分受限状态并关闭查询句柄。"""
        for restricted in (False, True):
            security, kernel = Mock(), Mock()
            security.OpenProcessToken.return_value = True
            security.IsTokenRestricted.return_value = restricted
            with self.subTest(restricted=restricted), \
                 patch("asr_runtime.utils.environment.ctypes.WinDLL", side_effect=[security, kernel]), \
                 patch("asr_runtime.utils.environment.ctypes.get_last_error", return_value=0):
                if restricted:
                    with self.assertRaisesRegex(SetupError, "require_escalated"):
                        check_login_execution_context()
                else:
                    check_login_execution_context()
            kernel.CloseHandle.assert_called_once()


class NativeLoginContractTests(RuntimeTestCase):
    def test_node_adapter_only_delegates_console_login_browser_calls(self):
        """验证适配阻止原生cmd开登录页，并保留其他execFile调用。"""
        adapter = self.runtime.resource("scripts/bailian/console-browser.cjs")
        script = r'''
const assert = require('node:assert/strict');
const cp = require('node:child_process');
let native = 0;
cp.execFile = () => { native += 1; return 'native'; };
require(process.argv[1]);
assert.throws(() => cp.execFile('cmd', ['/c', 'start', '', process.argv[2]], {}, () => {}), /MemoFlow/);
assert.equal(native, 0);
assert.equal(cp.execFile('node', ['--version'], {}, () => {}), 'native');
assert.equal(native, 1);
'''
        result = subprocess.run([str(find_node(contract_runtime())), "-e", script, str(adapter), LOGIN_URL],
                                capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(CONTRACT_BL_ENTRY.is_file(), "需要专用测试工作区中的固定BL")
    def test_real_bl_login_opens_one_complete_url_and_keeps_original_callback(self):
        """验证真实BL只交出一个完整链接，原回调保存合成凭据并正常退出。"""
        self.runtime.prepare()
        marker = self.runtime.path("native-browser-attempts")
        blocker = self.runtime.path("block-browser.cjs")
        blocker.write_text(
            "const cp=require('node:child_process'); const fs=require('node:fs'); "
            "cp.execFile=()=>{fs.writeFileSync(process.env.BROWSER_ATTEMPT_FILE,'called');"
            "throw Error('Native browser must not run in this test');};"
            "require('node:module').syncBuiltinESMExports();", encoding="utf-8")
        argv = bl_command(contract_runtime(), ["auth", "login", "--console", "--console-site", "domestic",
                                               "--config", "default", "--output", "json"])
        argv[1:1] = ["--require", str(blocker)]
        env = child_environment(self.runtime)
        env["BROWSER_ATTEMPT_FILE"] = str(marker)
        opened = []

        def complete_callback(url):
            """将合成凭据送入BL自身的本机回调，代替实际浏览器授权。"""
            opened.append(url)
            query = parse_qs(urlsplit(url).query)
            self.assertEqual(query["needapikey"], ["true"])
            callback = urlsplit("http://" + query["notice"][0])
            connection = http.client.HTTPConnection(callback.hostname, callback.port, timeout=5)
            try:
                connection.request("POST", "/?" + callback.query,
                                   json.dumps({"api_key": "fixture-login-key", "access_token": "fixture-console-token"}),
                                   {"Content-Type": "application/json"})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
            finally:
                connection.close()

        with patch("asr_runtime.utils.bailian.os.startfile", side_effect=complete_callback):
            _run_bl(self.runtime, PreparedCommand(tuple(argv), env), [], timeout=20, console_login=True)
        self.assertEqual(len(opened), 1)
        self.assertFalse(marker.exists(), "BL native browser opener must be suppressed")
        credentials = json.loads(self.runtime.path(".state/bailian/config.json").read_text(encoding="utf-8"))
        self.assertEqual(credentials["api_key"], "fixture-login-key")
        self.assertEqual(credentials["access_token"], "fixture-console-token")
