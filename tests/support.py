"""提供隔离的 Skill 资源与用户工作区测试环境。"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from asr_runtime.utils.environment import Runtime

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/asr-transcription"
CONTRACT_WORKSPACE = Path(os.environ.get("MEMOFLOW_BL_CONTRACT_WORKSPACE", str(ROOT / ".runtime/bl-2.4.0-workspace")))
CONTRACT_BL_ENTRY = CONTRACT_WORKSPACE / ".asr-transcription/.tools/bailian/node_modules/bailian-cli/dist/bailian.mjs"


def contract_runtime() -> Runtime:
    """取得专用本机合约工作区的运行环境。"""
    return Runtime(CONTRACT_WORKSPACE, SKILL_ROOT)


class RuntimeTestCase(unittest.TestCase):
    def setUp(self):
        """创建本例独立工作区和可修改的最小 Skill 资源。"""
        temporary_root = ROOT / ".runtime/test-temp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=temporary_root, prefix="case-")
        self.temporary_root = Path(self.temporary.name)
        workspace = self.temporary_root / "workspace"
        workspace.mkdir()
        skill_root = self.temporary_root / "skill"
        for relative in ("scripts/requirements.txt", "scripts/bailian/package.json",
                         "scripts/bailian/package-lock.json", "assets/env.example"):
            destination = skill_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SKILL_ROOT / relative, destination)
        self.runtime = Runtime(workspace, skill_root)
        self.runtime.root.mkdir()

    def tearDown(self):
        """核对临时根范围并清理本例资源与工作区。"""
        if not self.temporary_root.resolve().is_relative_to(ROOT.resolve()):
            raise AssertionError("测试临时目录越过工作区边界")
        self.temporary.cleanup()
