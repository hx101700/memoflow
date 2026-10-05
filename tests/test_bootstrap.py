import json
import locale
import shutil
import subprocess
import sys
from unittest.mock import patch

from asr_runtime import BAILIAN_VERSION
from asr_runtime.application.bootstrap import _install_bailian, bootstrap
from asr_runtime.utils.environment import SetupError, locked_python_versions, run_process
from asr_runtime.utils.installation import NPM_REGISTRIES, PIP_SHA256, PIP_VERSION, PYTHON_INDEXES
from tests.support import RuntimeTestCase


class BootstrapTests(RuntimeTestCase):
    def setUp(self):
        """准备依赖锁、安装目录和命令替身。"""
        super().setUp()
        python = self.runtime.path(".venv/Scripts/python.exe")
        python.parent.mkdir(parents=True)
        python.touch()
        self.runtime.path(".venv/pyvenv.cfg").touch()
        self.runtime.path(".venv/Lib/site-packages/pip").mkdir(parents=True)
        self.runtime.bl_entry.parent.mkdir(parents=True)
        self.runtime.bl_entry.touch()
        self.manifest = self.runtime.path(".tools/bailian/node_modules/bailian-cli/package.json")
        self.manifest.write_text(json.dumps({"version": BAILIAN_VERSION}), encoding="utf-8")
        for name, value in (
            ("check_python", None),
            ("check_node", (self.runtime.root / "node.exe", "v24.19.0")),
            ("npm_entry", self.runtime.root / "npm-cli.js"),
            ("verify_bl_installation", None),
            ("rank_python_indexes", list(PYTHON_INDEXES)),
            ("rank_npm_registries", list(NPM_REGISTRIES)),
        ):
            patcher = patch(f"asr_runtime.application.bootstrap.{name}", return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.expected = locked_python_versions(self.runtime)
        installer = patch("asr_runtime.application.bootstrap.run_installer", return_value=0)
        self.install = installer.start()
        self.addCleanup(installer.stop)

    def test_complete_environment_skips_pip_and_npm_install(self):
        """验证完整环境跳过pip和npm安装。"""
        with patch("asr_runtime.application.bootstrap.installed_python_versions", return_value=self.expected), \
             patch("asr_runtime.application.bootstrap.npm_entry", side_effect=AssertionError("已有BL不需要npm")), \
             patch("asr_runtime.application.bootstrap.run_process", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            report = bootstrap(self.runtime)
        self.assertEqual(report["status"], "already_installed")
        self.assertEqual(run.call_count, 1)
        self.assertNotIn("pip", run.call_args.args[1])
        self.install.assert_not_called()

    def test_python_version_check_ignores_workspace_sysconfig(self):
        """验证真实版本检查使用标准库并保留工作区同名源码。"""
        shadow = self.runtime.workspace / "sysconfig.py"
        shadow.write_text("from pathlib import Path\nPath('sysconfig-executed').touch()\n"
                          "raise RuntimeError('workspace module executed')\n", encoding="utf-8")

        def execute_version(runtime, argv, **kwargs):
            """用当前测试解释器及其基础目录执行生产版本检查。"""
            return run_process(runtime, [sys.executable, *argv[1:-1], sys.base_prefix], **kwargs)

        with patch("asr_runtime.application.bootstrap.installed_python_versions", return_value=self.expected), \
             patch("asr_runtime.application.bootstrap.run_process", side_effect=execute_version):
            report = bootstrap(self.runtime)
        self.assertEqual(report["status"], "already_installed")
        self.assertFalse((self.runtime.workspace / "sysconfig-executed").exists())

    def test_venv_bound_to_another_python_is_preserved(self):
        """验证旧系统解释器绑定被拒绝，保留venv并停止依赖安装。"""
        marker = self.runtime.path(".venv/existing-environment")
        marker.write_text("keep", encoding="utf-8")

        def execute_version(runtime, argv, **kwargs):
            """用真实测试解释器验证不同的工作区基础目录会被拒绝。"""
            self.assertEqual(argv[-1], str(runtime.base_python.parent))
            return run_process(runtime, [sys.executable, *argv[1:]], **kwargs)

        with patch("asr_runtime.application.bootstrap.run_process", side_effect=execute_version):
            with self.assertRaisesRegex(SetupError, "未绑定本地.*CPython 3.12"):
                bootstrap(self.runtime)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        self.install.assert_not_called()

    def test_ensurepip_and_pip_use_isolated_python(self):
        """验证ensurepip使用本地编码解码，pip使用显式UTF-8，均保持隔离。"""
        self.runtime.path(".venv/Lib/site-packages/pip").rmdir()
        with patch("asr_runtime.application.bootstrap.installed_python_versions", side_effect=[None, self.expected]), \
             patch("asr_runtime.application.bootstrap.run_process", return_value=subprocess.CompletedProcess([], 0, PIP_VERSION, "")):
            bootstrap(self.runtime)
        commands = [call.args[1] for call in self.install.call_args_list]
        self.assertEqual(commands[0][1:4], ["-I", "-m", "ensurepip"])
        self.assertEqual(self.install.call_args_list[0].kwargs["encoding"], locale.getencoding())
        self.assertTrue(all(command[1:6] == ["-I", "-X", "utf8", "-m", "pip"] for command in commands[1:]))

    def test_conflicting_bl_is_rejected_before_python_mutation(self):
        """验证BL版本冲突在修改Python环境前停止。"""
        self.manifest.write_text(json.dumps({"version": "0.0.0"}), encoding="utf-8")
        with patch("asr_runtime.application.bootstrap.run_process") as run:
            with self.assertRaisesRegex(SetupError, "BL安装不匹配"):
                bootstrap(self.runtime)
        run.assert_not_called()
        self.assertFalse(self.runtime.path(".runtime").exists())

    def test_corrupt_lock_stops_before_install(self):
        """验证损坏依赖锁在安装前停止。"""
        self.runtime.resource("scripts/bailian/package-lock.json").write_text("[]", encoding="utf-8")
        with patch("asr_runtime.application.bootstrap.run_process") as run:
            with self.assertRaisesRegex(SetupError, "锁文件"):
                bootstrap(self.runtime)
        run.assert_not_called()

    def test_python_install_is_followed_by_dependency_check(self):
        """验证Python安装完成后检查实际依赖。"""
        with patch("asr_runtime.application.bootstrap.installed_python_versions", side_effect=[None, self.expected]) as inspect, \
             patch("asr_runtime.application.bootstrap.run_process", return_value=subprocess.CompletedProcess([], 0, PIP_VERSION, "")):
            bootstrap(self.runtime)
        self.assertEqual(inspect.call_count, 2)
        download_args = self.install.call_args_list[0].args[1]
        self.assertIn("--require-hashes", download_args)
        self.assertEqual(download_args[download_args.index("--resume-retries") + 1], "5")
        self.assertEqual(download_args[download_args.index("--timeout") + 1], "120")
        self.assertEqual(download_args[download_args.index("--index-url") + 1], PYTHON_INDEXES[0].index_url)
        install_args = self.install.call_args_list[1].args[1]
        self.assertIn("--no-index", install_args)
        self.assertIn("--require-hashes", install_args)
        self.assertEqual(self.install.call_count, 2)

    def test_pip_success_without_working_dependencies_is_not_success(self):
        """验证pip成功但依赖检查失败时返回安装错误。"""
        with patch("asr_runtime.application.bootstrap.installed_python_versions", return_value=None), \
             patch("asr_runtime.application.bootstrap.run_process", return_value=subprocess.CompletedProcess([], 0, PIP_VERSION, "")):
            with self.assertRaisesRegex(SetupError, "依赖校验失败"):
                bootstrap(self.runtime)
        self.assertEqual(self.install.call_count, 2)

    def test_both_download_sources_failing_stops_before_install(self):
        """验证两个来源均失败后停止下载，不开始本机安装或BL安装。"""
        self.install.return_value = 1
        with patch("asr_runtime.application.bootstrap.installed_python_versions", return_value=None), \
             patch("asr_runtime.application.bootstrap.run_process", return_value=subprocess.CompletedProcess([], 0, PIP_VERSION, "")):
            with self.assertRaisesRegex(SetupError, "已尝试两个来源"):
                bootstrap(self.runtime)
        commands = [call.args[1] for call in self.install.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertTrue(all("download" in command for command in commands))
        log = self.runtime.path(".runtime/python-install.log").read_text(encoding="utf-8")
        self.assertTrue(all(index.name in log for index in PYTHON_INDEXES))

    def test_failed_first_source_uses_second_then_installs_offline(self) -> None:
        """验证首选源失败后只切换一次，下载完成后使用本机文件安装。"""
        self.install.side_effect = [1, 0, 0]
        with patch("asr_runtime.application.bootstrap.installed_python_versions", side_effect=[None, self.expected]), \
             patch("asr_runtime.application.bootstrap.run_process", return_value=subprocess.CompletedProcess([], 0, PIP_VERSION, "")):
            bootstrap(self.runtime)
        commands = [call.args[1] for call in self.install.call_args_list]
        for command, index in zip(commands[:2], PYTHON_INDEXES):
            self.assertEqual(command[command.index("--index-url") + 1], index.index_url)
        self.assertIn("--no-index", commands[2])
        self.assertNotIn("--index-url", commands[2])

    def test_local_install_failure_does_not_download_again(self) -> None:
        """验证文件已下载但本机安装失败时直接报告，避免重复换源。"""
        self.install.side_effect = [0, 1]
        with patch("asr_runtime.application.bootstrap.installed_python_versions", return_value=None), \
             patch("asr_runtime.application.bootstrap.run_process", return_value=subprocess.CompletedProcess([], 0, PIP_VERSION, "")):
            with self.assertRaisesRegex(SetupError, "本机安装失败"):
                bootstrap(self.runtime)
        self.assertEqual(self.install.call_count, 2)

    def test_bundled_pip_is_upgraded_from_a_hash_locked_wheel(self) -> None:
        """验证旧pip先获取锁定工具包，再用新版公开参数下载业务依赖。"""
        with patch("asr_runtime.application.bootstrap.installed_python_versions", side_effect=[None, self.expected]), \
             patch("asr_runtime.application.bootstrap.run_process", return_value=subprocess.CompletedProcess([], 0, "23.2.1", "")):
            bootstrap(self.runtime)
        commands = [call.args[1] for call in self.install.call_args_list]
        self.assertEqual(len(commands), 4)
        self.assertTrue(commands[0][-1].endswith("#sha256=" + PIP_SHA256))
        self.assertNotIn("--resume-retries", commands[0])
        self.assertTrue(commands[1][-1].startswith("file:///"))
        self.assertTrue(commands[1][-1].endswith("#sha256=" + PIP_SHA256))
        self.assertIn("--resume-retries", commands[2])

    def test_installs_locked_python_wheels_and_native_npm_lock(self):
        """验证Python经锁定下载后在本机安装，npm复用现有依赖锁。"""
        shutil.rmtree(self.runtime.bl_directory)
        node = self.runtime.root / "node.exe"
        npm = self.runtime.root / "npm-cli.js"
        python = self.runtime.path(".venv/Scripts/python.exe")
        calls = []

        def run(_runtime, argv, _log, **kwargs):
            """记录安装命令并模拟对应依赖落盘。"""
            calls.append(argv)
            if "ci" in argv:
                entry = self.runtime.bl_entry
                entry.parent.mkdir(parents=True, exist_ok=True)
                entry.touch()
                manifest = entry.parents[1] / "package.json"
                manifest.write_text(json.dumps({"version": BAILIAN_VERSION}), encoding="utf-8")
            return 0

        with patch("asr_runtime.application.bootstrap.check_python"), \
             patch("asr_runtime.application.bootstrap.check_node", return_value=(node, "v24.0.0")), \
             patch("asr_runtime.application.bootstrap.npm_entry", return_value=npm), \
             patch("asr_runtime.application.bootstrap.venv.EnvBuilder.create", side_effect=lambda path: (
                 python.parent.mkdir(parents=True),
                 (path / "pyvenv.cfg").write_text("home = python\\n", encoding="utf-8"),
                 python.touch(),
             )), \
             patch("asr_runtime.application.bootstrap.installed_python_versions", side_effect=[None, self.expected]), \
             patch("asr_runtime.application.bootstrap.verify_bl_installation") as verify, \
             patch("asr_runtime.application.bootstrap.run_process", return_value=subprocess.CompletedProcess([], 0, PIP_VERSION, "")), \
             patch("asr_runtime.application.bootstrap.run_installer", side_effect=run):
            result = bootstrap(self.runtime)

        self.assertEqual(result["status"], "installed")
        verify.assert_called_once_with(self.runtime)
        pip = next(argv for argv in calls if "download" in argv)
        self.assertIn("--require-hashes", pip)
        self.assertIn("--retries", pip)
        self.assertEqual(pip[pip.index("--retries") + 1], "2")
        self.assertEqual(pip[pip.index("--index-url") + 1], PYTHON_INDEXES[0].index_url)
        npm_command = next(argv for argv in calls if "ci" in argv)
        self.assertEqual(npm_command[:3], [str(node), str(npm), "ci"])
        self.assertIn("--prefix", npm_command)
        self.assertIn("--fetch-retries=2", npm_command)
        self.assertIn("--prefer-offline", npm_command)
        self.assertEqual(npm_command[npm_command.index("--registry") + 1], NPM_REGISTRIES[0])

    def test_existing_nonempty_destination_stops_without_retry(self):
        """验证非空BL目标目录保留原内容并拒绝安装。"""
        destination = self.runtime.bl_directory
        shutil.rmtree(destination)
        destination.mkdir(parents=True)
        (destination / "partial").touch()
        with patch("asr_runtime.application.bootstrap.check_python"), \
             patch("asr_runtime.application.bootstrap.check_node", return_value=(self.runtime.root / "node.exe", "v24.0.0")), \
             patch("asr_runtime.application.bootstrap.npm_entry", return_value=self.runtime.root / "npm.js"), \
             patch("asr_runtime.application.bootstrap.run_process") as run:
            with self.assertRaisesRegex(SetupError, "非空"):
                bootstrap(self.runtime)
        run.assert_not_called()

    def test_npm_download_failure_switches_once_in_ranked_order(self):
        """验证下载错误切换到测速给出的第二来源，并保留同一个锁和缓存位置。"""
        self.runtime.prepare()
        registries = list(reversed(NPM_REGISTRIES))

        def install(_runtime, argv, _log, *, stdout_file):
            """模拟第一个来源返回结构化下载错误，第二个完成安装。"""
            if argv[argv.index("--registry") + 1] == registries[0]:
                json.dump({"error": {"code": "E503"}}, stdout_file)
                return 1
            return 0

        self.install.side_effect = install
        with patch("asr_runtime.application.bootstrap.rank_npm_registries", return_value=registries):
            _install_bailian(self.runtime, self.runtime.root / "node.exe", self.runtime.root / "npm-cli.js")
        commands = [call.args[1] for call in self.install.call_args_list]
        self.assertEqual([command[command.index("--registry") + 1] for command in commands], registries)
        self.assertTrue(all("--fetch-retries=2" in command and "--json" in command for command in commands))
        self.assertEqual(len({command[command.index("--prefix") + 1] for command in commands}), 1)

    def test_npm_local_or_unknown_failure_stops_without_switching(self):
        """验证权限、磁盘、锁冲突和不明回执直接停止，避免无效换源。"""
        self.runtime.prepare()
        reports = [json.dumps({"error": {"code": code}}) for code in ("EPERM", "EACCES", "ENOSPC", "EUSAGE", "UNKNOWN")]
        for report in [*reports, "not json", "{}", '{"error":{"code":[]}}']:
            with self.subTest(report=report):
                self.install.reset_mock()

                def fail_install(_runtime, _argv, _log, *, stdout_file):
                    """提供本次安装失败的独立结构化结果。"""
                    stdout_file.write(report)
                    return 1

                self.install.side_effect = fail_install
                with self.assertRaisesRegex(SetupError, "npm安装失败"):
                    _install_bailian(self.runtime, self.runtime.root / "node.exe", self.runtime.root / "npm-cli.js")
                self.install.assert_called_once()
