import contextlib
import ctypes
from ctypes import wintypes
import io
import json
import os
import subprocess
import sys
from unittest.mock import Mock, patch

from asr_runtime import BAILIAN_VERSION
from asr_runtime.application.bootstrap import bootstrap
from asr_runtime.utils.environment import Runtime, SetupError, child_environment, check_node, check_python, find_node, installed_python_versions, locked_python_versions, run_process
from asr_runtime.utils.bailian import bl_command, verify_bl_installation
from asr_runtime.application.diagnostics import doctor
from scripts.probe_bl import SYNTHETIC_AUDIO_URL, probe
from scripts.probe_bl import main as probe_main
from asr_runtime.__main__ import main as runtime_main
from tests.support import RuntimeTestCase


class EnvironmentTests(RuntimeTestCase):
    def test_runtime_separates_resources_private_state_and_outputs(self):
        """验证 Skill 资源、私有状态及默认结果分别定位。"""
        self.assertEqual(self.runtime.root, self.runtime.workspace / ".asr-transcription")
        self.assertEqual(self.runtime.resource("scripts/requirements.txt"),
                         self.runtime.skill_root / "scripts/requirements.txt")
        self.assertEqual(self.runtime.output_root, self.runtime.workspace / "transcriptions")
        self.assertEqual(self.runtime.base_python, self.runtime.root / ".tools/python/python.exe")
        self.assertEqual(self.runtime.node_entry, self.runtime.root / ".tools/node/node.exe")
        with self.assertRaises(SetupError):
            self.runtime.resource("../workspace/.env")

    def test_runtime_requires_existing_workspace_outside_skill(self):
        """验证运行工作区必须存在且位于 Skill 安装目录之外。"""
        for workspace in (self.temporary_root / "missing", self.runtime.skill_root,
                          self.runtime.skill_root / "scripts"):
            with self.subTest(workspace=workspace), self.assertRaises(SetupError):
                Runtime(workspace, self.runtime.skill_root)

    def test_runtime_rejects_skill_inside_private_state_before_writing(self):
        """验证私有运行根等于或包含Skill时在构造阶段停止。"""
        for relative in (".asr-transcription", ".asr-transcription/installed-skill"):
            skill = self.runtime.workspace / relative
            skill.mkdir(parents=True, exist_ok=True)
            with self.subTest(relative=relative), self.assertRaisesRegex(SetupError, "重叠"):
                Runtime(self.runtime.workspace, skill)
        self.assertFalse((self.runtime.root / ".runtime").exists())

    def test_runtime_allows_a_project_skill_outside_private_state(self):
        """验证工作区内的常规项目Skill与私有运行目录独立。"""
        skill = self.runtime.workspace / ".agents/skills/asr-transcription"
        skill.mkdir(parents=True)
        runtime = Runtime(self.runtime.workspace, skill)
        runtime.prepare()
        self.assertEqual(runtime.root, self.runtime.workspace / ".asr-transcription")
        self.assertEqual(list(skill.iterdir()), [])

    def test_runtime_rechecks_a_directory_redirected_into_skill(self):
        """验证构造后的目录联接变更仍不能把运行或输出写入Skill。"""
        if os.name != "nt":
            self.skipTest("目录联接测试适用于Windows")
        from _winapi import CreateJunction

        skill = self.runtime.workspace / ".agents/skills/asr-transcription"
        skill.mkdir(parents=True)
        runtime = Runtime(self.runtime.workspace, skill)
        junction = self.runtime.workspace / ".asr-transcription"
        junction.rmdir()
        CreateJunction(str(skill), str(junction))
        try:
            with self.assertRaisesRegex(SetupError, "重叠"):
                runtime.prepare()
            with self.assertRaisesRegex(SetupError, "程序资源"):
                runtime.check_output_path(junction / "result.docx")
            self.assertEqual(list(skill.iterdir()), [])
        finally:
            junction.rmdir()

    def test_output_path_protects_skill_and_accepts_other_save_locations(self):
        """验证Skill资源不能用作输出目标，其余保存位置保持可用。"""
        for path in (self.runtime.skill_root, self.runtime.skill_root / "outputs/result.docx"):
            with self.subTest(path=path), self.assertRaisesRegex(SetupError, "程序资源"):
                self.runtime.check_output_path(path)
        for path in (self.runtime.output_root, self.runtime.root / "exports", self.temporary_root / "chosen"):
            with self.subTest(path=path):
                self.runtime.check_output_path(path)

    def test_dependency_probe_ignores_workspace_python_modules(self):
        """验证真实依赖子进程从venv加载库，跳过工作区同名模块。"""
        self.runtime.prepare()
        python = self.runtime.path(".venv/Scripts/python.exe")
        python.parent.mkdir(parents=True)
        python.touch()
        for name in ("json", "sysconfig"):
            (self.runtime.workspace / f"{name}.py").write_text(
                f"from pathlib import Path\nPath('{name}-executed').touch()\n"
                "raise RuntimeError('workspace module executed')\n", encoding="utf-8")

        def execute_probe(runtime, argv, **kwargs):
            """用当前测试venv执行生产探针参数。"""
            return run_process(runtime, [sys.executable, *argv[1:]], **kwargs)

        with patch("asr_runtime.utils.environment.run_process", side_effect=execute_probe):
            versions = installed_python_versions(self.runtime, {"openpyxl": "3.1.5"})
        self.assertEqual(versions, {"openpyxl": "3.1.5"})
        for name in ("json", "sysconfig"):
            self.assertFalse((self.runtime.workspace / f"{name}-executed").exists())

    def test_runtime_cli_rejects_development_probe(self):
        """验证用户命令入口拒绝开发合约探针。"""
        with contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as stopped:
                runtime_main(["--workspace", str(self.runtime.workspace), "probe-bl"])
        self.assertEqual(stopped.exception.code, 2)
        self.assertIn("invalid choice", error.getvalue())

    def test_development_probe_rejects_audio_arguments(self):
        """验证开发探针的独立入口拒绝外部音频参数。"""
        with patch("scripts.probe_bl.probe") as run, \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                probe_main(["--workspace", str(self.runtime.workspace), "--url", "https://example.invalid/another.wav"])
        self.assertEqual(stopped.exception.code, 2)
        run.assert_not_called()

    def test_python_runtime_matches_locked_binary_wheels(self):
        """验证Python平台与锁定二进制依赖匹配。"""
        for version, platform in (((3, 12, 1), "win-amd64"), ((3, 13, 0), "win-amd64"),
                                  ((3, 12, 1), "win32"), ((3, 12, 1), "win-arm64")):
            with self.subTest(version=version, platform=platform), \
                 patch("asr_runtime.utils.environment.sys.version_info", version), \
                 patch("asr_runtime.utils.environment.sysconfig.get_platform", return_value=platform):
                if version[:2] == (3, 12) and platform == "win-amd64":
                    check_python()
                else:
                    with self.assertRaisesRegex(SetupError, "CPython 3.12"):
                        check_python()

    def test_paths_cannot_leave_private_runtime(self):
        """验证私有运行目录外的路径返回范围错误。"""
        with self.assertRaises(SetupError):
            self.runtime.path("../outside")

    def test_child_does_not_inherit_credentials_or_node_injection(self):
        """验证子进程环境按白名单隔离凭据和注入项。"""
        private = {
            "DASHSCOPE_API_KEY": "synthetic-key",
            "DASHSCOPE_BASE_URL": "https://example.invalid",
            "NODE_OPTIONS": "--require unwanted.js",
            "NPM_TOKEN": "synthetic-token",
            "NPM_CONFIG_USERCONFIG": "outside.npmrc",
        }
        with patch.dict(os.environ, private):
            env = child_environment(self.runtime)
        for name in private.keys() - {"NPM_CONFIG_USERCONFIG"}:
            self.assertNotIn(name, env)
        self.assertTrue(env["NPM_CONFIG_USERCONFIG"].startswith(str(self.runtime.root)))
        self.assertEqual(env["DO_NOT_TRACK"], "1")

    def test_probe_does_not_share_login_directory(self):
        """验证探针与登录状态使用独立目录。"""
        normal = child_environment(self.runtime)
        isolated = child_environment(self.runtime, isolated_config=True)
        self.assertNotEqual(normal["BAILIAN_CONFIG_DIR"], isolated["BAILIAN_CONFIG_DIR"])

    def test_nonempty_npm_configuration_is_not_overwritten(self):
        """验证npm隔离配置冲突时保留原内容并报错。"""
        self.runtime.prepare()
        config = self.runtime.path(".runtime/npm-user.npmrc")
        config.write_text("registry=https://example.invalid\n", encoding="utf-8")
        with self.assertRaises(SetupError):
            self.runtime.prepare()
        self.assertIn("example.invalid", config.read_text(encoding="utf-8"))

    def test_failed_subprocess_is_not_retried_and_uses_argument_array(self):
        """验证子进程返回失败退出码且按参数数组调用一次。"""
        process = Mock(returncode=6, stdout=io.StringIO(), stderr=io.StringIO())
        process.communicate.return_value = ("", "network failure")
        process.poll.return_value = 6
        with patch("asr_runtime.utils.environment.subprocess.Popen", return_value=process) as run, \
                patch("asr_runtime.utils.environment.subprocess.run", side_effect=AssertionError("已退出命令无需终止")):
            result = run_process(self.runtime, ["node.exe", "file with spaces.mjs", "--help"])
        self.assertIsInstance(result, subprocess.CompletedProcess)
        self.assertEqual(result.returncode, 6)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "network failure")
        run.assert_called_once()
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(run.call_args.args[0][1], "file with spaces.mjs")
        self.assertEqual(run.call_args.kwargs["cwd"], self.runtime.workspace)
        self.assertEqual(run.call_args.kwargs["env"], child_environment(self.runtime))
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["stdout"], subprocess.PIPE)
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.PIPE)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        process.communicate.assert_called_once_with(timeout=60)
        self.assertTrue(process.stdout.closed)
        self.assertTrue(process.stderr.closed)

    def test_timeout_is_not_retried(self):
        """验证子进程超时返回环境错误且调用次数为一。"""
        process = Mock(stdout=io.StringIO(), stderr=io.StringIO())
        process.communicate.side_effect = subprocess.TimeoutExpired([], 1)
        with patch("asr_runtime.utils.environment.subprocess.Popen", return_value=process) as run, \
                patch("asr_runtime.utils.environment.stop_process_tree") as stop:
            with self.assertRaises(SetupError):
                run_process(self.runtime, ["node.exe"], timeout=1)
        run.assert_called_once()
        stop.assert_called_once_with(process)
        process.communicate.assert_called_once_with(timeout=1)
        self.assertTrue(process.stdout.closed)
        self.assertTrue(process.stderr.closed)

    def test_timeout_ends_the_actual_windows_venv_worker(self):
        """等待实际worker就绪后触发超时，用持有句柄确认启动器和worker均退出。"""
        if os.name != "nt":
            self.skipTest("Windows venv启动器测试")
        self.runtime.prepare()
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        processes, handles, actual_pids = [], [], []
        start = subprocess.Popen

        def record_worker(argv, **kwargs):
            """持有诊断worker的句柄，原生终止工具按正常路径运行。"""
            process = start(argv, **kwargs)
            if argv[0] == sys.executable:
                processes.append(process)
                actual_pid = int(process.stdout.readline().strip())
                actual_pids.append(actual_pid)
                handle = kernel.OpenProcess(0x00100001, False, actual_pid)
                self.assertTrue(handle)
                handles.append(handle)
            return process

        try:
            with patch("asr_runtime.utils.environment.subprocess.Popen", side_effect=record_worker):
                with self.assertRaisesRegex(SetupError, "超时，已停止"):
                    run_process(self.runtime, [sys.executable, "-I", "-u", "-c",
                                "import os,time; print(os.getpid(), flush=True); time.sleep(30)"], timeout=0.05)
            self.assertEqual(len(processes), 1)
            self.assertIsNotNone(processes[0].returncode)
            self.assertEqual(kernel.WaitForSingleObject(handles[0], 0), 0)
            self.assertTrue(processes[0].stdout.closed)
            self.assertTrue(processes[0].stderr.closed)
            if sys.prefix != sys.base_prefix:
                self.assertNotEqual(processes[0].pid, actual_pids[0])
        finally:
            for handle in handles:
                if kernel.WaitForSingleObject(handle, 0) == 0x102:
                    kernel.TerminateProcess(handle, 1)
                    kernel.WaitForSingleObject(handle, 2000)
                kernel.CloseHandle(handle)
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)

    def test_missing_local_bl_does_not_fall_back_to_global(self):
        """验证工作区未安装 BL 时返回安装错误。"""
        with self.assertRaises(SetupError):
            bl_command(self.runtime, ["--version"])

    def test_bl_command_always_disables_automatic_upgrade(self):
        """验证BL命令携带quiet参数。"""
        self.runtime.bl_entry.parent.mkdir(parents=True)
        self.runtime.bl_entry.touch()
        manifest = self.runtime.path(".tools/bailian/node_modules/bailian-cli/package.json")
        manifest.write_text(json.dumps({"version": BAILIAN_VERSION}), encoding="utf-8")
        with patch("asr_runtime.utils.bailian.find_node", return_value=self.runtime.node_entry) as find:
            command = bl_command(self.runtime, ["speech", "recognize", "--dry-run"])
        find.assert_called_once_with(self.runtime)
        self.assertEqual(command[0], str(self.runtime.node_entry))
        self.assertIn("--quiet", command)
        self.assertEqual(command[1], str(self.runtime.bl_entry))

    def test_bootstrap_requires_lock_before_installing(self):
        """验证安装前必须存在依赖锁。"""
        self.runtime.resource("scripts/bailian/package-lock.json").unlink()
        with patch("asr_runtime.application.bootstrap.check_node", return_value=(self.runtime.root / "node.exe", "v24.19.0")), \
             patch("asr_runtime.application.bootstrap.npm_entry", return_value=self.runtime.root / "npm-cli.js"):
            with self.assertRaisesRegex(SetupError, "锁文件"):
                bootstrap(self.runtime)
        self.assertFalse(self.runtime.path(".venv").exists())

    def test_missing_local_node_ignores_path_installation(self):
        """验证PATH中即使存在Node也不能替代缺失的工作区运行时。"""
        outside = self.runtime.workspace / "system-node"
        outside.mkdir()
        (outside / "node.exe").touch()
        with patch.dict(os.environ, {"PATH": str(outside)}):
            with self.assertRaisesRegex(SetupError, "scripts/bootstrap.ps1"):
                find_node(self.runtime)

    def test_node_uses_private_entry_and_child_path(self):
        """验证Node定位及子进程PATH优先使用工作区独立目录。"""
        node = self.runtime.node_entry
        node.parent.mkdir(parents=True)
        node.touch()
        outside = str(self.runtime.workspace / "system-node")
        with patch.dict(os.environ, {"PATH": outside}):
            self.assertEqual(find_node(self.runtime), node)
            env = child_environment(self.runtime)
        self.assertEqual(env["PATH"].split(os.pathsep), [str(node.parent), outside])

    def test_node_version_check_runs_only_private_executable(self):
        """验证Node版本检查使用工作区绝对入口并保留BL最低版本约束。"""
        node = self.runtime.node_entry
        node.parent.mkdir(parents=True)
        node.touch()
        with patch("asr_runtime.utils.environment.run_process",
                   return_value=subprocess.CompletedProcess([], 0, "v24.21.0\n", "")) as run:
            self.assertEqual(check_node(self.runtime), (node, "v24.21.0"))
        run.assert_called_once_with(self.runtime, [str(node), "--version"])

    def test_doctor_identifies_missing_private_python(self):
        """验证诊断给出独立Python预期位置及统一安装入口。"""
        with patch("asr_runtime.application.diagnostics.check_node",
                   side_effect=SetupError("Node unavailable")):
            report = doctor(self.runtime)
        self.assertEqual(report["base_python"], str(self.runtime.base_python))
        self.assertIn("工作区Python尚未安装，请运行Skill的scripts/bootstrap.ps1。", report["issues"])

    def test_doctor_reports_python_bound_outside_workspace(self):
        """验证诊断能指出当前解释器仍使用系统基础目录。"""
        self.runtime.base_python.parent.mkdir(parents=True)
        self.runtime.base_python.touch()
        with patch("asr_runtime.application.diagnostics.check_node",
                   side_effect=SetupError("Node unavailable")):
            report = doctor(self.runtime)
        self.assertIn("当前Python未绑定工作区独立运行时，请运行Skill的scripts/bootstrap.ps1检查环境。", report["issues"])

    def test_doctor_does_not_require_npm(self):
        """验证环境诊断直接检查已安装的BL和Python依赖。"""
        node = self.runtime.root / "node.exe"
        with patch("asr_runtime.application.diagnostics.check_node", return_value=(node, "v24.19.0")):
            report = doctor(self.runtime)
        self.assertEqual(report["node"], {"path": str(node), "version": "v24.19.0"})

    def test_metadata_alone_cannot_mark_incomplete_installation_ready(self):
        """验证BL入口启动失败被报告为安装异常。"""
        with patch("asr_runtime.utils.bailian.bl_command", return_value=["node.exe", "bl.mjs", "--version", "--quiet"]), \
             patch("asr_runtime.utils.bailian.run_process", return_value=subprocess.CompletedProcess([], 1, "", "missing dependency")) as run:
            with self.assertRaisesRegex(SetupError, "不完整"):
                verify_bl_installation(self.runtime)
        run.assert_called_once()

    def test_doctor_reports_python_version_drift(self):
        """验证环境诊断报告Python依赖版本偏差。"""
        python = self.runtime.path(".venv/Scripts/python.exe")
        python.parent.mkdir(parents=True)
        python.touch()
        packages = {**locked_python_versions(self.runtime), "av": "0.0.0"}
        with patch("asr_runtime.application.diagnostics.check_node", side_effect=SetupError("test Node unavailable")), \
             patch("asr_runtime.application.diagnostics.installed_bl_version", return_value=None), \
             patch("asr_runtime.utils.environment.run_process", return_value=subprocess.CompletedProcess([], 0, json.dumps(packages), "")):
            report = doctor(self.runtime)
        self.assertEqual(report["python_packages"], packages)
        self.assertTrue(any("av" in issue and "18.1.0" in issue for issue in report["issues"]))

    def test_doctor_reports_corrupt_bl_metadata_without_aborting(self):
        """验证损坏BL元信息加入诊断问题列表。"""
        manifest = self.runtime.path(".tools/bailian/node_modules/bailian-cli/package.json")
        manifest.parent.mkdir(parents=True)
        manifest.write_text("[]", encoding="utf-8")
        with patch("asr_runtime.application.diagnostics.check_node", side_effect=SetupError("test Node unavailable")):
            report = doctor(self.runtime)
        self.assertTrue(any("包信息损坏" in issue for issue in report["issues"]))

    def test_dependency_probe_rejects_malformed_report(self):
        """验证依赖探针拒绝异常返回结构。"""
        python = self.runtime.path(".venv/Scripts/python.exe")
        python.parent.mkdir(parents=True)
        python.touch()
        for output in ("not JSON", "[]", '{"av": null}', '{}'):
            with self.subTest(output=output), \
                 patch("asr_runtime.utils.environment.run_process", return_value=subprocess.CompletedProcess([], 0, output, "")):
                with self.assertRaisesRegex(SetupError, "依赖检查返回异常"):
                    installed_python_versions(self.runtime, {"av": "18.1.0"})

    def test_dependency_lock_requires_exact_versions_and_hashes(self):
        """验证依赖锁必须使用精确版本和摘要。"""
        path = self.runtime.resource("scripts/requirements.txt")
        for content in ("", "av>=18.0.0", "av==18.1.0"):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(SetupError):
                    locked_python_versions(self.runtime)

    def test_probe_refuses_existing_configuration_without_reading(self):
        """验证探针发现既有配置后返回配置冲突。"""
        config = self.runtime.path(".state/bailian-check/config.json")
        config.parent.mkdir(parents=True)
        config.write_text("not JSON: must not be read", encoding="utf-8")
        with self.assertRaisesRegex(SetupError, "配置/凭据"):
            probe(self.runtime)

    def test_probe_uses_only_reserved_url_and_dedicated_environment(self):
        """验证探针使用虚构URL及独立环境。"""
        from asr_runtime import MODEL
        payload = {"request": {
            "model": MODEL,
            "input": {"file_urls": [SYNTHETIC_AUDIO_URL], "context": [{"content": [{"text": "本地合约探针"}]}]},
            "parameters": {"diarization_enabled": True, "speaker_count": 3,
                           "language_hints": ["zh"], "vocabulary": {"测试术语": 4}},
        }}
        outputs = [
            subprocess.CompletedProcess([], 0, "bl 2.1.0\n", ""),
            *[subprocess.CompletedProcess([], 0, "", "Usage: test") for _ in range(3)],
            subprocess.CompletedProcess([], 0, json.dumps(payload), ""),
        ]
        with patch("scripts.probe_bl.bl_command", side_effect=lambda runtime, args: ["node.exe", *args, "--quiet"]), \
             patch("scripts.probe_bl.run_process", side_effect=outputs) as run:
            self.assertEqual(probe(self.runtime)["status"], "passed")
        for call in run.call_args_list:
            self.assertTrue(call.kwargs["isolated_config"])
        request_args = run.call_args_list[-1].args[1]
        self.assertEqual(request_args[request_args.index("--url") + 1], SYNTHETIC_AUDIO_URL)
        self.assertEqual(request_args[request_args.index("--language") + 1], "zh")
        self.assertEqual(request_args[request_args.index("--speaker-count") + 1], "3")
