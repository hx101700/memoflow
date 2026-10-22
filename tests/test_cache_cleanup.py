"""验证升级后的旧依赖缓存清理及工作目录边界。"""

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

from asr_runtime.utils import installation
from asr_runtime.utils.environment import Runtime, SetupError, run_process
from tests.support import CONTRACT_WORKSPACE, RuntimeTestCase, contract_runtime


PREFIX = "make-fetch-happen:request-cache:"


class DownloadCacheCleanupTests(RuntimeTestCase):
    def write_file(self, relative: str, content: bytes = b"retained") -> Path:
        """在隔离工作目录内创建测试文件。"""
        path = self.runtime.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def prepare_npm_cache(self) -> None:
        """准备私有npm入口与非空缓存供命令边界断言。"""
        self.write_file(".tools/node/node_modules/npm/bin/npm-cli.js")
        self.write_file(".runtime/npm-cache/_cacache/index-v5/test")

    def test_removes_old_wheels_and_keeps_current_versions(self) -> None:
        """验证只删除旧wheel，并保留当前依赖、pip和其他文件。"""
        kept = [
            self.write_file(".runtime/wheels/av-18.1.0-cp311-abi3-win_amd64.whl"),
            self.write_file(".runtime/wheels/python_docx-1.2.0-py3-none-any.whl"),
            self.write_file(f".runtime/wheels/pip-{installation.PIP_VERSION}-py3-none-any.whl"),
            self.write_file(".runtime/wheels/download.partial"),
            self.write_file(".runtime/wheels/unknown.whl"),
        ]
        obsolete = [
            self.write_file(".runtime/wheels/av-17.0.0-cp311-abi3-win_amd64.whl"),
            self.write_file(".runtime/wheels/pip-25.0.0-py3-none-any.whl"),
            self.write_file(".runtime/wheels/removed_package-1.0.0-py3-none-any.whl"),
        ]
        protected = [
            self.write_file(".env", b"DASHSCOPE_API_KEY=test-only"),
            self.write_file(".venv/Lib/site-packages/av/__init__.py"),
            self.write_file(".tools/bailian/node_modules/bailian-cli/package.json"),
            self.write_file(".runtime/runtime-cache/python-runtime.zip"),
        ]
        with patch.object(installation, "run_process") as run:
            result = installation.prune_download_cache(
                self.runtime, {"av": "18.1.0", "python-docx": "1.2.0"}, {},
            )
        self.assertEqual(result, {"python_wheels": 3, "npm_entries": 0})
        run.assert_not_called()
        self.assertTrue(all(path.exists() for path in kept))
        self.assertTrue(all(not path.exists() for path in obsolete))
        self.assertEqual([path.read_bytes() for path in protected],
                         [b"DASHSCOPE_API_KEY=test-only", b"retained", b"retained", b"retained"])

    def test_empty_caches_do_not_start_npm(self) -> None:
        """验证缓存缺失或空目录时直接返回清理数量。"""
        with patch.object(installation, "run_process") as run:
            for exists in (False, True):
                with self.subTest(cache_directory_exists=exists):
                    if exists:
                        self.runtime.path(".runtime/npm-cache").mkdir(parents=True)
                    self.assertEqual(installation.prune_download_cache(self.runtime, {}, {}),
                                     {"python_wheels": 0, "npm_entries": 0})
        run.assert_not_called()

    def test_parses_registry_and_mirror_package_keys(self) -> None:
        """验证官方、镜像及作用域包键可还原准确包名和版本。"""
        examples = {
            "https://registry.npmjs.org/bailian-cli/-/bailian-cli-2.4.0.tgz": ("bailian-cli", "2.4.0"),
            "https://registry.npmmirror.com/@bailian-cli/core/-/core-2.1.0.tgz": ("@bailian-cli/core", "2.1.0"),
            "https://registry.npmjs.org/@bailian-cli%2fcore/-/core-2.4.0.tgz": ("@bailian-cli/core", "2.4.0"),
            "https://cdn.npmmirror.com/packages/ansi-regex/6.2.2/ansi-regex-6.2.2.tgz": ("ansi-regex", "6.2.2"),
            "https://cdn.npmmirror.com/packages/@bailian-cli/core/2.4.0/core-2.4.0.tgz": ("@bailian-cli/core", "2.4.0"),
        }
        for url, expected in examples.items():
            with self.subTest(url=url):
                self.assertEqual(installation._npm_cached_package(PREFIX + url), expected)

    def test_preserves_unknown_npm_cache_keys(self) -> None:
        """验证元数据、未知来源及无法识别的缓存键保留。"""
        unknown = [
            "pacote:tarball:file:local.tgz",
            PREFIX + "https://registry.npmjs.org/bailian-cli",
            PREFIX + "https://example.test/pkg/-/pkg-1.0.0.tgz",
            PREFIX + "https://cdn.npmmirror.com/packages/pkg/1.0.0/other.tgz",
        ]
        for key in unknown:
            with self.subTest(key=key):
                self.assertIsNone(installation._npm_cached_package(key))
        self.prepare_npm_cache()
        with patch.object(installation, "run_process", return_value=subprocess.CompletedProcess([], 0, "\n".join(unknown), "")) as run:
            result = installation.prune_download_cache(self.runtime, {}, {})
        self.assertEqual(result["npm_entries"], 0)
        self.assertEqual(run.call_count, 1)

    def test_cleans_only_obsolete_keys_using_private_npm_and_cache(self) -> None:
        """验证按锁中实际包名保留别名包，并限定私有Node和缓存目录。"""
        self.prepare_npm_cache()
        retained = [
            PREFIX + "https://registry.npmjs.org/bailian-cli/-/bailian-cli-2.4.0.tgz",
            PREFIX + "https://cdn.npmmirror.com/packages/@bailian-cli/core/2.4.0/core-2.4.0.tgz",
            PREFIX + "https://registry.npmmirror.com/string-width/-/string-width-4.2.3.tgz",
            PREFIX + "https://registry.npmjs.org/bailian-cli",
        ]
        obsolete = [
            PREFIX + "https://registry.npmjs.org/bailian-cli/-/bailian-cli-2.1.0.tgz",
            PREFIX + "https://cdn.npmmirror.com/packages/@bailian-cli/core/2.1.0/core-2.1.0.tgz",
            PREFIX + "https://registry.npmmirror.com/removed-package/-/removed-package-1.0.0.tgz",
        ]
        packages = {
            "": {"name": "skill-runtime", "version": "0.1.1"},
            "node_modules/bailian-cli": {"version": "2.4.0"},
            "node_modules/@bailian-cli/core": {"version": "2.4.0"},
            "node_modules/string-width-cjs": {"name": "string-width", "version": "4.2.3"},
        }
        with patch.object(installation, "run_process", side_effect=[
            subprocess.CompletedProcess([], 0, "\n".join(retained + obsolete), ""),
            *[subprocess.CompletedProcess([], 0, "", "") for _ in range(len(obsolete) + 1)],
        ]) as run:
            result = installation.prune_download_cache(self.runtime, {}, packages)
        self.assertEqual(result, {"python_wheels": 0, "npm_entries": 3})
        base = [str(self.runtime.node_entry),
                str(self.runtime.node_entry.parent / "node_modules/npm/bin/npm-cli.js"),
                "--cache", str(self.runtime.path(".runtime/npm-cache")), "cache"]
        self.assertEqual(run.call_args_list[0].args, (self.runtime, [*base, "ls"]))
        self.assertEqual([call.args for call in run.call_args_list[1:-1]],
                         [(self.runtime, [*base, "clean", key]) for key in obsolete])
        self.assertEqual(run.call_args_list[-1].args, (self.runtime, [*base, "verify"]))

    def test_npm_list_and_clean_failures_report_setup_error(self) -> None:
        """验证npm失败时返回具体操作错误并停止后续清理命令。"""
        self.prepare_npm_cache()
        old = PREFIX + "https://registry.npmjs.org/bailian-cli/-/bailian-cli-2.1.0.tgz"
        cases = [
            ([subprocess.CompletedProcess([], 1, "", "error")], "列表读取失败", 1),
            ([subprocess.CompletedProcess([], 0, old, ""),
              subprocess.CompletedProcess([], 2, "", "error")], "清理未完成", 2),
            ([subprocess.CompletedProcess([], 0, old, ""),
              subprocess.CompletedProcess([], 0, "", ""),
              subprocess.CompletedProcess([], 2, "", "error")], "索引整理未完成", 3),
        ]
        for responses, message, count in cases:
            with self.subTest(message=message), patch.object(installation, "run_process", side_effect=responses) as run:
                with self.assertRaisesRegex(SetupError, message):
                    installation.prune_download_cache(self.runtime, {}, {})
                self.assertEqual(run.call_count, count)

    def test_invalid_lock_preserves_cache(self) -> None:
        """验证锁文件缺少版本时保留现有下载文件并报告原因。"""
        wheel = self.write_file(".runtime/wheels/av-17.0.0-cp311-abi3-win_amd64.whl")
        with patch.object(installation, "run_process") as run, self.assertRaisesRegex(SetupError, "缺少包名或版本"):
            installation.prune_download_cache(self.runtime, {}, {"node_modules/bailian-cli": {}})
        self.assertTrue(wheel.exists())
        run.assert_not_called()

    @unittest.skipUnless((CONTRACT_WORKSPACE / ".asr-transcription/.tools/node/node.exe").is_file(),
                         "需要私有Node及npm运行缓存合约")
    def test_mirror_aliases_remove_old_content_and_keep_current_cache_readable(self) -> None:
        """用真实npm验证共享旧内容的镜像键被清理，当前内容和元数据仍可读取。"""
        node = contract_runtime().node_entry
        cacache = node.parent / "node_modules/npm/node_modules/cacache"
        self.runtime.prepare()
        cache = self.runtime.path(".runtime/npm-cache/_cacache")
        cache.mkdir(parents=True)
        old = {
            PREFIX + "https://registry.npmjs.org/bailian-cli/-/bailian-cli-2.1.0.tgz": "old tarball",
            PREFIX + "https://cdn.npmmirror.com/packages/bailian-cli/2.1.0/bailian-cli-2.1.0.tgz": "old tarball",
            PREFIX + "https://registry.npmjs.org/z-unused/-/z-unused-1.0.0.tgz": "other old tarball",
        }
        kept = {
            PREFIX + "https://registry.npmjs.org/bailian-cli/-/bailian-cli-2.4.0.tgz": "current tarball",
            PREFIX + "https://cdn.npmmirror.com/packages/bailian-cli/2.4.0/bailian-cli-2.4.0.tgz": "current tarball",
            PREFIX + "https://registry.npmjs.org/bailian-cli": "metadata",
        }
        # cacache仅用于构建和读取测试夹具；生产清理走npm公开命令。
        create = """
const cache = require(process.argv[1]);
(async () => {
  for (const [key, value] of Object.entries(JSON.parse(process.argv[3]))) {
    await cache.put(process.argv[2], key, Buffer.from(value));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        read = """
const cache = require(process.argv[1]);
(async () => {
  const contents = {};
  for (const key of Object.keys(await cache.ls(process.argv[2]))) {
    contents[key] = (await cache.get(process.argv[2], key)).data.toString();
  }
  process.stdout.write(JSON.stringify(contents));
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        with patch.object(Runtime, "node_entry", new_callable=PropertyMock, return_value=node):
            created = run_process(self.runtime, [str(node), "-e", create, str(cacache), str(cache),
                                                json.dumps(old | kept)])
            self.assertEqual(created.returncode, 0, created.stderr)
            result = installation.prune_download_cache(self.runtime, {}, {
                "node_modules/bailian-cli": {"version": "2.4.0"},
            })
            remaining = run_process(self.runtime, [str(node), "-e", read, str(cacache), str(cache)])
        self.assertEqual(result, {"python_wheels": 0, "npm_entries": 3})
        self.assertEqual(remaining.returncode, 0, remaining.stderr)
        self.assertEqual(json.loads(remaining.stdout), kept)
