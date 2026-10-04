"""回收已结束操作的自有临时文件，保留任务、结果与正式凭据。"""

import re
import shutil
import time
from pathlib import Path
from typing import TypedDict

from ..utils.environment import Runtime, SetupError, process_is_running
from ..utils.job_files import document_directory, job_directory, read_config
from ..utils.session_files import read_connection, read_receipt, session_directory

IDENTIFIER = re.compile(r"[0-9a-f]{32}")
JSON_TEMP = re.compile(r"(?:connection|receipt|status)\.json\.pid-(\d+)-[a-z0-9_]+\.tmp")
DOCUMENT_TEMP = re.compile(r"transcription\.partial-pid-(\d+)-[a-z0-9_]+\.(?:xlsx|docx|md)")
PYTHON_TEMP = re.compile(r"python-(\d+)-[a-z0-9_]+")


class CleanupReport(TypedDict):
    """记录已回收条目和需要保留处理的问题。"""

    removed_items: int
    warnings: list[str]


def _entries(directory: Path) -> list[Path]:
    """读取原位置的目录内容，拒绝经链接重定向的清理目标。"""
    if directory.resolve() != directory:
        raise SetupError("清理目录被重定向，已保留。")
    if not directory.exists():
        return []
    return list(directory.iterdir())


def _remove_file(path: Path, report: CleanupReport) -> None:
    """删除自有普通临时文件并累计实际回收数量。"""
    if path.resolve() != path or path.is_dir():
        raise SetupError("临时文件类型或位置发生变化，已保留。")
    try:
        path.unlink()
        report["removed_items"] += 1
    except FileNotFoundError:
        pass


def _remove_empty(directory: Path) -> None:
    """移除已经清空的操作目录。"""
    if directory.exists() and not _entries(directory):
        try:
            directory.rmdir()
        except FileNotFoundError:
            pass


def finish_session(runtime: Runtime, session_id: str) -> CleanupReport:
    """在服务及请求结束后清理会话暂存，保留已交接回执。"""
    report: CleanupReport = {"removed_items": 0, "warnings": []}
    try:
        directory = session_directory(runtime, session_id)
        entries = _entries(directory)
        receipt = read_receipt(runtime, session_id, require_committed=False)
        committed = False
        if receipt:
            candidate = job_directory(runtime, receipt["job_id"])
            _entries(candidate)
            committed = (candidate / "config.json").exists()
            if not committed:
                if (candidate / "execution").exists() or (candidate / "delivery").exists():
                    raise SetupError("任务记录与交接状态不一致，已保留。")
                for name in ("config.json.tmp", "config.sha256"):
                    _remove_file(candidate / name, report)
                _remove_empty(candidate)

        for path in entries:
            if path.name in ("connection.json", "receipt.json"):
                continue
            if path.name == ".env" or re.fullmatch(r"\.tmp_[a-z0-9_]+", path.name) or JSON_TEMP.fullmatch(path.name):
                _remove_file(path, report)
            else:
                raise SetupError("会话记录目录含未知文件，已保留。")
        if not committed:
            _remove_file(directory / "receipt.json", report)
        # 连接记录也保存所属进程和截止时间；前面清理失败时保留它供下次处理。
        _remove_file(directory / "connection.json", report)
        _remove_empty(directory)
    except (OSError, SetupError, ValueError, KeyError, TypeError):
        report["warnings"].append(f"会话 {session_id} 的残留未能完全清理；已保留记录，请检查权限或文件归属。")
    return report


def _clean_pid_files(directory: Path, pattern: re.Pattern[str], report: CleanupReport) -> None:
    """清除命名包含已结束进程编号的临时文件，保留存活或未知归属。"""
    for path in _entries(directory):
        match = pattern.fullmatch(path.name)
        if match is None:
            continue
        state = process_is_running(int(match[1]))
        if state is False:
            _remove_file(path, report)
        elif state is None:
            report["warnings"].append(f"无法确认进程 {match[1]} 的状态，已保留其临时文件。")


def recover_workspace(runtime: Runtime, *, now: float | None = None) -> CleanupReport:
    """启动网页前回收过期且已结束的会话及死进程所属的操作临时文件。"""
    report: CleanupReport = {"removed_items": 0, "warnings": []}
    deadline_now = time.time() if now is None else now
    try:
        jobs = _entries(runtime.root / ".state/jobs")
    except (OSError, SetupError):
        jobs = []
        report["warnings"].append("任务目录不可读，已保留其文件。")
    for directory in jobs:
        if not IDENTIFIER.fullmatch(directory.name):
            continue
        try:
            _entries(directory)
            config = read_config(runtime, directory.name) if (directory / "config.json").exists() else None
        except (OSError, SetupError, ValueError, KeyError, TypeError):
            report["warnings"].append(f"任务 {directory.name} 的配置不可读，已保留任务文件。")
            continue
        try:
            if config:
                destination = document_directory(config)
                runtime.check_output_path(destination)
                _clean_pid_files(destination, DOCUMENT_TEMP, report)
            for name in ("execution", "delivery"):
                _clean_pid_files(directory / name, JSON_TEMP, report)
        except (OSError, SetupError, ValueError, KeyError, TypeError):
            report["warnings"].append(f"任务 {directory.name} 的部分临时文件未能清理，已保留。")

    try:
        sessions = _entries(runtime.root / ".state/sessions")
    except (OSError, SetupError):
        sessions = []
        report["warnings"].append("会话目录不可读，已保留其文件。")
    for directory in sessions:
        if not IDENTIFIER.fullmatch(directory.name):
            continue
        try:
            _clean_pid_files(directory, JSON_TEMP, report)
            if not (directory / "connection.json").exists():
                if any(path.name != "receipt.json" for path in _entries(directory)):
                    report["warnings"].append(f"会话 {directory.name} 缺少清理依据，已保留未知文件。")
                _remove_empty(directory)
                continue
            connection = read_connection(runtime, directory.name)
            if connection["deadline"] > deadline_now:
                continue
            state = process_is_running(connection["pid"])
            if state is False:
                recovered = finish_session(runtime, directory.name)
                report["removed_items"] += recovered["removed_items"]
                report["warnings"].extend(recovered["warnings"])
            elif state is None:
                report["warnings"].append(f"无法确认会话 {directory.name} 的原服务状态，已保留其文件。")
        except (OSError, SetupError, ValueError):
            report["warnings"].append(f"会话 {directory.name} 的清理依据不完整，已保留其文件。")

    try:
        for directory in _entries(runtime.root / ".runtime/tmp"):
            match = PYTHON_TEMP.fullmatch(directory.name)
            if match is None:
                continue
            state = process_is_running(int(match[1]))
            if state is False:
                # 仅回收本程序创建的进程目录，解析后的绝对位置必须保持原样。
                _entries(directory)
                shutil.rmtree(directory)
                report["removed_items"] += 1
            elif state is None:
                report["warnings"].append(f"无法确认进程 {match[1]} 的状态，已保留其 Python 临时目录。")
    except (OSError, SetupError):
        report["warnings"].append("部分 Python 临时目录未能清理，请检查访问权限。")
    return report
