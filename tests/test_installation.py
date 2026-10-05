"""验证来源采样和安装进度的本机行为。"""

import ctypes
from ctypes import wintypes
import io
import json
import locale
import os
import subprocess
import sys
import threading
import time
import unittest
import venv
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from http.client import HTTPResponse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any
from unittest.mock import Mock, patch
from urllib.request import Request, urlopen

from asr_runtime.utils import installation
from asr_runtime.utils.environment import Runtime, SetupError, run_process
from asr_runtime.utils.installation import PythonIndex, rank_npm_registries, rank_python_indexes, run_installer
from tests.support import RuntimeTestCase


class IndexSamplingTests(unittest.TestCase):
    def sample_source(self, name: str, *, delay: float = 0, unavailable: bool = False,
                      ignore_range: bool = False, header_delay: float = 0) -> tuple[PythonIndex, list[str | None]]:
        """启动只提供合成字节的来源并登记测试结束时的回收操作。"""
        ranges: list[str | None] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                """发送定速合成数据或指定的失败响应。"""
                ranges.append(self.headers.get("Range"))
                if unavailable:
                    self.send_error(503)
                    return
                time.sleep(header_delay)
                size = 512 * 1024 if ignore_range else 256 * 1024
                self.send_response(200 if ignore_range else 206)
                self.send_header("Content-Length", str(size))
                self.end_headers()
                try:
                    for _ in range(size // 8192):
                        time.sleep(delay)
                        self.wfile.write(b"x" * 8192)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

            def log_message(self, format: str, *args: object) -> None:
                """将合成服务日志留在测试断言中。"""

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(worker.join, 5)
        self.addCleanup(server.shutdown)
        base_url = f"http://127.0.0.1:{server.server_port}/"
        return PythonIndex(name, base_url + "simple/", base_url), ranges

    def test_faster_source_ranks_first(self) -> None:
        """验证实际收到的数据吞吐率决定顺序。"""
        slow, _ = self.sample_source("slow", delay=0.01)
        fast, _ = self.sample_source("fast")
        with patch.object(installation, "PYTHON_INDEXES", (slow, fast)):
            self.assertEqual(rank_python_indexes(), [fast, slow])

    def test_failed_source_remains_last_candidate(self) -> None:
        """验证失败来源保留在成功来源之后。"""
        missing, _ = self.sample_source("missing", unavailable=True)
        working, _ = self.sample_source("working")
        with patch.object(installation, "PYTHON_INDEXES", (missing, working)):
            self.assertEqual(rank_python_indexes(), [working, missing])

    def test_all_failed_sources_preserve_the_finite_candidates(self) -> None:
        """验证全部采样失败后仍返回原有候选供安装命令诊断。"""
        first, _ = self.sample_source("first", unavailable=True)
        second, _ = self.sample_source("second", unavailable=True)
        with patch.object(installation, "PYTHON_INDEXES", (first, second)):
            self.assertEqual(rank_python_indexes(), [first, second])

    def test_ignored_range_still_reads_only_the_prefix(self) -> None:
        """验证服务端返回完整响应时客户端最多读取256KiB。"""
        source, ranges = self.sample_source("full-response", ignore_range=True)
        received = 0

        def open_response(request: Request, *, timeout: float) -> HTTPResponse:
            """记录真实HTTP响应每次交给采样器的数据量。"""
            response: HTTPResponse = urlopen(request, timeout=timeout)
            read = response.read1

            def read_prefix(size: int = -1) -> bytes:
                """读取响应片段并累计已消费字节。"""
                nonlocal received
                chunk = read(size)
                received += len(chunk)
                return chunk

            response.read1 = read_prefix  # type: ignore[method-assign]
            return response

        with patch.object(installation, "urlopen", side_effect=open_response):
            self.assertGreater(installation._sample_download(source.wheel_base_url + installation.PIP_WHEEL_PATH), 0)
        self.assertEqual(received, 256 * 1024)
        self.assertEqual(ranges, ["bytes=0-262143"])

    def test_slow_stream_stops_sampling_without_waiting_for_a_full_chunk(self) -> None:
        """验证采样期限在小块数据持续到达时生效。"""
        source, _ = self.sample_source("slow", delay=0.1)
        started = time.monotonic()
        with patch.object(installation, "_SAMPLE_SECONDS", 0.15):
            self.assertGreater(installation._sample_download(source.wheel_base_url + installation.PIP_WHEEL_PATH), 0)
        self.assertLess(time.monotonic() - started, 0.7)

    def test_slow_headers_still_allow_body_sampling(self) -> None:
        """验证响应头等待超过采样时段后仍读取正文，评分包含连接耗时。"""
        source, _ = self.sample_source("slow-headers", header_delay=0.1)
        with patch.object(installation, "_SAMPLE_SECONDS", 0.05):
            speed = installation._sample_download(source.wheel_base_url + installation.PIP_WHEEL_PATH)
        self.assertGreater(speed, 0)
        self.assertLess(speed, 256 * 1024 / 0.1)

    def test_npm_ranks_file_throughput_and_keeps_unavailable_source(self) -> None:
        """验证npm复用文件前缀测速，并保留失败来源供正式安装诊断。"""
        slow, _ = self.sample_source("slow", delay=0.01)
        fast, _ = self.sample_source("fast")
        missing, _ = self.sample_source("missing", unavailable=True)
        with patch.object(installation, "NPM_REGISTRIES", (slow.wheel_base_url, fast.wheel_base_url)):
            self.assertEqual(rank_npm_registries(), [fast.wheel_base_url, slow.wheel_base_url])
        with patch.object(installation, "NPM_REGISTRIES", (missing.wheel_base_url, fast.wheel_base_url)):
            self.assertEqual(rank_npm_registries(), [fast.wheel_base_url, missing.wheel_base_url])


class InstallerProcessTests(RuntimeTestCase):
    def setUp(self) -> None:
        """准备实际安装子进程使用的隔离目录。"""
        super().setUp()
        self.runtime.prepare()

    def test_ensurepip_preserves_chinese_paths_with_local_encoding(self) -> None:
        """验证全新中文空格venv的ensurepip日志保真且安装后的pip可加载。"""
        workspace = self.runtime.workspace / "安装 中文 空格"
        workspace.mkdir()
        runtime = Runtime(workspace, self.runtime.skill_root)
        runtime.prepare()
        environment = runtime.path(".venv")
        venv.EnvBuilder(with_pip=False).create(environment)
        python = environment / "Scripts/python.exe"
        log = io.StringIO()
        with redirect_stderr(io.StringIO()):
            result = run_installer(runtime, [str(python), "-I", "-m", "ensurepip", "--default-pip"],
                                   log, encoding=locale.getencoding())
        self.assertEqual(result, 0, log.getvalue())
        self.assertIn("安装 中文 空格", log.getvalue())
        self.assertNotIn("\ufffd", log.getvalue())
        installed = run_process(runtime, [str(python), "-I", "-c", "import pip; print(pip.__version__)"])
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertRegex(installed.stdout.strip(), r"^\d+\.\d+")

    def test_progress_is_flushed_before_exit_and_stdout_stays_empty(self) -> None:
        """验证等待中的安装进程持续交付日志并保留退出码。"""
        flushed = threading.Event()

        class ProgressLog(io.StringIO):
            def flush(self) -> None:
                """通知测试首行已交给日志接收方。"""
                super().flush()
                flushed.set()

        release = self.runtime.root / "release-install"
        code = (
            "import pathlib, sys, time\n"
            "print('开始下载', flush=True)\n"
            "deadline = time.monotonic() + 10\n"
            "while not pathlib.Path(sys.argv[1]).exists() and time.monotonic() < deadline:\n"
            "    time.sleep(0.01)\n"
            "print('安装结束', file=sys.stderr, flush=True)\n"
            "sys.exit(7)\n"
        )
        log = ProgressLog()
        output, progress = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(progress), ThreadPoolExecutor(max_workers=1) as worker:
            result = worker.submit(run_installer, self.runtime,
                                   [sys.executable, "-I", "-X", "utf8", "-u", "-c", code, str(release)], log)
            try:
                self.assertTrue(flushed.wait(5))
                self.assertEqual(log.getvalue(), "开始下载\n")
                self.assertFalse(result.done())
            finally:
                release.touch()
            self.assertEqual(result.result(timeout=5), 7)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(progress.getvalue(), "开始下载\n安装结束\n")
        self.assertEqual(log.getvalue(), progress.getvalue())

    def test_arguments_remain_data_and_child_uses_workspace(self) -> None:
        """验证带命令符号的参数原样传递并使用工作区作为当前目录。"""
        argument = '名称 "test" & echo unsafe > executed.txt | $() ; `value`'
        code = "import json, os, sys; print(json.dumps([sys.argv[1:], os.getcwd()]))"
        log = io.StringIO()
        with redirect_stderr(io.StringIO()), \
                patch.object(installation.subprocess, "run", side_effect=AssertionError("正常结束无需终止进程")):
            result = run_installer(self.runtime, [sys.executable, "-I", "-c", code, argument], log)
        arguments, directory = json.loads(log.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(arguments, [argument])
        self.assertEqual(Path(directory), self.runtime.workspace)
        self.assertFalse((self.runtime.workspace / "executed.txt").exists())

    def test_json_stdout_is_separate_from_live_stderr(self) -> None:
        """验证结构化stdout独立保存，stderr实时写日志且保留调用方文件句柄。"""
        log, progress = io.StringIO(), io.StringIO()
        code = "import json,sys; print('下载失败', file=sys.stderr); print(json.dumps({'error':{'code':'E503'}})); sys.exit(1)"
        with TemporaryFile(mode="w+", encoding="utf-8", dir=self.runtime.path(".runtime/tmp")) as output:
            with redirect_stderr(progress):
                result = run_installer(self.runtime, [sys.executable, "-I", "-X", "utf8", "-c", code], log,
                                       stdout_file=output)
            self.assertFalse(output.closed)
            output.seek(0)
            self.assertEqual(json.load(output), {"error": {"code": "E503"}})
        self.assertEqual(result, 1)
        self.assertEqual(log.getvalue(), "下载失败\n")
        self.assertEqual(progress.getvalue(), log.getvalue())

    def test_interruption_and_log_failure_reap_the_process(self) -> None:
        """验证用户中断或写日志异常同时结束启动器与已经就绪的实际worker。"""
        kernel = None
        if os.name == "nt":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        for error in (KeyboardInterrupt(), OSError("synthetic log failure")):
            with self.subTest(error=type(error).__name__):
                processes: list[subprocess.Popen[str]] = []
                actual_pids: list[int] = []
                handles = []
                start = subprocess.Popen

                def record_process(argv: list[str], **kwargs: Any) -> subprocess.Popen[str]:
                    """保存实际启动的子进程供生命周期断言使用。"""
                    process: subprocess.Popen[str] = start(argv, **kwargs)
                    if argv[0] == sys.executable:
                        processes.append(process)
                    return process

                class FailingLog(io.StringIO):
                    def write(self, text: str) -> int:
                        """取得真实worker句柄后模拟用户中断或日志写入失败。"""
                        actual_pids.append(int(text.strip()))
                        if kernel is not None:
                            handle = kernel.OpenProcess(0x00100001, False, actual_pids[-1])
                            if not handle:
                                raise AssertionError("无法持有本例实际worker的句柄")
                            handles.append(handle)
                        raise error

                code = "import os,time; print(os.getpid(), flush=True); time.sleep(30)"
                try:
                    with patch.object(installation.subprocess, "Popen", side_effect=record_process):
                        with self.assertRaises(type(error)):
                            run_installer(self.runtime, [sys.executable, "-I", "-u", "-c", code], FailingLog())
                    self.assertEqual(len(processes), 1)
                    self.assertIsNotNone(processes[0].returncode)
                    self.assertIsNotNone(processes[0].stdout)
                    assert processes[0].stdout is not None
                    self.assertTrue(processes[0].stdout.closed)
                    if kernel is not None:
                        self.assertEqual(kernel.WaitForSingleObject(handles[0], 0), 0)
                        if sys.prefix != sys.base_prefix:
                            self.assertNotEqual(processes[0].pid, actual_pids[0])
                finally:
                    if kernel is not None:
                        for handle in handles:
                            if kernel.WaitForSingleObject(handle, 0) == 0x102:
                                kernel.TerminateProcess(handle, 1)
                                kernel.WaitForSingleObject(handle, 2000)
                            kernel.CloseHandle(handle)
                    for process in processes:
                        if process.poll() is None:
                            process.kill()
                        process.wait(timeout=5)

    @unittest.skipUnless(os.name == "nt", "Windows安装使用taskkill结束进程树")
    def test_taskkill_failure_reports_the_owned_pid_and_closes_output(self) -> None:
        """验证进程树清理失败明确报告本次PID并关闭输出管道。"""
        process = Mock(pid=12345)
        process.poll.return_value = None
        process.stdout = io.StringIO("ready\n")
        log = Mock()
        log.write.side_effect = OSError("synthetic log failure")
        with patch.object(installation.subprocess, "Popen", return_value=process), \
                patch.object(installation.subprocess, "run", return_value=subprocess.CompletedProcess([], 5)) as stop:
            with self.assertRaisesRegex(SetupError, "PID 12345，退出码 5"):
                run_installer(self.runtime, [sys.executable, "-I", "-c", "pass"], log)
        self.assertEqual(stop.call_args.args[0], [
            str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"), "/PID", "12345", "/T", "/F",
        ])
        self.assertFalse(stop.call_args.kwargs["shell"])
        self.assertEqual(stop.call_args.kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)
        process.kill.assert_not_called()
        process.wait.assert_not_called()
        self.assertTrue(process.stdout.closed)

    def test_start_failure_has_a_setup_error(self) -> None:
        """验证找不到安装命令时返回环境错误。"""
        with self.assertRaisesRegex(SetupError, "无法启动子进程"):
            run_installer(self.runtime, [str(self.runtime.root / "missing-installer.exe")], io.StringIO())
