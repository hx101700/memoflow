"""通过固定pip与本机合成wheel验证下载续传和摘要拒绝。"""

import base64
from contextlib import redirect_stderr
import hashlib
import io
import re
import subprocess
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from asr_runtime.application.bootstrap import _download_python_packages
from asr_runtime.utils.environment import Runtime, run_process
from asr_runtime.utils.installation import PIP_VERSION, PythonIndex, run_installer
from tests.support import CONTRACT_WORKSPACE, SKILL_ROOT, RuntimeTestCase


WHEEL_FILENAME = "memoflow_download_fixture-1.0.0-py3-none-any.whl"


def fixture_wheel() -> bytes:
    """生成含合法元数据和512KiB合成内容的纯Python wheel。"""
    metadata = "memoflow_download_fixture-1.0.0.dist-info"
    entries = {
        "memoflow_download_fixture/__init__.py": b"",
        "memoflow_download_fixture/payload.bin": bytes(range(256)) * 2048,
        f"{metadata}/METADATA": (
            b"Metadata-Version: 2.1\nName: memoflow-download-fixture\nVersion: 1.0.0\n"
        ),
        f"{metadata}/WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: MemoFlow contract test\n"
            b"Root-Is-Purelib: true\nTag: py3-none-any\n"
        ),
    }
    records = []
    for name, content in entries.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode("ascii").rstrip("=")
        records.append(f"{name},sha256={digest},{len(content)}\n")
    records.append(f"{metadata}/RECORD,,\n")
    entries[f"{metadata}/RECORD"] = "".join(records).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as wheel:
        for name, content in entries.items():
            wheel.writestr(name, content)
    return buffer.getvalue()


