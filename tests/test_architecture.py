"""验证运行包的模块布局和单向依赖。"""

import ast
import unittest

from tests.support import SKILL_ROOT


class ArchitectureTests(unittest.TestCase):
    def test_utils_do_not_depend_on_application_or_http(self):
        """验证工具层遵守单向依赖约定。"""
        source = SKILL_ROOT / "scripts/asr_runtime/utils"
        self.assertTrue(source.is_dir())
        for path in source.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    self.assertFalse({"application", "web", "review_web"}.intersection(module.split(".")), str(path))
                elif isinstance(node, ast.Import):
                    self.assertTrue(all(not alias.name.startswith(("asr_runtime.application", "asr_runtime.web", "asr_runtime.review_web"))
                                        for alias in node.names), str(path))

    def test_package_root_contains_only_entry_models_and_http(self):
        """验证包根聚焦入口、共享数据与HTTP，具体能力位于各自目录。"""
        root = SKILL_ROOT / "scripts/asr_runtime"
        self.assertEqual({path.name for path in root.glob("*.py")},
                         {"__init__.py", "__main__.py", "models.py", "web.py", "review_web.py"})
        for name in ("application", "utils", "static"):
            self.assertTrue((root / name).is_dir(), name)
