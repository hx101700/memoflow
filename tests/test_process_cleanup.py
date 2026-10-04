"""验证遗留临时文件清理所需的进程状态与Python临时目录边界。"""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import Mock, patch

from openpyxl import Workbook

from asr_runtime.utils.environment import (
    child_environment, process_is_running, python_temporary_directory,
)
from tests.support import ROOT, RuntimeTestCase


class ProcessCleanupTests(RuntimeTestCase):
    def test_running_child_and_its_exit_are_distinguished(self):
        """用本例启动的进程核对运行中和退出后的真实状态。"""
        if os.name != "nt":
            self.skipTest("进程状态查询适用于Windows")
        with subprocess.Popen(
            [sys.executable, "-I", "-c", "import sys; sys.stdin.buffer.read(1)"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ) as child:
            try:
                self.assertIs(process_is_running(child.pid), True)
                child.communicate(b"x", timeout=10)
                self.assertEqual(child.returncode, 0)
                self.assertIs(process_is_running(child.pid), False)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=10)

    def test_unknown_process_access_preserves_files(self):
        """验证权限拒绝和未知错误返回未知，已不存在的进程返回False。"""
        kernel = Mock()
        kernel.OpenProcess.return_value = None
        for code, expected in ((5, None), (87, False), (0, None)):
            with self.subTest(code=code), \
                    patch("asr_runtime.utils.environment.os.name", "nt"), \
                    patch("asr_runtime.utils.environment.ctypes.WinDLL", return_value=kernel), \
                    patch("asr_runtime.utils.environment.ctypes.get_last_error", return_value=code):
                self.assertIs(process_is_running(4321), expected)
        kernel.OpenProcess.assert_called_with(0x00100000, False, 4321)
        kernel.WaitForSingleObject.assert_not_called()
        kernel.CloseHandle.assert_not_called()

    def test_process_handle_is_closed_for_every_wait_result(self):
        """验证进程等待结果按存活、结束和未知分类且始终释放句柄。"""
        for state, expected in ((0x102, True), (0, False), (0xFFFFFFFF, None)):
            kernel = Mock()
            kernel.OpenProcess.return_value = 23
            kernel.WaitForSingleObject.return_value = state
            with self.subTest(state=state), \
                    patch("asr_runtime.utils.environment.os.name", "nt"), \
                    patch("asr_runtime.utils.environment.ctypes.WinDLL", return_value=kernel):
                self.assertIs(process_is_running(4321), expected)
            kernel.WaitForSingleObject.assert_called_once_with(23, 0)
            kernel.CloseHandle.assert_called_once_with(23)

    def test_unsupported_platform_and_invalid_pids_are_unknown(self):
        """验证非法编号与未支持的平台均保持未知状态。"""
        with patch("asr_runtime.utils.environment.os.name", "nt"), \
                patch("asr_runtime.utils.environment.ctypes.WinDLL") as library:
            for pid in (-1, 0, 0x100000000, True, "1", None):
                with self.subTest(pid=pid):
                    self.assertIsNone(process_is_running(pid))
            library.assert_not_called()
        with patch("asr_runtime.utils.environment.os.name", "posix"):
            self.assertIsNone(process_is_running(4321))

    def test_python_scope_contains_library_scratch_and_restores_settings(self):
        """验证openpyxl临时文件进入进程目录且不改变子进程环境。"""
        previous = tempfile.tempdir
        environment = dict(os.environ)
        child_env = child_environment(self.runtime)
        with python_temporary_directory(self.runtime):
            directory = Path(tempfile.gettempdir())
            self.assertEqual(directory.parent, self.runtime.path(".runtime/tmp"))
            self.assertTrue(directory.name.startswith(f"python-{os.getpid()}-"))
            workbook = Workbook(write_only=True)
            sheet = workbook.create_sheet()
            sheet.append(["synthetic hotword"])
            self.assertTrue(list(directory.glob("openpyxl.*")))
            workbook.save(io.BytesIO())
            self.assertEqual(dict(os.environ), environment)
            self.assertEqual(child_environment(self.runtime), child_env)
        self.assertEqual(tempfile.tempdir, previous)
        self.assertFalse(directory.exists())

    def test_python_scope_cleans_after_an_exception(self):
        """验证操作异常时恢复临时目录设置并清理本进程文件。"""
        previous = tempfile.tempdir
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            with python_temporary_directory(self.runtime):
                directory = Path(tempfile.gettempdir())
                with tempfile.NamedTemporaryFile(delete=False) as scratch:
                    scratch.write(b"synthetic temporary content")
                raise RuntimeError("synthetic failure")
        self.assertEqual(tempfile.tempdir, previous)
        self.assertFalse(directory.exists())

    def test_abrupt_child_exit_leaves_an_identifiable_owned_directory(self):
        """验证异常进程退出遗留文件仍可按目录中的PID定位。"""
        script = (
            "import json, os, sys, tempfile\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from asr_runtime.utils.environment import Runtime, python_temporary_directory\n"
            "runtime = Runtime(Path(sys.argv[2]), Path(sys.argv[3]))\n"
            "with python_temporary_directory(runtime):\n"
            "    directory = Path(tempfile.gettempdir())\n"
            "    (directory / 'scratch.tmp').write_text('synthetic', encoding='utf-8')\n"
            "    print(json.dumps({'pid': os.getpid(), 'path': str(directory)}), flush=True)\n"
            "    os._exit(0)\n"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-c", script,
             str(ROOT / "skills/asr-transcription/scripts"),
             str(self.runtime.workspace), str(self.runtime.skill_root)],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        directory = Path(report["path"])
        self.assertEqual(directory.parent, self.runtime.path(".runtime/tmp"))
        self.assertTrue(directory.name.startswith(f"python-{report['pid']}-"))
        self.assertEqual((directory / "scratch.tmp").read_text(encoding="utf-8"), "synthetic")
        if os.name == "nt":
            self.assertIs(process_is_running(report["pid"]), False)
