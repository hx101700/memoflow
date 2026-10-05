"""验证 Skill 包边界、解压入口和工作区隔离。"""

import hashlib
import json
import posixpath
from pathlib import Path
import re
import shutil
import subprocess
import sys
from unittest.mock import patch
from zipfile import ZipFile

from scripts.build_zip import REPOSITORY_FILES, REQUIRED_FILES, SKILL_DIRECTORY, build_zip
from asr_runtime.utils.environment import Runtime
from tests.support import RuntimeTestCase, SKILL_ROOT


class PackageTests(RuntimeTestCase):
    def setUp(self):
        """准备含固定运行资源及仓库使用说明的独立副本。"""
        super().setUp()
        self.source = self.temporary_root / "中文 源码目录"
        self.skill = self.source / SKILL_DIRECTORY
        for relative in REQUIRED_FILES:
            destination = self.skill / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SKILL_ROOT / relative, destination)
        for relative in REPOSITORY_FILES:
            shutil.copyfile(SKILL_ROOT.parents[1] / relative, self.source / relative)

    def extract(self, name="解压 验收目录"):
        """构建独立包并解压到本例指定目录。"""
        report = build_zip(self.source)
        destination = self.temporary_root / name
        with ZipFile(report["path"]) as archive:
            self.assertIsNone(archive.testzip())
            archive.extractall(destination)
        return destination

    def test_release_contains_runtime_and_current_repository_readmes(self):
        """验证运行资源和最新版仓库说明入包，开发文件与私有数据排除。"""
        excluded = (
            "AGENTS.md", ".gitignore", ".env", "pyproject.toml",
            "data/audio/private.wav", "transcriptions/job/transcription.md",
            ".asr-transcription/.env", ".asr-transcription/.state/jobs/config.json",
            ".asr-transcription/.state/sessions/private/connection.json",
            ".asr-transcription/.runtime/tmp/python-123-private/openpyxl.tmp",
            ".asr-transcription/.venv/Lib/site-packages/private.py",
            ".asr-transcription/.tools/python/python.exe", ".asr-transcription/.tools/node/node.exe",
            ".asr-transcription/.runtime/runtime-downloads/python.zip.part",
            "scripts/bailian/node_modules/private.js", "scripts/developer.py",
            "scripts/asr_runtime/debug.py", "scripts/asr_runtime/static/debug.ts",
            "frontend/App.vue", "frontend/main.ts", "frontend/tsconfig.json", "mypy.ini", "requirements-dev.txt",
            "scripts/build_zip.py", "scripts/probe_bl.py", "tests/test_package.py",
            "doc/STATUS.md", "doc/DEVELOPMENT.md", "doc/ACCEPTANCE.md", "doc/uml/private.png",
            ".agents/skills/private/SKILL.md", "dist/old.zip", "assets/av.whl",
        )
        for relative in excluded:
            path = self.skill / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic-private-marker")
        for relative in REPOSITORY_FILES:
            (self.skill / relative).write_bytes(b"stale-skill-copy")
            path = self.source / relative
            path.write_bytes(path.read_bytes() + b"\n<!-- current repository README -->\n")
        report = build_zip(self.source)
        self.assertEqual(Path(report["path"]), self.source / "dist/asr-transcription-lite.zip")
        with ZipFile(report["path"]) as archive:
            names = archive.namelist()
            self.assertEqual(names, report["files"])
            self.assertEqual(set(names), set(REQUIRED_FILES) | set(REPOSITORY_FILES))
            self.assertEqual(len(names), report["file_count"])
            self.assertIn("SKILL.md", names)
            self.assertIn("scripts/bootstrap.ps1", names)
            self.assertIn("scripts/runtimes.json", names)
            self.assertTrue(all(name.split("/")[0] in
                                {"SKILL.md", "LICENSE", "README.md", "README.en.md", "agents", "scripts", "references", "assets"}
                                for name in names))
            self.assertFalse(any("tools" in name.split("/") for name in names))
            for name in names:
                source = self.source if name in REPOSITORY_FILES else self.skill
                self.assertEqual(archive.read(name), (source / name).read_bytes())
            for name in excluded:
                self.assertNotIn(name, names)

    def test_existing_zip_is_preserved(self):
        """验证构建保留同名旧包并返回文件已存在错误。"""
        destination = self.temporary_root / "existing.zip"
        destination.write_bytes(b"previous-package")
        with self.assertRaises(FileExistsError):
            build_zip(self.source, destination)
        self.assertEqual(destination.read_bytes(), b"previous-package")

    def prepare_runtime_archives(self):
        """构造可验证的小型运行时归档与本例发行摘要。"""
        directory = self.temporary_root / "runtime-downloads"
        directory.mkdir()
        manifest = {}
        for name in ("python", "node"):
            archive = directory / f"{name}.zip"
            with ZipFile(archive, "w") as output:
                output.writestr(f"{name}.exe", "synthetic runtime")
            manifest[name] = {"url": f"https://example.invalid/{name}.zip",
                              "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
        (self.skill / "scripts/runtimes.json").write_text(json.dumps(manifest), encoding="utf-8")
        return directory

    def test_full_and_lite_packages_share_all_skill_files(self):
        """验证完整包只额外附带两个官方归档，其余文件与轻量包逐字相同。"""
        directory = self.prepare_runtime_archives()
        lite = build_zip(self.source)
        full = build_zip(self.source, runtime_directory=directory)
        self.assertEqual(Path(full["path"]).name, "asr-transcription.zip")
        with ZipFile(lite["path"]) as lite_zip, ZipFile(full["path"]) as full_zip:
            self.assertEqual(set(full_zip.namelist()) - set(lite_zip.namelist()),
                             {"assets/runtimes/python.zip", "assets/runtimes/node.zip"})
            for name in lite_zip.namelist():
                self.assertEqual(lite_zip.read(name), full_zip.read(name))

    def test_runtime_digest_mismatch_prevents_package_creation(self):
        """验证打包前拒绝损坏的运行时归档。"""
        directory = self.prepare_runtime_archives()
        (directory / "python.zip").write_bytes(b"damaged")
        with self.assertRaisesRegex(ValueError, "运行时归档摘要不符"):
            build_zip(self.source, runtime_directory=directory)
        self.assertFalse((self.source / "dist").exists())

    def test_missing_skill_stops_before_creating_archive(self):
        """验证缺少 Skill 入口时在创建 ZIP 前停止。"""
        (self.skill / "SKILL.md").unlink()
        with self.assertRaises(FileNotFoundError):
            build_zip(self.source)
        self.assertFalse((self.source / "dist").exists())

    def test_missing_resource_stops_before_creating_archive(self):
        """验证缺少运行依赖锁时在创建 ZIP 前停止。"""
        (self.skill / "scripts/requirements.txt").unlink()
        with self.assertRaises(FileNotFoundError):
            build_zip(self.source)
        self.assertFalse((self.source / "dist").exists())

    def test_missing_repository_readme_stops_before_creating_archive(self):
        """验证缺少仓库使用说明时在创建 ZIP 前停止。"""
        (self.source / "README.en.md").unlink()
        with self.assertRaises(FileNotFoundError):
            build_zip(self.source)
        self.assertFalse((self.source / "dist").exists())

    def test_redirected_source_file_is_rejected(self):
        """验证重定向到清单之外的文件被拒绝。"""
        redirected = self.skill / "scripts/requirements.txt"
        outside = self.temporary_root / "outside.md"
        outside.write_bytes(b"synthetic-private-marker")
        original_resolve = Path.resolve

        def resolve(path, *args, **kwargs):
            """将指定依赖锁模拟解析到另一个文件。"""
            return outside if path == redirected else original_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve):
            with self.assertRaisesRegex(ValueError, "发行文件不是普通文件"):
                build_zip(self.source)
        self.assertFalse((self.source / "dist").exists())

    def test_extracted_entry_runs_from_an_unrelated_directory(self):
        """验证中文空格路径的绝对入口从其他 cwd 正常显示帮助。"""
        skill = self.extract()
        other = self.temporary_root / "无关 当前目录"
        other.mkdir()
        result = subprocess.run(
            [sys.executable, "-S", "-X", "utf8", str(skill / "scripts/asr.py"), "--help"],
            cwd=other, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("bootstrap", "transcribe", "--workspace"):
            self.assertIn(command, result.stdout)
        self.assertNotIn("probe-bl", result.stdout)
        self.assertFalse((skill / ".asr-transcription").exists())
        self.assertEqual(list(other.iterdir()), [])

    def test_extracted_entry_requires_an_explicit_workspace(self):
        """验证执行命令在缺少工作区参数时返回用法错误。"""
        skill = self.extract()
        result = subprocess.run(
            [sys.executable, "-S", "-X", "utf8", str(skill / "scripts/asr.py"), "doctor"],
            cwd=self.temporary_root, capture_output=True, text=True, encoding="utf-8", timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--workspace", result.stderr)
        self.assertFalse((skill / ".asr-transcription").exists())

    def test_diagnostic_uses_selected_workspace_and_preserves_skill_resources(self):
        """验证诊断定位指定工作区且 Skill 文件内容保持一致。"""
        skill = self.extract()
        workspace = self.temporary_root / "用户 工作目录"
        workspace.mkdir()
        before = {name: hashlib.sha256((skill / name).read_bytes()).hexdigest()
                  for name in REQUIRED_FILES}
        result = subprocess.run(
            [sys.executable, "-S", "-X", "utf8", str(skill / "scripts/asr.py"),
             "--workspace", str(workspace), "doctor"],
            cwd=self.temporary_root, capture_output=True, text=True, encoding="utf-8", timeout=30,
            check=False,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["workspace"], str(workspace.resolve()))
        self.assertEqual(report["skill_root"], str(skill.resolve()))
        self.assertEqual(report["runtime_root"], str(workspace / ".asr-transcription"))
        self.assertEqual(before, {name: hashlib.sha256((skill / name).read_bytes()).hexdigest()
                                  for name in REQUIRED_FILES})
        self.assertEqual({path.relative_to(skill).as_posix() for path in skill.rglob("*") if path.is_file()},
                         set(REQUIRED_FILES) | set(REPOSITORY_FILES))
        self.assertFalse((skill / ".asr-transcription").exists())

    def test_two_workspaces_keep_credentials_and_state_separate(self):
        """验证同一 Skill 的两个工作区分别保存凭据和任务状态。"""
        skill = self.extract()
        workspaces = [self.temporary_root / name for name in ("工作区一", "工作区二")]
        for workspace in workspaces:
            workspace.mkdir()
        first, second = (Runtime(workspace, skill) for workspace in workspaces)
        first.prepare()
        second.prepare()
        first.path(".env").write_text("DASHSCOPE_API_KEY=synthetic-one\n", encoding="utf-8")
        first.path(".state/test.json").write_text("{}", encoding="utf-8")
        self.assertFalse(second.path(".env").exists())
        self.assertFalse(second.path(".state/test.json").exists())
        self.assertNotEqual(first.bl_directory, second.bl_directory)
        self.assertEqual(first.output_root, workspaces[0] / "transcriptions")
        self.assertFalse((skill / ".asr-transcription").exists())

    def test_extracted_runtime_imports_use_only_skill_source(self):
        """验证解压后的模块仅从该 Skill 的 scripts 目录加载。"""
        skill = self.extract()
        script = (
            "import importlib, pathlib, sys; "
            f"root=pathlib.Path({str(skill / 'scripts')!r}).resolve(); sys.path.insert(0,str(root)); "
            "modules=[importlib.import_module('asr_runtime.'+name) for name in "
            "['__main__','web','application.transcription','application.inputs','utils.media','utils.documents']]; "
            "assert all(pathlib.Path(module.__file__).is_relative_to(root) for module in modules)"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-X", "utf8", "-c", script],
            cwd=self.temporary_root, capture_output=True, text=True, encoding="utf-8", timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_markdown_links_resolve_inside_archive(self):
        """验证 Skill 引用的相对 Markdown 链接都位于包内。"""
        report = build_zip(self.source)
        with ZipFile(report["path"]) as archive:
            names = set(archive.namelist())
            for name in sorted(names):
                if not name.endswith(".md"):
                    continue
                for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", archive.read(name).decode("utf-8")):
                    if target.startswith(("https://", "http://", "#")):
                        continue
                    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target.split("#")[0]))
                    self.assertIn(resolved, names, f"{name} 指向包中不存在的 {target}")
