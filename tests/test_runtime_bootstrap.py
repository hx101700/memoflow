"""通过Windows PowerShell验证私有运行时安装的文件边界与缓存行为。"""

import base64
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile

from tests.support import ROOT, SKILL_ROOT, RuntimeTestCase


def ps_string(value: str | Path) -> str:
    """将路径或文本编码为PowerShell单引号字面量。"""
    return "'" + str(value).replace("'", "''") + "'"


class RuntimeBootstrapTests(RuntimeTestCase):
    def setUp(self):
        """复制安装入口到本例Skill目录，隔离包内归档测试。"""
        super().setUp()
        shutil.copyfile(SKILL_ROOT / "scripts/bootstrap.ps1", self.runtime.skill_root / "scripts/bootstrap.ps1")

    def run_powershell(self, body: str) -> subprocess.CompletedProcess[str]:
        """在无Python和Node搜索路径的系统PowerShell中执行安装函数。"""
        script = (
            "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)\n"
            f". {ps_string(self.runtime.skill_root / 'scripts/bootstrap.ps1')} "
            f"-Workspace {ps_string(self.runtime.workspace)}\n"
            "try {\n" + body + "\n} catch { Write-Output $_.Exception.Message; exit 1 }"
        )
        system = Path(os.environ["SYSTEMROOT"])
        environment = dict(os.environ, PATH=str(system / "System32"))
        return subprocess.run(
            [str(system / "System32/WindowsPowerShell/v1.0/powershell.exe"),
             "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand",
             base64.b64encode(script.encode("utf-16-le")).decode("ascii")],
            cwd=ROOT, env=environment, capture_output=True, encoding="utf-8", timeout=30,
        )

    def install_archive(self, name: str, entries: dict[str, str], *, archive_root: str = "",
                        bad_hash: bool = False, bundled: bool = False) -> subprocess.CompletedProcess[str]:
        """用本地小归档执行实际摘要校验、解压和目录发布。"""
        archive = self.temporary_root / f"{name}.zip"
        with ZipFile(archive, "w") as output:
            for path, content in entries.items():
                output.writestr(path, content)
        definition = {
            "url": archive.as_uri(), "archive_root": archive_root,
            "sha256": "0" * 64 if bad_hash else hashlib.sha256(archive.read_bytes()).hexdigest(),
        }
        if bundled:
            destination = self.runtime.resource("assets/runtimes")
            destination.mkdir()
            shutil.copyfile(archive, destination / archive.name)
            definition["url"] = "http://127.0.0.1:1/" + archive.name
        return self.run_powershell(
            f"$root = Get-InstallRoot {ps_string(self.runtime.workspace)} {ps_string(self.runtime.skill_root)}\n"
            f"$definition = {ps_string(json.dumps(definition))} | ConvertFrom-Json\n"
            f"Install-PrivateRuntime {ps_string(name)} $definition $root"
        )

    def test_full_python_archive_installs_under_workspace(self):
        """验证根目录布局的Python归档安装及完整缓存保留。"""
        result = self.install_archive("python", {"python.exe": "python", "Lib/venv/__init__.py": "venv"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.runtime.base_python.read_text(), "python")
        self.assertTrue(self.runtime.path(".runtime/runtime-downloads/python.zip").is_file())
        self.assertEqual(list(self.runtime.path(".runtime/tmp").iterdir()), [])

    def test_node_archive_removes_distribution_wrapper(self):
        """验证Node压缩包内的版本目录转换为固定工作区路径。"""
        result = self.install_archive("node", {"node-version/node.exe": "node"}, archive_root="node-version")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.runtime.node_entry.read_text(), "node")
        self.assertEqual(list(self.runtime.path(".runtime/tmp").iterdir()), [])

    def test_existing_runtime_is_preserved(self):
        """验证已有运行时不会被归档覆盖。"""
        self.runtime.base_python.parent.mkdir(parents=True)
        self.runtime.base_python.write_text("existing")
        result = self.install_archive("python", {"python.exe": "replacement"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.runtime.base_python.read_text(), "existing")
        self.assertFalse(self.runtime.path(".runtime/runtime-downloads/python.zip").exists())

    def test_bundled_archive_works_without_download(self):
        """验证完整包使用包内归档，下载缓存保持为空。"""
        result = self.install_archive("python", {"python.exe": "bundled"}, bundled=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.runtime.base_python.read_text(), "bundled")
        self.assertEqual(list(self.runtime.path(".runtime/runtime-downloads").iterdir()), [])
        self.assertTrue(self.runtime.resource("assets/runtimes/python.zip").is_file())

    def test_corrupt_bundled_archive_stops_before_installation(self):
        """验证完整包内损坏归档直接报错且保留Skill原文件。"""
        result = self.install_archive("python", {"python.exe": "bad"}, bad_hash=True, bundled=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("安装包内运行时摘要不匹配", result.stdout)
        self.assertFalse(self.runtime.base_python.parent.exists())
        self.assertTrue(self.runtime.resource("assets/runtimes/python.zip").is_file())

    def test_digest_mismatch_never_publishes_runtime(self):
        """验证摘要错误删除损坏下载并保持运行时未安装。"""
        result = self.install_archive("python", {"python.exe": "bad"}, bad_hash=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("摘要不匹配", result.stdout)
        self.assertFalse(self.runtime.base_python.parent.exists())
        self.assertEqual(list(self.runtime.path(".runtime/runtime-downloads").iterdir()), [])

    def test_missing_executable_cleans_staging(self):
        """验证缺少入口的归档不会发布半成品且清理解压暂存。"""
        result = self.install_archive("python", {"readme.txt": "no executable"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少入口", result.stdout)
        self.assertFalse(self.runtime.base_python.parent.exists())
        self.assertEqual(list(self.runtime.path(".runtime/tmp").iterdir()), [])

    def test_skill_cannot_be_used_as_workspace(self):
        """验证安装前拒绝将Skill资源目录作为工作目录。"""
        result = self.run_powershell(
            f"Get-InstallRoot {ps_string(self.runtime.skill_root)} {ps_string(self.runtime.skill_root)}"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime.skill_root / ".asr-transcription").exists())

    def test_private_directory_junction_is_rejected_before_writing(self):
        """验证私有目录联接不会把下载写入资源位置。"""
        redirected = self.temporary_root / "redirected"
        redirected.mkdir()
        result = self.run_powershell(
            f"$null = New-Item -ItemType Junction -Path {ps_string(self.runtime.path('.tools'))} "
            f"-Target {ps_string(redirected)}\n"
            f"Get-InstallRoot {ps_string(self.runtime.workspace)} {ps_string(self.runtime.skill_root)}"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("目录联接", result.stdout)
        self.assertEqual(list(redirected.iterdir()), [])

    def test_unicode_and_spaces_are_kept_in_paths(self):
        """验证中文及空格目录保留完整名称。"""
        workspace = self.temporary_root / "转写 工作目录"
        workspace.mkdir()
        result = self.run_powershell(
            f"Get-InstallRoot {ps_string(workspace)} {ps_string(self.runtime.skill_root)}"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), str(workspace / ".asr-transcription"))
