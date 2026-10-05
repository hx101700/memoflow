"""通过真实npm与本机registry验证锁定安装、有限换源和缓存复用。"""

import base64
import ctypes
from ctypes import wintypes
from contextlib import redirect_stderr
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import tarfile
import threading
import time
from typing import TextIO
from unittest.mock import patch
from urllib.parse import unquote

from asr_runtime.application.bootstrap import _install_bailian
from asr_runtime.utils.environment import Runtime, SetupError, find_node, npm_entry
from asr_runtime.utils.installation import run_installer
from tests.support import RuntimeTestCase, contract_runtime


def package_tarball(name: str, content: bytes = b"module.exports = 42;") -> bytes:
    """生成带固定版本元信息的合成npm依赖包。"""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        entries = {"package.json": json.dumps({"name": name, "version": "1.0.0"}).encode(),
                   "index.js": content}
        for filename, data in entries.items():
            entry = tarfile.TarInfo("package/" + filename)
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
    return buffer.getvalue()


def tarball_path(name: str, version: str = "1.0.0") -> str:
    """按npm默认registry布局生成锁定tarball路径。"""
    return f"/{name}/-/{name.rsplit('/', 1)[-1]}-{version}.tgz"


class NpmInstallContractTests(RuntimeTestCase):
    def setUp(self) -> None:
        """准备独立npm环境、合成依赖锁及真实本机Node/npm入口。"""
        super().setUp()
        self.runtime.prepare()
        self.node = find_node(contract_runtime())
        self.npm = npm_entry(self.node)
        self.destination = self.runtime.bl_directory
        self.destination.mkdir(parents=True)
        self.attempts: list[str] = []
        self.packages: dict[str, bytes] = {}
        self.configure_packages("memoflow-npm-fixture")

    def configure_packages(self, *names: str) -> None:
        """写入只引用npmjs公开URL的合成包清单与完整性摘要。"""
        self.packages = {name: package_tarball(name) for name in names}
        manifest = {"name": "memoflow-npm-contract", "version": "1.0.0", "private": True,
                    "dependencies": {name: "1.0.0" for name in names}}
        lock = {"name": manifest["name"], "version": "1.0.0", "lockfileVersion": 3,
                "requires": True, "packages": {"": manifest, **{
                    "node_modules/" + name: {
                        "version": "1.0.0", "resolved": "https://registry.npmjs.org" + tarball_path(name),
                        "integrity": "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode(),
                    } for name, data in self.packages.items()}}}
        (self.destination / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.lock_bytes = json.dumps(lock).encode()
        (self.destination / "package-lock.json").write_bytes(self.lock_bytes)

    def registry(self, mode: str = "success", *, failing_package: str | None = None) -> tuple[str, list[str]]:
        """启动只提供合成内容的本机registry，并记录实际请求路径。"""
        requests: list[str] = []
        delivered = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                """按场景返回包、元数据或网络错误，保持全部请求位于本机。"""
                slow_body = False
                request_path = unquote(self.path)
                requests.append(request_path)
                name = next((name for name in owner.packages if request_path == tarball_path(name)), None)
                if name is None:
                    name = request_path.lstrip("/")
                    if name not in owner.packages:
                        self.send_error(404)
                        return
                    integrity = "sha512-" + base64.b64encode(hashlib.sha512(owner.packages[name]).digest()).decode()
                    versions = {version: {"name": name, "version": version, "dist": {
                        "tarball": f"http://127.0.0.1:{self.server.server_port}" + tarball_path(name, version),
                        "integrity": integrity,
                    }} for version in ("1.0.0", "1.0.1")}
                    body = json.dumps({"name": name, "versions": versions, "dist-tags": {"latest": "1.0.1"}}).encode()
                    status = 200
                else:
                    scenario = mode if failing_package is None or name == failing_package else "success"
                    if failing_package is not None and name == failing_package:
                        # 给已发送的完整包留出npm写入内容缓存的时间，再结束失败下载。
                        delivered.wait(1)
                        time.sleep(0.05)
                    if scenario == "reset":
                        self.connection.shutdown(socket.SHUT_RDWR)
                        self.connection.close()
                        return
                    if scenario == "timeout":
                        time.sleep(0.6)
                    slow_body = scenario == "body_timeout"
                    status = int(scenario[5:]) if scenario.startswith("http_") else 200
                    body = (package_tarball(name, b"altered synthetic content") if scenario == "integrity"
                            else owner.packages[name])
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    if slow_body:
                        self.wfile.write(body[:16])
                        self.wfile.flush()
                        time.sleep(0.6)
                        body = body[16:]
                    self.wfile.write(body)
                    self.wfile.flush()
                    if name != failing_package:
                        delivered.set()
                except OSError:
                    pass

            def log_message(self, *args: object) -> None:
                """将合成registry日志保留在请求数组中。"""

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(worker.join, 5)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}/", requests

    def install(self, *registries: str) -> None:
        """调用生产安装用例，仅缩短测试中的npm网络重试与等待参数。"""
        def bounded_installer(runtime: Runtime, argv: list[str], log: TextIO, *, stdout_file: TextIO | None = None) -> int:
            """保留真实npm进程、标准流与隔离环境，将故障等待限定到本例。"""
            self.assertIn("--fetch-retries=2", argv)
            self.assertIn("--prefer-offline", argv)
            self.assertIn("--json", argv)
            self.attempts.append(argv[argv.index("--registry") + 1])
            bounded = ["--fetch-retries=0" if value == "--fetch-retries=2" else value for value in argv]
            return run_installer(runtime, [*bounded, "--fetch-timeout=300"], log, stdout_file=stdout_file)

        with patch("asr_runtime.application.bootstrap.rank_npm_registries", return_value=list(registries)), \
                patch("asr_runtime.application.bootstrap.run_installer", side_effect=bounded_installer), \
                redirect_stderr(io.StringIO()):
            _install_bailian(self.runtime, self.node, self.npm)

    def assert_installed(self) -> None:
        """核对npm保留原锁并安装其指定版本和内容。"""
        self.assertEqual((self.destination / "package-lock.json").read_bytes(), self.lock_bytes)
        for name in self.packages:
            directory = self.destination / "node_modules" / name
            self.assertEqual(json.loads((directory / "package.json").read_text())["version"], "1.0.0")
            self.assertEqual((directory / "index.js").read_bytes(), b"module.exports = 42;")

    def assert_fallback(self, failure: str, code: str) -> None:
        """核对首源错误由npm原生JSON识别，并且只切到第二源一次。"""
        first, first_requests = self.registry(failure)
        second, second_requests = self.registry()
        self.install(first, second)
        self.assertEqual(self.attempts, [first, second])
        self.assertTrue(first_requests)
        self.assertEqual(second_requests, [tarball_path("memoflow-npm-fixture")])
        self.assertIn(f"当前npm来源下载失败（{code}）", self.runtime.path(".runtime/bootstrap.log").read_text(encoding="utf-8"))
        self.assert_installed()

    def test_registry_replaces_npmjs_urls_and_preserves_scoped_package_integrity(self) -> None:
        """验证普通与带scope的锁定包都从指定registry获取并保留原锁。"""
        self.configure_packages("memoflow-npm-fixture", "@memoflow/scoped-fixture")
        first, requests = self.registry()
        second, unused = self.registry()
        self.install(first, second)
        self.assertEqual(self.attempts, [first])
        self.assertCountEqual(requests, [tarball_path(name) for name in self.packages])
        self.assertEqual(unused, [])
        self.assert_installed()

    def test_http_503_uses_the_second_registry(self) -> None:
        """验证registry暂不可用时读取E503并切换第二源。"""
        self.assert_fallback("http_503", "E503")

    def test_connection_reset_uses_the_second_registry(self) -> None:
        """验证连接中断由原生ECONNRESET触发一次换源。"""
        self.assert_fallback("reset", "ECONNRESET")

    def test_network_timeout_uses_the_second_registry(self) -> None:
        """验证当前npm的FETCH_ERROR超时输出可以触发一次换源。"""
        self.assert_fallback("timeout", "FETCH_ERROR")

    def test_stalled_tarball_body_uses_the_second_registry(self) -> None:
        """验证已开始接收tarball后停顿时由EIDLETIMEOUT触发换源。"""
        self.assert_fallback("body_timeout", "EIDLETIMEOUT")

    def test_wrong_integrity_is_rejected_then_valid_second_source_installs(self) -> None:
        """验证错误包不会被接受，第二源仍使用原锁摘要安装。"""
        self.assert_fallback("integrity", "EINTEGRITY")

    def test_both_wrong_integrities_stop_after_two_npm_processes(self) -> None:
        """验证两源摘要都不符时停止，不修改锁或增加第三次安装。"""
        first, first_requests = self.registry("integrity")
        second, second_requests = self.registry("integrity")
        with self.assertRaisesRegex(SetupError, "已尝试两个来源"):
            self.install(first, second)
        self.assertEqual(self.attempts, [first, second])
        self.assertTrue(first_requests and second_requests)
        self.assertEqual((self.destination / "package-lock.json").read_bytes(), self.lock_bytes)

    def test_completed_package_is_reused_from_npm_cache_after_switch(self) -> None:
        """验证首源已下载完整的包在换源后由npm缓存复用。"""
        self.configure_packages("memoflow-cached-fixture", "memoflow-failed-fixture")
        first, first_requests = self.registry("http_503", failing_package="memoflow-failed-fixture")
        second, second_requests = self.registry()
        self.install(first, second)
        self.assertEqual(self.attempts, [first, second])
        self.assertIn(tarball_path("memoflow-cached-fixture"), first_requests)
        self.assertEqual(second_requests, [tarball_path("memoflow-failed-fixture")])
        self.assert_installed()

    def test_lock_conflict_stops_without_using_the_second_registry(self) -> None:
        """验证package与锁冲突返回EUSAGE且保持单次npm调用。"""
        manifest = self.destination / "package.json"
        value = json.loads(manifest.read_text())
        value["dependencies"]["memoflow-npm-fixture"] = "1.0.1"
        manifest.write_text(json.dumps(value), encoding="utf-8")
        first, requests = self.registry()
        second, unused = self.registry()
        with self.assertRaisesRegex(SetupError, "EUSAGE"):
            self.install(first, second)
        self.assertEqual(self.attempts, [first])
        self.assertEqual(requests, ["/memoflow-npm-fixture"])
        self.assertEqual(unused, [])
        self.assertEqual((self.destination / "package-lock.json").read_bytes(), self.lock_bytes)

    def test_registry_forbidden_stops_without_using_the_second_registry(self) -> None:
        """验证源权限错误E403保持明确失败，避免误当下载中断。"""
        first, requests = self.registry("http_403")
        second, unused = self.registry()
        with self.assertRaisesRegex(SetupError, "E403"):
            self.install(first, second)
        self.assertEqual(self.attempts, [first])
        self.assertTrue(requests)
        self.assertEqual(unused, [])

    def test_locked_local_file_stops_without_switching_registries(self) -> None:
        """验证Windows本机文件占用返回EBUSY，且两个源都不会被请求。"""
        if os.name != "nt":
            self.skipTest("本机文件占用合约适用于Windows")
        held = self.destination / "node_modules/held.txt"
        held.parent.mkdir()
        held.write_bytes(b"synthetic held file")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(held), 0x80000000, 0, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        first, requests = self.registry()
        second, unused = self.registry()
        try:
            with self.assertRaisesRegex(SetupError, "EBUSY"):
                self.install(first, second)
        finally:
            kernel.CloseHandle(handle)
        self.assertEqual(self.attempts, [first])
        self.assertEqual(requests, [])
        self.assertEqual(unused, [])
