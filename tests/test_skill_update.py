"""验证轻量包更新、每日检查和业务进程的文件使用边界。"""

from datetime import date
import hashlib
from http.client import IncompleteRead
from io import BytesIO, StringIO
from contextlib import redirect_stderr, redirect_stdout
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from zipfile import ZIP_STORED, ZipFile

import update
from tests.support import ROOT, SKILL_ROOT


@unittest.skipUnless(os.name == "nt", "共享 Skill 文件租约使用 Windows 文件共享参数")
class SkillUpdateTests(unittest.TestCase):
    def setUp(self):
        """创建包含发行清单及稳定哨兵的隔离 Skill。"""
        directory = ROOT / ".runtime/test-temp"
        directory.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=directory, prefix="skill-update-")
        self.directory = Path(self.temporary.name)
        self.skill = self.directory / "已安装 Skill"
        self.skill.mkdir()
        self.original_files = {
            "SKILL.md": b"installed skill instructions",
            "scripts/asr.py": b"installed business entry",
            "scripts/update.py": b"installed updater",
            "README.md": b"installed readme",
            "references/obsolete.md": b"managed obsolete reference",
        }
        for name, data in self.original_files.items():
            path = self.skill / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (self.skill / update.LOCK).parent.mkdir(parents=True, exist_ok=True)
        (self.skill / update.LOCK).write_bytes(b"stable lock sentinel")
        self.installed_manifest = self.manifest("0.1.1", self.original_files)
        (self.skill / update.MANIFEST).write_bytes(self.encode(self.installed_manifest))

    def tearDown(self):
        """清理位于仓库测试根内的合成安装与工作目录。"""
        if not self.directory.resolve().is_relative_to(ROOT.resolve()):
            raise AssertionError("测试目录越过仓库边界")
        self.temporary.cleanup()

    @staticmethod
    def encode(value):
        """将合成发行资料编码为 UTF-8 JSON。"""
        return json.dumps(value, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def manifest(version, files):
        """构造记录版本及受管文件名的发行清单。"""
        return {"schema_version": 1, "name": "asr-transcription",
                "version": version, "files": list(files)}

    def package(self, *, version="0.1.2", extra=None):
        """生成带完整新文件和发行清单的内存轻量 ZIP。"""
        files = {"SKILL.md": b"new skill instructions: reload this document",
                 "scripts/asr.py": b"new business entry", "scripts/update.py": b"new updater",
                 "README.md": b"new readme", "references/current.md": b"new reference"}
        if extra:
            files.update(extra)
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_STORED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
            archive.writestr(update.MANIFEST, self.encode(self.manifest(version, files)))
            archive.writestr(update.LOCK, b"new archive sentinel")
        return output.getvalue(), files

    def release(self, *, version="0.1.2", package=None):
        """生成包含轻量包大小及 GitHub 摘要的正式发布资料。"""
        assets = [] if package is None else [{
            "name": "asr-transcription-lite.zip", "size": len(package),
            "digest": "sha256:" + hashlib.sha256(package).hexdigest(),
        }]
        return {"tag_name": "v" + version, "draft": False, "prerelease": False, "assets": assets}

    def state(self):
        """读取实际写入的日检及更新完成状态。"""
        return json.loads((self.skill / update.STATE).read_bytes())

    def main_report(self):
        """在隔离安装目录运行命令入口并解析退出码与回执。"""
        output = StringIO()
        with patch.object(update, "__file__", str(self.skill / "scripts/update.py")), \
             patch.object(sys, "argv", ["update.py"]), redirect_stdout(output):
            exit_code = update.main()
        return exit_code, json.loads(output.getvalue())

    def assert_original_files(self):
        """核对预检失败后每个原始受管文件均保持完整。"""
        for name, data in self.original_files.items():
            self.assertEqual((self.skill / name).read_bytes(), data, name)
        self.assertEqual(json.loads((self.skill / update.MANIFEST).read_bytes()), self.installed_manifest)

    def test_source_checkout_skips_release_lookup_and_state_creation(self):
        """验证源码目录没有发行清单时保留原文件并跳过网络。"""
        (self.skill / update.MANIFEST).unlink()
        with patch.object(update, "_download") as download:
            report = update.update_skill(self.skill)
        self.assertEqual(report["status"], "unmanaged")
        self.assertIsNone(report["is_latest"])
        self.assertFalse((self.skill / update.STATE).exists())
        download.assert_not_called()

    def test_same_version_checks_metadata_once_and_caches_result(self):
        """验证同版本只查询发布资料一次并复用当天结论。"""
        with patch.object(update, "_download", return_value=self.encode(self.release(version="0.1.1"))) as download:
            first = update.update_skill(self.skill)
            second = update.update_skill(self.skill)
        self.assertEqual(first["status"], "latest")
        self.assertTrue(first["is_latest"])
        self.assertEqual(second["status"], "checked_today")
        self.assertEqual(second["last_status"], "latest")
        self.assertTrue(second["is_latest"])
        download.assert_called_once_with(update.LATEST_URL)
        self.assert_original_files()

    def test_network_failure_consumes_day_and_is_not_reported_as_latest(self):
        """验证首次网络请求前保存日期，失败后当天保持未知结论。"""
        def fail_download(_url):
            """在模拟网络失败前核对日期已经持久化。"""
            self.assertEqual(self.state()["checked_on"], date.today().isoformat())
            self.assertEqual(self.state()["status"], "checking")
            raise URLError("synthetic disconnected network")

        with patch.object(update, "_download", side_effect=fail_download) as download:
            first = update.update_skill(self.skill)
            second = update.update_skill(self.skill)
        self.assertEqual(first["status"], "failed")
        self.assertIsNone(first["is_latest"])
        self.assertFalse(first["repair_required"])
        self.assertEqual(second["status"], "checked_today")
        self.assertEqual(second["last_status"], "failed")
        self.assertIsNone(second["is_latest"])
        download.assert_called_once()
        self.assert_original_files()

    def test_http_403_allows_current_installation_and_reuses_daily_failure(self):
        """验证 HTTP 403 保留当前安装、成功退出，且当天不再联网。"""
        error = HTTPError(update.LATEST_URL, 403, "Forbidden", None, None)
        with patch.object(update, "urlopen", side_effect=error) as open_url:
            first_code, first = self.main_report()
            cached_code, cached = self.main_report()
        self.assertEqual(first_code, 0)
        self.assertEqual(first["status"], "failed")
        self.assertFalse(first["repair_required"])
        self.assertEqual(first["installed_version"], "0.1.1")
        self.assertIsNone(first["is_latest"])
        self.assertIn("HTTP 403", first["message"])
        self.assertIn("可继续使用当前安装 v0.1.1", first["message"])
        self.assertEqual(cached_code, 0)
        self.assertEqual(cached["status"], "checked_today")
        self.assertEqual(cached["last_status"], "failed")
        self.assertFalse(cached["repair_required"])
        self.assertEqual(cached["installed_version"], "0.1.1")
        self.assertIsNone(cached["is_latest"])
        self.assertEqual(cached["message"], first["message"])
        open_url.assert_called_once()
        self.assertEqual(open_url.call_args.kwargs["timeout"], 30)
        with update.skill_in_use(self.skill):
            pass
        self.assert_original_files()

    def test_initial_record_write_failure_skips_network_and_allows_current_installation(self):
        """验证首次日检记录写失败立即返回可继续结果，不误报安装需要修复。"""
        with patch.object(update, "_write_json", side_effect=PermissionError("synthetic state write failure")) as write, \
             patch.object(update, "_download") as download:
            exit_code, report = self.main_report()
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["repair_required"])
        self.assertEqual(report["installed_version"], "0.1.1")
        self.assertIsNone(report["is_latest"])
        self.assertIn("state write failure", report["record_error"])
        self.assertIn("可继续使用当前安装 v0.1.1", report["message"])
        write.assert_called_once()
        download.assert_not_called()
        self.assertFalse((self.skill / update.STATE).exists())
        with update.skill_in_use(self.skill):
            pass
        self.assert_original_files()

    def test_main_requires_repair_for_invalid_existing_manifest_or_state(self):
        """验证已有清单或状态损坏时要求修复并以非零退出，且不联网。"""
        for name in (update.MANIFEST, update.STATE):
            with self.subTest(name=name):
                (self.skill / update.MANIFEST).write_bytes(self.encode(self.installed_manifest))
                (self.skill / update.STATE).unlink(missing_ok=True)
                (self.skill / name).write_bytes(b"{")
                with patch.object(update, "_download") as download:
                    exit_code, report = self.main_report()
                self.assertEqual(exit_code, 1)
                self.assertEqual(report["status"], "failed")
                self.assertTrue(report["repair_required"])
                self.assertIsNone(report["is_latest"])
                self.assertNotIn("record_error", report)
                download.assert_not_called()

    def test_main_requires_repair_when_existing_manifest_or_state_cannot_be_read(self):
        """验证无法读取已有清单或状态时不能将安装判断为可继续使用。"""
        read_bytes = Path.read_bytes
        (self.skill / update.STATE).write_bytes(b"{}")
        for name in (update.MANIFEST, update.STATE):
            with self.subTest(name=name):
                def fail_read(path):
                    """模拟指定安装元数据不可读取，其他文件保持正常。"""
                    if path == self.skill / name:
                        raise PermissionError("synthetic metadata read failure")
                    return read_bytes(path)

                with patch.object(Path, "read_bytes", fail_read), \
                     patch.object(update, "_download") as download:
                    exit_code, report = self.main_report()
                self.assertEqual(exit_code, 1)
                self.assertTrue(report["repair_required"])
                self.assertIn("metadata read failure", report["message"])
                self.assertNotIn("record_error", report)
                download.assert_not_called()
        self.assert_original_files()

    def test_main_requires_repair_when_installation_lease_cannot_be_opened(self):
        """验证无法建立安装读取保护时要求修复，而正常占用仍由原暂缓分支处理。"""
        with patch.object(update, "_lease", side_effect=PermissionError("synthetic lease open failure")), \
             patch.object(update, "_download") as download:
            exit_code, report = self.main_report()
        self.assertEqual(exit_code, 1)
        self.assertTrue(report["repair_required"])
        self.assertIn("lease open failure", report["message"])
        self.assertNotIn("record_error", report)
        download.assert_not_called()
        self.assertFalse((self.skill / update.STATE).exists())
        self.assert_original_files()

    def test_main_requires_repair_for_unfinished_file_replacement(self):
        """验证旧更新停在覆盖状态时继续阻止业务读取并以非零退出。"""
        (self.skill / update.STATE).write_bytes(self.encode({
            "checked_on": date.today().isoformat(), "status": "applying", "target_version": "0.1.2",
        }))
        with patch.object(update, "_download") as download:
            exit_code, report = self.main_report()
        self.assertEqual(exit_code, 1)
        self.assertTrue(report["repair_required"])
        download.assert_not_called()
        with self.assertRaisesRegex(update.UpdateError, "更新未完成"):
            with update.skill_in_use(self.skill):
                self.fail("未完成文件替换时进入了业务代码")
        self.assert_original_files()

    def test_next_local_calendar_day_allows_one_new_check(self):
        """验证跨越本地日期后允许新检查，日期内仍只查询一次。"""
        with patch.object(update, "date") as local_date, \
             patch.object(update, "_download", return_value=self.encode(self.release(version="0.1.1"))) as download:
            local_date.today.return_value = date(2026, 10, 20)
            update.update_skill(self.skill)
            update.update_skill(self.skill)
            local_date.today.return_value = date(2026, 10, 21)
            next_day = update.update_skill(self.skill)
            update.update_skill(self.skill)
        self.assertEqual(download.call_count, 2)
        self.assertEqual(next_day["status"], "latest")
        self.assertEqual(self.state()["checked_on"], "2026-10-21")

    def test_requested_check_bypasses_daily_cache_and_counts_for_later_auto_check(self):
        """验证用户主动检查可越过当日缓存，之后自动调用复用新结果。"""
        package, _ = self.package()
        replies = [self.encode(self.release(version="0.1.1")),
                   self.encode(self.release(package=package)), package]
        with patch.object(update, "_download", side_effect=replies) as download:
            update.update_skill(self.skill)
            requested = update.update_skill(self.skill, check_now=True)
            cached = update.update_skill(self.skill)
        self.assertEqual(requested["status"], "updated")
        self.assertEqual(cached["status"], "checked_today")
        self.assertEqual(cached["last_status"], "updated")
        self.assertEqual(download.call_count, 3)

    def test_incomplete_response_returns_failure_and_keeps_original_files(self):
        """验证正文中断得到下载失败回执并消耗当日检查机会。"""
        with patch.object(update, "urlopen") as open_url:
            open_url.return_value.__enter__.return_value.read.side_effect = IncompleteRead(b"partial", 100)
            first = update.update_skill(self.skill)
            cached = update.update_skill(self.skill)
        self.assertEqual(first["status"], "failed")
        self.assertIn("未完整接收", first["message"])
        self.assertFalse(first["repair_required"])
        self.assertEqual(cached["last_status"], "failed")
        open_url.assert_called_once()
        self.assert_original_files()

    def test_update_progress_identifies_current_and_target_versions(self):
        """验证下载前提供版本与动作进度，供 Codex 告知用户。"""
        package, _ = self.package()
        progress = StringIO()
        with patch.object(update, "_download", side_effect=[self.encode(self.release(package=package)), package]), \
             redirect_stderr(progress):
            update.update_skill(self.skill)
        self.assertIn("v0.1.1", progress.getvalue())
        self.assertIn("v0.1.2", progress.getvalue())
        self.assertIn("下载轻量包", progress.getvalue())

    def test_older_release_preserves_newer_installation(self):
        """验证当前安装领先正式版本时保留现有文件。"""
        with patch.object(update, "_download", return_value=self.encode(self.release(version="0.1.0"))) as download:
            report = update.update_skill(self.skill)
        self.assertEqual(report["status"], "local_ahead")
        self.assertIsNone(report["is_latest"])
        download.assert_called_once_with(update.LATEST_URL)
        self.assert_original_files()

    def test_missing_lite_asset_returns_actionable_failure(self):
        """验证新版本缺少轻量包时明确失败并保留原安装。"""
        with patch.object(update, "_download", return_value=self.encode(self.release())) as download:
            report = update.update_skill(self.skill)
        self.assertEqual(report["status"], "failed")
        self.assertIn("轻量安装包", report["message"])
        self.assertFalse(report["repair_required"])
        download.assert_called_once_with(update.LATEST_URL)
        self.assert_original_files()

    def test_new_release_replaces_managed_files_and_preserves_unrelated_data(self):
        """验证轻量包覆盖受管文件、清理遗留文件并保留用户与运行时文件。"""
        package, files = self.package()
        preserved = {".env": b"synthetic private key", "notes.md": b"user notes",
                     "assets/runtimes/python.zip": b"existing Python runtime archive",
                     "assets/runtimes/node.zip": b"existing Node runtime archive",
                     "assets/update.lock": b"stable lock sentinel"}
        for name, data in preserved.items():
            path = self.skill / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        with patch.object(update, "_download", side_effect=[self.encode(self.release(package=package)), package]) as download:
            report = update.update_skill(self.skill)
        self.assertEqual(report["status"], "updated")
        self.assertEqual(report["installed_version"], "0.1.2")
        self.assertTrue(report["is_latest"])
        self.assertFalse((self.skill / "references/obsolete.md").exists())
        for name, data in {**files, **preserved}.items():
            self.assertEqual((self.skill / name).read_bytes(), data, name)
        self.assertEqual(download.call_args_list[0].args, (update.LATEST_URL,))
        self.assertEqual(download.call_args_list[1].args, (
            "https://github.com/hx101700/memoflow/releases/download/v0.1.2/asr-transcription-lite.zip",))
        self.assertEqual(download.call_count, 2)
        self.assertFalse([path for path in self.skill.glob(".skill-update-*") if path.is_dir()])
        self.assertEqual(self.state()["status"], "updated")
        self.assertEqual(json.loads((self.skill / update.MANIFEST).read_bytes())["version"], "0.1.2")

    def test_success_reports_installed_version_then_reuses_daily_result(self):
        """验证更新回执要求重读说明，当天缓存沿用成功结果。"""
        package, _ = self.package()
        with patch.object(update, "_download", side_effect=[self.encode(self.release(package=package)), package]) as download:
            report = update.update_skill(self.skill)
            cached = update.update_skill(self.skill)
        self.assertEqual(report["status"], "updated")
        self.assertIn("SKILL.md", report["message"])
        self.assertIn("准备工作目录环境", report["message"])
        self.assertEqual(cached["last_status"], "updated")
        self.assertEqual(cached["installed_version"], "0.1.2")
        self.assertEqual(cached["status"], "checked_today")
        self.assertEqual(download.call_count, 2)

    def test_final_record_failure_preserves_actual_success_and_daily_cache(self):
        """验证最终日检记录保存失败仍报告真实安装版本，后续从完成清单读取成功结果。"""
        package, files = self.package()
        write_json = update._write_json

        def fail_final_record(path, value):
            """模拟文件更新完成后的日检记录保存失败。"""
            if path == self.skill / update.STATE and value.get("status") == "updated":
                raise PermissionError("synthetic state write failure")
            write_json(path, value)

        with patch.object(update, "_download", side_effect=[self.encode(self.release(package=package)), package]), \
             patch.object(update, "_write_json", side_effect=fail_final_record):
            report = update.update_skill(self.skill)
        self.assertEqual(report["status"], "updated")
        self.assertEqual(report["installed_version"], "0.1.2")
        self.assertIn("state write failure", report["record_error"])
        for name, data in files.items():
            self.assertEqual((self.skill / name).read_bytes(), data)
        with update.skill_in_use(self.skill):
            pass
        with patch.object(update, "_download") as download:
            cached = update.update_skill(self.skill)
        self.assertEqual(cached["status"], "checked_today")
        self.assertEqual(cached["last_status"], "updated")
        self.assertTrue(cached["is_latest"])
        self.assertEqual(cached["installed_version"], "0.1.2")
        download.assert_not_called()

    def test_truncated_or_digest_mismatched_zip_keeps_original_files(self):
        """验证下载长度或 GitHub 摘要不符时停止于文件替换之前。"""
        package, _ = self.package()
        for failure in ("size", "digest"):
            with self.subTest(failure=failure):
                (self.skill / update.STATE).unlink(missing_ok=True)
                release = self.release(package=package)
                received = package[:-10] if failure == "size" else package
                if failure == "digest":
                    release["assets"][0]["digest"] = "sha256:" + "0" * 64
                with patch.object(update, "_download", side_effect=[self.encode(release), received]):
                    report = update.update_skill(self.skill)
                self.assertEqual(report["status"], "failed")
                self.assertFalse(report["repair_required"])
                self.assert_original_files()
                self.assertFalse([path for path in self.skill.glob(".skill-update-*") if path.is_dir()])

    def test_corrupt_zip_member_is_rejected_before_any_installed_file_changes(self):
        """验证 ZIP 成员 CRC 错误先于任何安装文件覆盖被发现。"""
        package, files = self.package()
        corrupt = bytearray(package)
        corrupt[package.index(files["README.md"])] ^= 1
        received = bytes(corrupt)
        with patch.object(update, "_download", side_effect=[self.encode(self.release(package=received)), received]):
            report = update.update_skill(self.skill)
        self.assertEqual(report["status"], "failed")
        self.assertIn("CRC", report["message"])
        self.assertFalse(report["repair_required"])
        self.assert_original_files()

    def test_archive_version_or_file_set_mismatch_keeps_original_installation(self):
        """验证包内版本和额外非清单文件均在覆盖前被拒绝。"""
        for failure in ("version", "unexpected member"):
            with self.subTest(failure=failure):
                (self.skill / update.STATE).unlink(missing_ok=True)
                package, _ = self.package(version="0.1.3" if failure == "version" else "0.1.2")
                if failure == "unexpected member":
                    buffer = BytesIO(package)
                    with ZipFile(buffer, "a") as archive:
                        archive.writestr("unmanaged.txt", b"outside package manifest")
                    package = buffer.getvalue()
                with patch.object(update, "_download", side_effect=[self.encode(self.release(package=package)), package]):
                    report = update.update_skill(self.skill)
                self.assertEqual(report["status"], "failed")
                self.assertFalse(report["repair_required"])
                self.assert_original_files()

    def test_manifest_rejects_paths_outside_managed_skill_files(self):
        """验证发行清单只能管理规范的 Skill 路径。"""
        for name in ("../outside.txt", "scripts/../../outside.txt", "C:/outside.txt",
                     "scripts\\escape.py", "assets/runtimes/python.zip", update.LOCK):
            with self.subTest(name=name):
                manifest = self.manifest("0.1.2", [*self.original_files, name])
                with self.assertRaises(update.UpdateError):
                    update._manifest(self.skill, self.encode(manifest))

    def test_partial_replace_restores_installed_version_and_cleans_new_files(self):
        """验证覆盖失败恢复旧安装，移除新增文件和目录，并保留当日记录。"""
        package, _ = self.package(extra={"scripts/new/module.py": b"new module"})
        replace = Path.replace

        def fail_business_entry(path, target):
            """模拟末尾的新模块无法被替换。"""
            if Path(target) == self.skill / "scripts/new/module.py":
                raise PermissionError("synthetic write restriction")
            return replace(path, target)

        with patch.object(update, "_download", side_effect=[self.encode(self.release(package=package)), package]), \
             patch.object(Path, "replace", fail_business_entry):
            report = update.update_skill(self.skill)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["repair_required"])
        self.assertEqual(self.state()["status"], "failed")
        self.assert_original_files()
        self.assertFalse((self.skill / "scripts/new").exists())
        self.assertFalse((self.skill / "references/current.md").exists())
        self.assertFalse(list(self.skill.glob('.skill-update-*/')))
        self.assertFalse(list(self.skill.rglob('.update-*')))
        with update.skill_in_use(self.skill):
            pass
        with patch.object(update, "_download") as download:
            cached = update.update_skill(self.skill)
        self.assertEqual(cached["last_status"], "failed")
        download.assert_not_called()

    def test_manifest_write_failure_restores_deleted_old_files(self):
        """验证最后写清单失败时恢复已删除的旧文件，并清除本次新增文件。"""
        package, _ = self.package()
        write_json = update._write_json

        def fail_manifest(path, value):
            """模拟旧清单无法被新清单替换。"""
            if path == self.skill / update.MANIFEST:
                raise PermissionError("synthetic manifest restriction")
            write_json(path, value)

        with patch.object(update, "_download", side_effect=[self.encode(self.release(package=package)), package]), \
             patch.object(update, "_write_json", side_effect=fail_manifest):
            report = update.update_skill(self.skill)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["repair_required"])
        self.assert_original_files()
        self.assertFalse((self.skill / "references/current.md").exists())
        self.assertFalse(list(self.skill.glob('.skill-update-*/')))

    def test_shared_business_readers_defer_update_without_consuming_day(self):
        """验证多个业务读取可共存，更新暂缓时保留当天检查机会。"""
        with update.skill_in_use(self.skill), update.skill_in_use(self.skill), \
             patch.object(update, "_download") as download:
            report = update.update_skill(self.skill)
        self.assertEqual(report["status"], "deferred")
        self.assertFalse((self.skill / update.STATE).exists())
        download.assert_not_called()
        with patch.object(update, "_download", return_value=self.encode(self.release(version="0.1.1"))) as download:
            self.assertEqual(update.update_skill(self.skill)["status"], "latest")
        download.assert_called_once_with(update.LATEST_URL)

    def test_exclusive_update_lease_stops_new_business_reader(self):
        """验证更新器持有独占租约时，新业务调用得到明确等待提示。"""
        with update._lease(self.skill, exclusive=True) as acquired:
            self.assertTrue(acquired)
            with self.assertRaisesRegex(update.UpdateError, "正在更新"):
                with update.skill_in_use(self.skill):
                    self.fail("独占更新期间进入了业务代码")

    def test_two_workspace_processes_share_one_installed_skill_lease(self):
        """验证不同工作目录的真实进程共享同一 Skill 租约并在退出后释放。"""
        script = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); import update; "
            "lease = update.skill_in_use(Path(sys.argv[2])); lease.__enter__(); "
            "print('ready', flush=True); sys.stdin.readline(); lease.__exit__(None, None, None)"
        )
        processes = []
        try:
            for number in (1, 2):
                workspace = self.directory / f"工作目录{number}"
                workspace.mkdir()
                process = subprocess.Popen(
                    [sys.executable, "-I", "-B", "-X", "utf8", "-c", script,
                     str(SKILL_ROOT / "scripts"), str(self.skill)],
                    cwd=workspace, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW,
                )
                processes.append(process)
                self.assertEqual(process.stdout.readline().strip(), "ready")
            with patch.object(update, "_download") as download:
                self.assertEqual(update.update_skill(self.skill)["status"], "deferred")
            download.assert_not_called()
            self.assertFalse((self.skill / update.STATE).exists())
        finally:
            for process in processes:
                _, errors = process.communicate("\n", timeout=10)
                self.assertEqual(process.returncode, 0, errors)
        with patch.object(update, "_download", return_value=self.encode(self.release(version="0.1.1"))) as download:
            self.assertEqual(update.update_skill(self.skill)["status"], "latest")
        download.assert_called_once_with(update.LATEST_URL)
