"""用合成录音与本机服务验证 BL 原生上传超时，不访问云端。"""

import json
import os
import subprocess
import threading
import time
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from asr_runtime import MODEL
from asr_runtime.utils.auth import bailian_environment
from asr_runtime.utils.bailian import explain_cli_error
from tests.support import CONTRACT_BL_ENTRY, RuntimeTestCase, contract_runtime
_PRELOAD_SOURCE = r"""
const fs = require("node:fs");
const undici = require("node:module").createRequire(process.argv[1])("undici");
const dispatcher = new undici.MockAgent();
dispatcher.disableNetConnect();
dispatcher.enableNetConnect(new URL(fixture.base_url).host);
undici.setGlobalDispatcher(dispatcher);
const originalFetch = undici.fetch;
const originalSetTimeout = globalThis.setTimeout;
const evidence = {
  policy_requests: 0, blocked_external_requests: 0, upload_aborted: false,
  upload_timer_ms: null
};
let lastTimerMs = null;

// 保存请求阶段与计时证据，供进程未退出时检查。
function snapshot() {
  fs.writeFileSync(fixture.evidence_path, JSON.stringify(evidence), "utf8");
}

// 记录官方上传使用的计时器，保持实际等待时长。
globalThis.setTimeout = function recordTimer(callback, delay, ...args) {
  lastTimerMs = delay;
  return originalSetTimeout(callback, delay, ...args);
};

// 观察BL实际使用的Undici入口，只允许本次本机服务，不改写官方上传路径。
undici.fetch = async function localFetch(input, options) {
  const target = typeof input === "string" || input instanceof URL ? String(input) : input.url;
  if (new URL(target).origin !== fixture.base_url) {
    evidence.blocked_external_requests += 1;
    snapshot();
    throw new Error("External request blocked by the upload contract fixture.");
  }
  if (target === fixture.policy_url) evidence.policy_requests += 1;
  if (target === fixture.base_url + "/upload") {
    evidence.upload_timer_ms = lastTimerMs;
    options.signal.addEventListener("abort", function recordUploadAbort() {
      // 保存上传中止事实，不采集请求正文或凭据。
      evidence.upload_aborted = true;
      snapshot();
    }, { once: true });
  }
  evidence.last_fetch = target;
  snapshot();
  return originalFetch(target, options);
};

// 保存本次隔离进程的计时与网络边界证据。
process.once("exit", function saveEvidence() {
  snapshot();
});
"""


