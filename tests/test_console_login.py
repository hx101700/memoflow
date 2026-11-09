"""验证登录权限边界及官方 BL 的 Windows 开页和回调合约。"""

import contextlib
import io
import json
import os
import subprocess
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch

from asr_runtime.utils.auth import bailian_environment
from asr_runtime.utils.bailian import console_status, login_console, bl_command, explain_cli_error
from asr_runtime.utils.environment import SetupError, check_login_execution_context
from tests.support import RuntimeTestCase, CONTRACT_BL_ENTRY, contract_runtime


class LoginPermissionTests(RuntimeTestCase):
    def test_restricted_process_stops_before_login_side_effects(self):
        """验证受限权限在 BL、浏览器及运行目录准备之前返回操作提示。"""
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
        """验证 Windows 令牌检查区分受限状态并关闭查询句柄。"""
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


@unittest.skipUnless(os.name == "nt" and CONTRACT_BL_ENTRY.is_file(),
                     "需要 Windows 及专用测试工作区中的官方 BL")
class NativeLoginContractTests(RuntimeTestCase):
    def test_official_opener_passes_one_complete_url_and_callback_saves_credentials(self):
        """验证完整URL只打开一次，快速回调先于开页结束仍能保存凭据。"""
        self.runtime.prepare()
        evidence = self.runtime.path("login-evidence.json")
        fixture = self.runtime.path("login-fixture.cjs")
        fixture.write_text(r'''
const fs = require("node:fs");
const http = require("node:http");
const cp = require("node:child_process");
const undici = require("node:module").createRequire(process.argv[1])("undici");
const dispatcher = new undici.MockAgent();
dispatcher.disableNetConnect();
undici.setGlobalDispatcher(dispatcher);
const evidence = { invocations: [], blocked_external_requests: 0 };
const evidencePath = require("node:path").join(__dirname, "login-evidence.json");
const save = () => fs.writeFileSync(evidencePath, JSON.stringify(evidence));

// 屏蔽云端网络，保证本例只使用官方授权流程的本机回调。
undici.fetch = async () => {
  evidence.blocked_external_requests += 1;
  save();
  throw Error("External request blocked by the login contract fixture.");
};

// 记录原生 Windows 打开命令，用合成本机回调代替真实浏览器授权。
cp.execFile = (file, args, options, callback) => {
  evidence.invocations.push({ file, args, options });
  save();
  const quoted = args.at(-1).match(/^"start "" "(https:\/\/[^\"]+)""$/);
  if (!quoted) throw Error("Unexpected Windows browser invocation.");
  const loginUrl = new URL(quoted[1]);
  const target = new URL("http://" + loginUrl.searchParams.get("notice"));
  if (target.hostname !== "127.0.0.1") throw Error("Callback must use loopback.");
  queueMicrotask(() => {
    // 回调收到响应后才完成打开程序，覆盖2.5.1修正的快速回调顺序。
      const body = JSON.stringify({ api_key: "fixture-login-key", access_token: "fixture-console-token" });
      const request = http.request(target, { method: "POST", headers: {
        "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body)
      } }, response => {
        evidence.callback_status = response.statusCode;
        response.resume();
        response.on("end", () => {
          evidence.callback_before_open_completion = true;
          save();
          callback(null, "", "");
        });
      });
      request.on("error", error => { evidence.callback_error = error.message; save(); });
      request.end(body);
  });
  return {};
};
require("node:module").syncBuiltinESMExports();
''', encoding="utf-8")
        arguments = ["auth", "login", "--console", "--console-site", "domestic",
                     "--config", "default", "--output", "text"]
        argv = bl_command(contract_runtime(), arguments)
        argv[1:1] = ["--require", str(fixture)]
        env = bailian_environment(self.runtime, "console")
        result = subprocess.run(
            argv, cwd=self.runtime.workspace, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", timeout=20,
            shell=False, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        recorded = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(recorded["blocked_external_requests"], 0)
        self.assertEqual(recorded["callback_status"], 200)
        self.assertTrue(recorded["callback_before_open_completion"])
        self.assertEqual(len(recorded["invocations"]), 1)
        invocation = recorded["invocations"][0]
        self.assertEqual(invocation["file"], "cmd")
        self.assertEqual(invocation["args"][:4], ["/d", "/v:off", "/s", "/c"])
        self.assertTrue(invocation["options"]["windowsHide"])
        self.assertTrue(invocation["options"]["windowsVerbatimArguments"])
        target = invocation["args"][4].removeprefix('"start "" "').removesuffix('""')
        parsed = urlsplit(target)
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path),
                         ("https", "bailian.console.aliyun.com", "/console-login"))
        query = parse_qs(parsed.query)
        self.assertEqual(query["needapikey"], ["true"])
        self.assertRegex(query["notice"][0], r"^127\.0\.0\.1:\d+\?state=[0-9a-f]{32}$")
        credentials = json.loads(self.runtime.path(".state/bailian/config.json").read_text(encoding="utf-8"))
        self.assertEqual(credentials["api_key"], "fixture-login-key")
        self.assertEqual(credentials["access_token"], "fixture-console-token")

        def installed_command(_runtime, arguments):
            """查询当前测试工作区，并为状态查询进程保留同一网络阻断。"""
            command = bl_command(contract_runtime(), arguments)
            command[1:1] = ["--require", str(fixture)]
            return command

        with patch("asr_runtime.utils.bailian.bl_command", side_effect=installed_command):
            status = console_status(self.runtime)
        self.assertTrue(status["configured"])
        self.assertTrue(status["console_configured"])
        self.assertFalse(status["verified_online"])
        self.assertEqual(json.loads(evidence.read_text(encoding="utf-8"))["blocked_external_requests"], 0)

    def test_official_text_login_timeout_uses_exit_code(self):
        """验证文本登录超时按退出码解释，授权链接保留在进程内部。"""
        self.runtime.prepare()
        fixture = self.runtime.path("login-timeout-fixture.cjs")
        fixture.write_text(r'''
const cp = require("node:child_process");
const undici = require("node:module").createRequire(process.argv[1])("undici");
const dispatcher = new undici.MockAgent();
dispatcher.disableNetConnect();
undici.setGlobalDispatcher(dispatcher);
const originalSetTimeout = globalThis.setTimeout;
// 仅缩短本机夹具中的官方15分钟登录计时器。
globalThis.setTimeout = (callback, delay, ...args) =>
  originalSetTimeout(callback, delay === 900000 ? 50 : delay, ...args);
undici.fetch = async () => { throw Error("External request blocked by login fixture."); };
cp.execFile = (_file, _args, _options, callback) => {
  queueMicrotask(() => callback(null, "", ""));
  return {};
};
require("node:module").syncBuiltinESMExports();
''', encoding="utf-8")
        argv = bl_command(contract_runtime(), ["auth", "login", "--console", "--console-site", "domestic",
                                               "--config", "default", "--output", "text"])
        argv[1:1] = ["--require", str(fixture)]
        result = subprocess.run(argv, cwd=self.runtime.workspace, env=bailian_environment(self.runtime, "console"),
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                                timeout=20, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 5, result.stderr)
        report = explain_cli_error(result.returncode, result.stderr, [])
        self.assertEqual(report["cli_exit_code"], 5)
        self.assertIn("超时", report["message"])
        self.assertNotIn("console-login?", json.dumps(report))
        self.assertFalse(self.runtime.path(".state/bailian/config.json").exists())