class PipDownloadContractTests(RuntimeTestCase):
    python: Path

    @classmethod
    def setUpClass(cls) -> None:
        """确认独立验收目录提供本轮固定版本的真实pip。"""
        super().setUpClass()
        cls.python = CONTRACT_WORKSPACE / ".asr-transcription/.venv/Scripts/python.exe"
        if not cls.python.is_file():
            raise unittest.SkipTest("请先在.runtime/skill-contract-workspace完成bootstrap，以提供真实pip。")
        runtime = Runtime(CONTRACT_WORKSPACE, SKILL_ROOT)
        result = run_process(runtime, [str(cls.python), "-I", "-X", "utf8", "-m", "pip", "--version"])
        if result.returncode or not result.stdout.startswith(f"pip {PIP_VERSION} "):
            raise unittest.SkipTest(f"下载合约需要验收目录中的pip {PIP_VERSION}。")

    def setUp(self) -> None:
        """为每个合约建立独立下载目录与合成wheel。"""
        super().setUp()
        self.runtime.prepare()
        self.wheel = fixture_wheel()
        self.digest = hashlib.sha256(self.wheel).hexdigest()
        self.destination = self.runtime.path(".runtime/downloads")
        self.destination.mkdir()

    def serve_wheel(self, *, truncate_first: bool = True,
                    supports_range: bool = True) -> tuple[str, list[str | None]]:
        """启动可截断首个响应并控制Range行为的本机下载服务。"""
        wheel = self.wheel
        ranges: list[str | None] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                """按本例设定发送部分响应或完整wheel。"""
                if self.path != f"/{WHEEL_FILENAME}":
                    self.send_error(404)
                    return
                requested_range = self.headers.get("Range")
                ranges.append(requested_range)
                start = 0
                if requested_range and supports_range:
                    match = re.fullmatch(r"bytes=(\d+)-", requested_range)
                    if not match or int(match[1]) >= len(wheel):
                        self.send_error(416)
                        return
                    start = int(match[1])
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{len(wheel) - 1}/{len(wheel)}")
                else:
                    self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(wheel) - start))
                self.send_header("ETag", '"memoflow-download-fixture"')
                self.send_header("Connection", "close")
                self.end_headers()
                payload = wheel[:128 * 1024] if truncate_first and len(ranges) == 1 else wheel[start:]
                self.wfile.write(payload)
                self.wfile.flush()
                self.close_connection = True

            def log_message(self, format: str, *args: object) -> None:
                """将请求细节保留在合约断言中。"""

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(worker.join, 5)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}/{WHEEL_FILENAME}", ranges

    def download(self, url: str, digest: str) -> subprocess.CompletedProcess[str]:
        """使用真实pip下载本机wheel并核对给定摘要。"""
        return run_process(self.runtime, [
            str(self.python), "-I", "-X", "utf8", "-m", "pip", "download", "--no-index", "--no-deps",
            "--require-hashes", "--resume-retries", "2", "--retries", "0", "--timeout", "2",
            "--no-cache-dir", "--disable-pip-version-check", "--progress-bar", "off",
            "--dest", str(self.destination), f"{url}#sha256={digest}",
        ], timeout=30)

    def assert_completed_download(self, result: subprocess.CompletedProcess[str]) -> None:
        """确认下载成功且最终wheel与原始合成内容一致。"""
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        saved = (self.destination / WHEEL_FILENAME).read_bytes()
        self.assertEqual(hashlib.sha256(saved).hexdigest(), self.digest)
        self.assertEqual(saved, self.wheel)

    def test_short_response_resumes_with_range(self) -> None:
        """验证首个响应截断后pip续传剩余内容并保留正确摘要。"""
        url, ranges = self.serve_wheel()
        result = self.download(url, self.digest)
        self.assert_completed_download(result)
        self.assertEqual(len(ranges), 2)
        self.assertIsNone(ranges[0])
        self.assertRegex(ranges[1] or "", r"^bytes=[1-9]\d*-$")

    def test_production_download_log_preserves_chinese_workspace(self) -> None:
        """验证生产下载命令经真实pip和日志转发后完整保留中文空格路径。"""
        workspace = self.runtime.workspace / "中文 空格"
        workspace.mkdir()
        runtime = Runtime(workspace, self.runtime.skill_root)
        runtime.prepare()
        url, ranges = self.serve_wheel(truncate_first=False)
        runtime.resource("scripts/requirements.txt").write_text(
            f"{url} --hash=sha256:{self.digest}\n", encoding="utf-8")
        index = PythonIndex("本机合约", url.rsplit("/", 1)[0] + "/simple/", "")
        log_path = runtime.path(".runtime/python-install.log")

        def execute_download(selected_runtime, arguments, log):
            """从外层目录执行生产参数，让pip的相对保存路径也包含中文。"""
            self.assertEqual(selected_runtime, runtime)
            return run_installer(self.runtime, [str(self.python), *arguments[1:]], log)

        with log_path.open("w", encoding="utf-8") as log, redirect_stderr(io.StringIO()), \
                patch("asr_runtime.application.bootstrap.run_installer", side_effect=execute_download):
            _download_python_packages(runtime, [index], log, installer=False)
        output = log_path.read_text(encoding="utf-8")
        saved_line = next(line for line in output.splitlines() if line.startswith("Saved "))
        self.assertIn("中文 空格", saved_line)
        self.assertNotIn("\ufffd", output)
        self.assertEqual(runtime.path(".runtime/wheels/" + WHEEL_FILENAME).read_bytes(), self.wheel)
        self.assertEqual(ranges, [None])

    def test_ignored_range_restarts_the_download(self) -> None:
        """验证服务端忽略Range时pip重新下载完整文件。"""
        url, ranges = self.serve_wheel(supports_range=False)
        result = self.download(url, self.digest)
        self.assert_completed_download(result)
        self.assertEqual(len(ranges), 2)
        self.assertIsNone(ranges[0])
        self.assertRegex(ranges[1] or "", r"^bytes=[1-9]\d*-$")

    def test_complete_file_with_wrong_hash_is_rejected(self) -> None:
        """验证完整响应的摘要不匹配时pip拒绝保存wheel。"""
        url, ranges = self.serve_wheel(truncate_first=False)
        expected = hashlib.sha256(self.wheel + b"different expected content").hexdigest()
        result = self.download(url, expected)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected sha256 " + expected, result.stderr)
        self.assertIn(self.digest, result.stderr)
        self.assertEqual(ranges, [None])
        self.assertEqual(list(self.destination.iterdir()), [])