@unittest.skipUnless(CONTRACT_BL_ENTRY.is_file(), "需要已安装的固定官方 BL 才能运行上传合约")
class BailianUploadContractTests(RuntimeTestCase):
    def setUp(self):
        """创建合成录音，并启动凭证、上传与识别的本机模拟服务。"""
        super().setUp()
        self.runtime.prepare()
        self.calls = []
        self.submitted = None
        self.upload_bytes = 0
        self.upload_delay_seconds = 0.3
        self.policy_status = 200
        self.audio = self.runtime.workspace / "合成上传.wav"
        with wave.open(str(self.audio), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 1600)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                """关闭本机模拟服务的访问日志。"""
                pass

            def reply(self, payload, status=200):
                """返回合成 JSON，并忽略已超时客户端关闭的连接。"""
                body = json.dumps(payload).encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

            def do_GET(self):
                """提供合成上传凭证、已完成任务与转写结果。"""
                if self.path == f"/api/v1/uploads?action=getPolicy&model={MODEL}":
                    owner.calls.append("policy")
                    if owner.policy_status != 200:
                        self.reply({
                            "code": "AccessDenied", "request_id": "synthetic-policy-request",
                            "message": f"Synthetic refusal for {owner.base_url}/private?token=fixture "
                                       "asr-transcription-synthetic-upload-key",
                        }, owner.policy_status)
                        return
                    self.reply({"data": {
                        "upload_host": owner.base_url + "/upload", "upload_dir": "synthetic",
                        "oss_access_key_id": "synthetic-access-key", "signature": "synthetic-signature",
                        "policy": "synthetic-policy", "x_oss_object_acl": "private",
                        "x_oss_forbid_overwrite": "true",
                    }})
                elif self.path == "/api/v1/tasks/local-upload-task":
                    owner.calls.append("task")
                    self.reply({"output": {
                        "task_id": "local-upload-task", "task_status": "SUCCEEDED", "results": [{
                            "subtask_status": "SUCCEEDED", "file_url": "oss://synthetic/合成上传.wav",
                            "transcription_url": owner.base_url + "/result.json",
                        }],
                    }})
                elif self.path == "/result.json":
                    owner.calls.append("result")
                    self.reply({"transcripts": [{"sentences": [{
                        "text": "合成本机结果", "begin_time": 0, "end_time": 100,
                    }]}]})
                else:
                    self.send_error(404)

            def do_POST(self):
                """接收合成 multipart 上传并延迟响应，随后模拟识别提交。"""
                body = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path == "/upload":
                    owner.calls.append("upload")
                    owner.upload_bytes = len(body)
                    time.sleep(owner.upload_delay_seconds)
                    self.reply({})
                elif self.path == "/api/v1/services/audio/asr/transcription":
                    owner.calls.append("submit")
                    owner.submitted = json.loads(body)
                    self.reply({"output": {"task_id": "local-upload-task", "task_status": "PENDING"}})
                else:
                    self.send_error(404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        """关闭本机服务并清理本例自有临时文件。"""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        super().tearDown()

    def invoke(self, timeout):
        """用原生 BL 入口执行本机上传合约，并读取隔离进程证据。"""
        self.runtime.path(".env").write_text(
            "DASHSCOPE_API_KEY=asr-transcription-synthetic-upload-key\n", encoding="utf-8")
        evidence_path = self.runtime.path("upload-evidence.json")
        fixture = {
            "base_url": self.base_url,
            "policy_url": f"{self.base_url}/api/v1/uploads?action=getPolicy&model={MODEL}",
            "evidence_path": str(evidence_path),
        }
        preload = self.runtime.path("upload-fixture.cjs")
        preload.write_text("const fixture = " + json.dumps(fixture) + ";\n" + _PRELOAD_SOURCE,
                           encoding="utf-8")
        output = self.runtime.path("result.json")
        # 官方base-url直接选择本机上传服务；预加载只阻断外网并记录计时。
        command = [
            str(contract_runtime().node_entry), "--require", str(preload), str(CONTRACT_BL_ENTRY),
            "speech", "recognize", "--config", "default", "--model", MODEL,
            "--url", str(self.audio), "--base-url", self.base_url, "--out", str(output),
            "--timeout", str(timeout), "--poll-interval", "0.01", "--output", "json", "--quiet",
        ]
        try:
            result = subprocess.run(
                command, cwd=self.runtime.workspace, env=bailian_environment(self.runtime, "api_key"),
                stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                timeout=10, shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired as exc:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.is_file() else {}
            self.fail(f"BL进程未退出；calls={self.calls!r}; evidence={evidence!r}; "
                      f"stdout={exc.stdout!r}; stderr={exc.stderr!r}; result_exists={output.exists()}")
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["blocked_external_requests"], 0)
        return result, output, evidence

    def assert_upload_timeout(self, result, output, evidence):
        """核对上传中止、结构化超时与未进入识别提交的事实。"""
        self.assertEqual(result.returncode, 5, result.stderr)
        diagnostics = [json.loads(line) for line in result.stderr.splitlines() if line.strip()]
        self.assertIn("warning", diagnostics[0])
        report = explain_cli_error(result.returncode, result.stderr, [])
        self.assertEqual(report["message"], "Request timed out.")
        self.assertEqual(self.calls, ["policy", "upload"])
        self.assertGreater(self.upload_bytes, self.audio.stat().st_size)
        self.assertTrue(evidence["upload_aborted"])
        self.assertEqual(evidence["policy_requests"], 1)
        self.assertFalse(output.exists())
        self.assertIsNone(self.submitted)

    def test_official_timeout_allows_upload_within_user_limit(self):
        """验证官方包在一秒设置下完成三百毫秒上传与单次识别。"""
        result, output, evidence = self.invoke(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls, ["policy", "upload", "submit", "task", "result"])
        self.assertEqual(self.submitted["input"]["file_urls"], ["oss://synthetic/合成上传.wav"])
        self.assertEqual(evidence["upload_timer_ms"], 1000)
        self.assertFalse(evidence["upload_aborted"])
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["transcripts"][0]
                         ["sentences"][0]["text"], "合成本机结果")

    def test_official_timeout_stops_upload_at_user_limit_without_retry(self):
        """验证官方包按零点一秒设置中止上传，且不提交或重传。"""
        result, output, evidence = self.invoke(0.1)
        self.assert_upload_timeout(result, output, evidence)
        self.assertEqual(evidence["upload_timer_ms"], 100)

    def test_policy_refusal_preserves_official_metadata_and_redacts_private_values(self):
        """验证官方上传凭证错误透传状态与请求编号，本机脱敏且不上传或重试。"""
        self.policy_status = 403
        result, output, evidence = self.invoke(1)
        self.assertEqual(result.returncode, 1, result.stderr)
        report = explain_cli_error(result.returncode, result.stderr,
                                   ["asr-transcription-synthetic-upload-key"])
        self.assertEqual(report["http_status"], 403)
        self.assertEqual(report["code"], "AccessDenied")
        self.assertEqual(report["request_id"], "synthetic-policy-request")
        self.assertIn("Synthetic refusal", report["message"])
        self.assertNotIn(self.base_url, report["message"])
        self.assertNotIn("token=fixture", report["message"])
        self.assertNotIn("asr-transcription-synthetic-upload-key", report["message"])
        self.assertEqual(self.calls, ["policy"])
        self.assertEqual(evidence["policy_requests"], 1)
        self.assertEqual(self.upload_bytes, 0)
        self.assertIsNone(self.submitted)
        self.assertFalse(output.exists())
