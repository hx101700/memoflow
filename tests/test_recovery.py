"""验证过期会话及强制退出后的自有临时文件回收。"""

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from asr_runtime.application.recovery import finish_session, recover_workspace
from asr_runtime.application.session import Session
from asr_runtime.utils.job_files import read_config
from asr_runtime.utils.session_files import session_directory, write_connection, write_receipt
from asr_runtime.web import create_server
from tests.support import SKILL_ROOT
from tests.test_session import WebFixture

DEAD_PID = 900001


class RecoveryTests(WebFixture):
    def expired_session(self):
        """创建有明确归属的过期编辑会话和合成上传。"""
        session = Session(self.runtime, clock=lambda: 0.0)
        payload = self.payload_for(session)
        write_connection(self.runtime, session.session_id, 12345, session.token, session.deadline)
        directory = session_directory(self.runtime, session.session_id)
        connection = json.loads((directory / "connection.json").read_text(encoding="utf-8"))
        connection["pid"] = DEAD_PID
        (directory / "connection.json").write_text(json.dumps(connection), encoding="utf-8")
        return session, payload, directory

    def recover(self, *, now=8000):
        """将指定合成进程视为已结束，执行实际文件回收。"""
        with patch("asr_runtime.application.recovery.process_is_running", side_effect=lambda pid: pid != DEAD_PID):
            return recover_workspace(self.runtime, now=now)

    def committed_job(self):
        """创建已交接的真实配置文件，保留音频和会话回执。"""
        session, payload, directory = self.expired_session()
        preview = session.validate(payload)
        session.preview_ready(preview["validation_id"])
        receipt = session.confirm()
        return session, directory, read_config(self.runtime, receipt["job_id"])

    def test_expired_dead_session_cleans_all_session_owned_files(self):
        """验证会话Key工作副本和连接临时文件被回收，原录音始终保留。"""
        session, _, directory = self.expired_session()
        for name in (".env", ".tmp_example", f"connection.json.pid-{DEAD_PID}-example.tmp"):
            (directory / name).write_text("synthetic private content", encoding="utf-8")
        formal_key = self.runtime.path(".env")
        formal_key.write_text("DASHSCOPE_API_KEY=synthetic-formal-key", encoding="utf-8")
        report = self.recover()
        self.assertEqual(report["warnings"], [])
        self.assertGreaterEqual(report["removed_items"], 4)
        self.assertFalse(directory.exists())
        self.assertTrue(self.audio.exists())
        self.assertTrue(self.audio.exists())
        self.assertIn("synthetic-formal-key", formal_key.read_text(encoding="utf-8"))
        self.assertEqual(self.recover(), {"removed_items": 0, "warnings": []})

    def test_running_unknown_and_not_yet_expired_sessions_keep_inputs(self):
        """验证进程存活、权限未知或期限未到时保留会话输入。"""
        session, _, directory = self.expired_session()
        for state in (True, None):
            with self.subTest(state=state), patch("asr_runtime.application.recovery.process_is_running", return_value=state):
                report = recover_workspace(self.runtime, now=8000)
            self.assertEqual(report["removed_items"], 0)
            self.assertEqual(bool(report["warnings"]), state is None)
            self.assertTrue(directory.exists())
            self.assertTrue(self.audio.exists())
        self.assertEqual(self.recover(now=7199)["removed_items"], 0)

    def test_committed_job_keeps_audio_receipt_and_formal_outputs(self):
        """验证交接任务只清理进程临时文件，保留所有正式数据。"""
        session, directory, config = self.committed_job()
        job = self.runtime.path(f'.state/jobs/{config["job_id"]}')
        documents = Path(config["document_directory"])
        documents.mkdir(parents=True)
        result = Path(config["json_directory"])
        result.mkdir(parents=True)
        execution = job / "execution"
        execution.mkdir()
        keep = [Path(config["audio"]["path"]), directory / "receipt.json", job / "config.json", job / "config.sha256"]
        for path in (execution / "mono.flac", execution / "status.json", result / "transcription.json",
                     *(documents / f"transcription.{suffix}" for suffix in ("docx", "xlsx", "md"))):
            path.write_bytes(b"preserve task data")
            keep.append(path)
        expected = {path: path.read_bytes() for path in keep}
        temp = documents / f"transcription.partial-pid-{DEAD_PID}-example.docx"
        temp.write_bytes(b"incomplete document")
        status_temp = execution / f"status.json.pid-{DEAD_PID}-example.tmp"
        status_temp.write_bytes(b"incomplete status")
        key_temp = directory / ".tmp_example"
        key_temp.write_bytes(b"synthetic key")
        report = self.recover()
        self.assertEqual(report["warnings"], [])
        for path in (temp, status_temp, key_temp, directory / "connection.json"):
            self.assertFalse(path.exists())
        for path, data in expected.items():
            self.assertEqual(path.read_bytes(), data)

    def test_committed_audio_is_protected_when_receipt_was_removed(self):
        """验证原录音不属于会话清理目标，即使回执缺失也保留。"""
        session, directory, config = self.committed_job()
        (directory / "receipt.json").unlink()
        self.recover()
        self.assertTrue(Path(config["audio"]["path"]).is_file())
        self.assertTrue(self.audio.exists())

    def test_unpublished_candidate_files_are_reclaimed(self):
        """验证强杀留下的未发布配置和热词上下文副本可按会话归属回收。"""
        session, _, directory = self.expired_session()
        job_id = "d" * 32
        candidate = self.runtime.path(f".state/jobs/{job_id}")
        candidate.mkdir(parents=True)
        (candidate / "config.json.tmp").write_text("synthetic context", encoding="utf-8")
        (candidate / "config.sha256").write_text("incomplete", encoding="utf-8")
        write_receipt(self.runtime, session.session_id, {
            "ok": True, "session_id": session.session_id, "job_id": job_id,
            "config_path": str(candidate / "config.json"), "auth_mode": "console",
            "json_directory": "", "document_directory": "", "execution_started": False,
        })
        self.assertEqual(self.recover()["warnings"], [])
        self.assertFalse(candidate.exists())
        self.assertFalse(directory.exists())
        self.assertTrue(self.audio.exists())

    def test_legacy_unknown_files_and_unreadable_metadata_are_preserved(self):
        """验证缺少归属依据的历史文件得到保留和明确提示。"""
        session, _, directory = self.expired_session()
        (directory / "connection.json").write_text('{"port":12345,"token":"synthetic"}', encoding="utf-8")
        unknown = self.runtime.path(".tmp_legacy")
        unknown.write_text("synthetic key", encoding="utf-8")
        report = self.recover()
        self.assertTrue(report["warnings"])
        self.assertTrue(self.audio.exists())
        self.assertTrue(unknown.exists())

    def test_private_python_temp_is_reclaimed_but_child_caches_are_kept(self):
        """验证仅回收带死亡进程归属的Python暂存，不扫描系统或安装缓存。"""
        base = self.runtime.path(".runtime/tmp")
        dead = base / f"python-{DEAD_PID}-example"
        live = base / f"python-{os.getpid()}-example"
        child = base / "pip-unpack-example"
        for path in (dead, live, child):
            path.mkdir(parents=True)
            (path / "openpyxl.example").write_text("synthetic worksheet", encoding="utf-8")
        self.recover()
        self.assertFalse(dead.exists())
        self.assertTrue(live.exists())
        self.assertTrue(child.exists())

    def test_atomic_temp_can_be_cleaned_before_first_connection_publish(self):
        """验证初次连接记录尚未发布时，也能回收有PID归属的临时文件。"""
        directory = self.runtime.path(".state/sessions/" + "e" * 32)
        directory.mkdir(parents=True)
        (directory / f"connection.json.pid-{DEAD_PID}-example.tmp").write_bytes(b"partial private record")
        self.assertEqual(self.recover()["warnings"], [])
        self.assertFalse(directory.exists())

    def test_locked_file_keeps_connection_for_a_later_attempt(self):
        """验证文件占用时保留清理依据，下次启动可继续回收。"""
        session, _, directory = self.expired_session()
        staged = directory / ".env"
        staged.write_text("synthetic key", encoding="utf-8")
        original_unlink = Path.unlink

        def blocked(path, *args, **kwargs):
            """模拟系统暂时占用当前会话的Key暂存文件。"""
            if path == staged:
                raise PermissionError("synthetic lock")
            return original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", blocked):
            self.assertTrue(self.recover()["warnings"])
        self.assertTrue((directory / "connection.json").exists())
        self.assertEqual(self.recover()["warnings"], [])
        self.assertFalse(directory.exists())

    def test_unavailable_document_folder_does_not_block_session_cleanup(self):
        """验证输出目录不可访问时仍清理无关的会话暂存，原始录音保留。"""
        _, _, config = self.committed_job()
        session, _, directory = self.expired_session()
        original_iterdir = Path.iterdir

        def unavailable(path):
            """模拟用户保存位置不可读取，保留其他目录的真实操作。"""
            if path == Path(config["document_directory"]):
                raise PermissionError("synthetic unavailable output")
            return original_iterdir(path)

        Path(config["document_directory"]).mkdir(parents=True)
        with patch.object(Path, "iterdir", unavailable):
            report = self.recover()
        self.assertTrue(report["warnings"])
        self.assertFalse(directory.exists())
        self.assertTrue(self.audio.exists())
        self.assertTrue(Path(config["audio"]["path"]).exists())

    def test_normal_finish_cleans_key_temp_after_request_threads_end(self):
        """验证正常关闭同样清理会话Key暂存并移除连接记录。"""
        server = create_server(self.runtime)
        session = server.session
        self.payload_for(session)
        directory = session_directory(self.runtime, session.session_id)
        (directory / ".tmp_example").write_bytes(b"synthetic key")
        server.server_close()
        self.assertFalse(directory.exists())
        self.assertTrue(self.audio.exists())

    def test_force_killed_service_is_collected_on_the_next_start(self):
        """验证真实子进程强杀后回收Key及Python暂存，所选原录音保持原样。"""
        script = r'''
import io, json, os, sys, threading
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from asr_runtime.application.session import Session
from asr_runtime.utils.environment import Runtime, python_temporary_directory
from asr_runtime.utils.session_files import session_directory
from asr_runtime.web import create_server
from dotenv.main import rewrite
from openpyxl.worksheet._writer import create_temporary_file
runtime = Runtime(Path(sys.argv[2]), Path(sys.argv[1]))
with python_temporary_directory(runtime):
    session = Session(runtime, clock=lambda: 0.0)
    with patch("asr_runtime.web.Session", return_value=session):
        server = create_server(runtime)
    with patch("asr_runtime.utils.path_picker.choose_path", return_value=Path(sys.argv[3])):
        session.select_audio("fixture-audio")
    directory = session_directory(runtime, session.session_id)
    staged = directory / ".env"
    staged.write_text("DASHSCOPE_API_KEY=synthetic-old", encoding="utf-8")
    with rewrite(staged, encoding="utf-8") as (source, target):
        target.write("DASHSCOPE_API_KEY=synthetic-new")
        target.flush()
        Path(create_temporary_file()).write_text("synthetic worksheet", encoding="utf-8")
        print(json.dumps({"session_id":session.session_id,"port":server.server_port}),flush=True)
        server.serve_forever()
'''
        self.runtime.path(".env").write_text("DASHSCOPE_API_KEY=synthetic-formal", encoding="utf-8")
        process = subprocess.Popen([sys.executable, "-I", "-B", "-X", "utf8", "-c", script,
                                    str(SKILL_ROOT), str(self.runtime.workspace), str(self.audio)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        service_handle = None
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        try:
            ready = json.loads(process.stdout.readline())
            directory = session_directory(self.runtime, ready["session_id"])
            owner = json.loads((directory / "connection.json").read_text(encoding="utf-8"))
            # venv启动器PID可能不同；持有本例真实服务的进程句柄后再模拟强杀。
            service_handle = kernel.OpenProcess(0x00100001, False, owner["pid"])
            self.assertTrue(service_handle)
            self.assertEqual(recover_workspace(self.runtime)["removed_items"], 0)
            self.assertTrue(kernel.TerminateProcess(service_handle, 1))
            self.assertEqual(kernel.WaitForSingleObject(service_handle, 5000), 0)
            _, errors = process.communicate(timeout=5)
            self.assertEqual(errors, "")
            self.assertTrue(directory.exists())
            self.assertTrue(list(self.runtime.path(".runtime/tmp").glob("python-*")))
            next_server = create_server(self.runtime)
            try:
                self.assertEqual(next_server.recovery["warnings"], [])
                self.assertGreaterEqual(next_server.recovery["removed_items"], 4)
                self.assertFalse(directory.exists())
                self.assertTrue(self.audio.is_file())
                self.assertFalse(list(self.runtime.path(".runtime/tmp").glob("python-*")))
                self.assertIn("synthetic-formal", self.runtime.path(".env").read_text(encoding="utf-8"))
            finally:
                next_server.server_close()
        finally:
            if service_handle:
                if kernel.WaitForSingleObject(service_handle, 0) == 0x00000102:
                    kernel.TerminateProcess(service_handle, 1)
                    kernel.WaitForSingleObject(service_handle, 5000)
                kernel.CloseHandle(service_handle)
            if process.poll() is None:
                process.kill()
                process.communicate()
