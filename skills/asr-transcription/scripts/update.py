"""每天检查正式 Release，用轻量包直接更新闲置的 Skill。"""

import argparse
import ctypes
from ctypes import wintypes
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
import hashlib
from http.client import IncompleteRead
from io import BytesIO, TextIOWrapper
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import TypedDict, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

MANIFEST = "skill-manifest.json"
STATE = ".skill-update-state.json"
LOCK = "assets/update.lock"
REPOSITORY = "hx101700/memoflow"
LATEST_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"


class UpdateError(Exception):
    """表示可向用户解释的安装或更新问题。"""


class Manifest(TypedDict):
    """记录包版本及更新器负责覆盖和删除的文件。"""

    schema_version: int
    name: str
    version: str
    files: list[str]


class UpdateReport(TypedDict, total=False):
    """向 Codex 返回版本判断、更新结果与后续动作。"""

    status: str
    installed_version: str
    latest_version: str | None
    is_latest: bool | None
    checked_on: str
    last_status: str
    repair_required: bool
    record_error: str
    message: str


def _json(data: bytes) -> dict[str, object]:
    """解析更新协议中的 JSON 对象。"""
    value = json.loads(data)
    if not isinstance(value, dict):
        raise UpdateError("更新资料格式不正确。")
    return cast(dict[str, object], value)


def _target(root: Path, relative: str) -> Path:
    """将发行文件名定位到当前 Skill 内的规范路径。"""
    path = PurePosixPath(relative)
    allowed = relative in {"SKILL.md", "LICENSE", "README.md", "README.en.md"} or (
        bool(path.parts) and path.parts[0] in {"scripts", "references", "agents", "assets"}
    )
    if (not allowed or path.is_absolute() or ".." in path.parts or "\\" in relative
            or ":" in relative or path.as_posix() != relative
            or relative == LOCK or relative.startswith("assets/runtimes/")):
        raise UpdateError("更新清单含有管理范围之外的路径。")
    destination = root / relative
    if not destination.resolve().is_relative_to(root):
        raise UpdateError("更新目标不能指向 Skill 目录之外。")
    return destination


def _manifest(root: Path, data: bytes) -> Manifest:
    """校验单一版本的发行清单及文件记录。"""
    value = _json(data)
    version = value.get("version")
    files = value.get("files")
    if (value.get("schema_version") != 1 or value.get("name") != "asr-transcription"
            or not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version)
            or not isinstance(files, list) or not all(isinstance(name, str) for name in files)
            or len(set(files)) != len(files)
            or not {"SKILL.md", "scripts/asr.py", "scripts/update.py"} <= set(files)):
        raise UpdateError("发行清单的版本或格式不受支持。")
    for relative in files:
        _target(root, relative)
    return cast(Manifest, value)


def _write_bytes(path: Path, data: bytes) -> None:
    """通过同目录暂存文件完整替换目标内容。"""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".update-", delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_json(path: Path, value: object) -> None:
    """发布 UTF-8 编码的更新状态或发行清单。"""
    _write_bytes(path, (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))


def _prepare_parent(path: Path, created: list[Path]) -> None:
    """创建目标父目录并记录本次新增目录，供失败时清理。"""
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir()
        created.append(directory)


def _restore(root: Path, originals: dict[str, bytes | None], modified: list[str], created: list[Path]) -> None:
    """恢复本次已修改的文件，并移除新增文件与空目录。"""
    for name in reversed(modified):
        data = originals[name]
        if data is None:
            (root / name).unlink(missing_ok=True)
        else:
            _write_bytes(root / name, data)
    for directory in reversed(created):
        directory.rmdir()


def _state(root: Path) -> dict[str, object]:
    """读取当前安装目录的日检记录。"""
    path = root / STATE
    return _json(path.read_bytes()) if path.exists() else {}


def _incomplete(root: Path, state: dict[str, object]) -> bool:
    """用最后发布的清单判断文件替换是否完整结束。"""
    if state.get("status") != "applying":
        return False
    # 新清单在全部文件替换之后发布，是本次更新完成的标记。
    return _json((root / MANIFEST).read_bytes()).get("version") != state.get("target_version")


@contextmanager
def _lease(root: Path, *, exclusive: bool) -> Iterator[bool]:
    """用稳定哨兵的 Windows 共享参数协调读取和独占更新。"""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    # 所有调用只读打开同一哨兵；更新器的share=0会与正在读取的业务进程互斥。
    handle = kernel.CreateFileW(str(root / LOCK), 0x80000000, 0 if exclusive else 1, None, 3, 128, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        if error == 32:  # ERROR_SHARING_VIOLATION
            yield False
            return
        raise ctypes.WinError(error)
    try:
        yield True
    finally:
        kernel.CloseHandle(handle)


@contextmanager
def skill_in_use(root: Path) -> Iterator[None]:
    """在业务模块加载及执行期间保持同一套 Skill 文件。"""
    root = root.resolve()
    if not (root / MANIFEST).is_file():
        yield
        return
    with _lease(root, exclusive=False) as acquired:
        if not acquired:
            raise UpdateError("Skill 正在更新，请等待更新结束后再运行。")
        if _incomplete(root, _state(root)):
            raise UpdateError("上次 Skill 文件更新未完成，请重新安装最新 ZIP。")
        yield


def _download(url: str) -> bytes:
    """读取公开发行资料，返回服务器响应的原始字节。"""
    request = Request(url, headers={"User-Agent": "MemoFlow-skill-update", "Accept": "application/vnd.github+json"})
    try:
        with urlopen(request, timeout=30) as response:
            return cast(bytes, response.read())
    except IncompleteRead as error:
        raise UpdateError("更新下载连接提前结束，文件未完整接收。") from error


def _unpack(root: Path, data: bytes, tag: str, directory: Path) -> Manifest:
    """核对轻量包版本与清单，在替换前读完全部文件并验证 ZIP CRC。"""
    with ZipFile(BytesIO(data)) as archive:
        manifest = _manifest(root, archive.read(MANIFEST))
        if "v" + manifest["version"] != tag:
            raise UpdateError("轻量包与正式版本不一致。")
        expected = set(manifest["files"]) | {MANIFEST, LOCK}
        if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
            raise UpdateError("轻量包内容与发行清单不一致。")
        archive.read(LOCK)
        for name in manifest["files"]:
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
        return manifest


def update_skill(root: Path, *, check_now: bool = False) -> UpdateReport:
    """执行每日自动检查或用户主动检查，用新轻量包覆盖当前安装。"""
    root = root.resolve()
    if not (root / MANIFEST).is_file():
        return {"status": "unmanaged", "is_latest": None, "message": "当前目录没有发行清单，保留源码或现有安装。"}
    with _lease(root, exclusive=True) as acquired:
        if not acquired:
            return {"status": "deferred", "is_latest": None, "message": "有命令正在使用此 Skill，暂缓更新检查。"}
        current = _manifest(root, (root / MANIFEST).read_bytes())
        state = _state(root)
        if _incomplete(root, state):
            return {"status": "failed", "repair_required": True, "is_latest": None,
                    "message": "上次 Skill 文件更新未完成，请重新安装最新 ZIP。"}
        today = date.today().isoformat()
        if not check_now and state.get("checked_on") == today:
            cached = state.get("report")
            report = cast(UpdateReport, dict(cached)) if isinstance(cached, dict) else UpdateReport(is_latest=None)
            last_status = str(state.get("status"))
            if last_status == "applying":
                # 新清单已发布，说明文件更新完成，仅最终日检记录尚未写入。
                last_status = "updated"
                report.update({"installed_version": current["version"], "latest_version": current["version"],
                               "is_latest": True, "message": "Skill 文件更新已完成，沿用当天版本检查结果。"})
            return {**report, "status": "checked_today", "last_status": last_status,
                    "installed_version": current["version"], "checked_on": today}

        report = UpdateReport(status="checking", installed_version=current["version"],
                              latest_version=None, is_latest=None, checked_on=today)
        # 先登记检查日期，网络失败或进程退出也消耗当日检查机会。
        state = {"checked_on": today, "status": "checking", "report": report}
        try:
            _write_json(root / STATE, state)
        except OSError as error:
            report.update({"status": "failed", "repair_required": False, "record_error": str(error),
                           "message": f"更新检查记录保存失败，已跳过本次联网检查。可继续使用当前安装 v{current['version']}。"})
            return report
        print(f"正在检查 Skill 正式版本（当前 v{current['version']}）。", file=sys.stderr, flush=True)
        applying = False
        originals: dict[str, bytes | None] = {}
        modified: list[str] = []
        created: list[Path] = []
        try:
            release = _json(_download(LATEST_URL))
            tag = release.get("tag_name")
            if (not isinstance(tag, str) or not re.fullmatch(r"v\d+\.\d+\.\d+", tag)
                    or release.get("draft") is not False or release.get("prerelease") is not False):
                raise UpdateError("最新正式版本的发布资料不正确。")
            latest = tag[1:]
            report["latest_version"] = latest
            remote_version = tuple(map(int, latest.split(".")))
            installed_version = tuple(map(int, current["version"].split(".")))
            if remote_version == installed_version:
                report.update({"status": "latest", "is_latest": True,
                               "message": "当前安装版本与最新正式版一致。"})
            elif remote_version < installed_version:
                report.update({"status": "local_ahead", "message": "当前安装版本高于最新正式版，保留当前文件。"})
            else:
                report["is_latest"] = False
                assets = release.get("assets")
                asset = None
                if isinstance(assets, list):
                    for item in assets:
                        if isinstance(item, dict) and item.get("name") == "asr-transcription-lite.zip":
                            asset = item
                            break
                if asset is None:
                    raise UpdateError("最新正式版尚未提供轻量安装包。")
                print(f"发现新版 v{latest}，正在下载轻量包并更新 Skill（当前 v{current['version']}）。",
                      file=sys.stderr, flush=True)
                data = _download(f"https://github.com/{REPOSITORY}/releases/download/{tag}/asr-transcription-lite.zip")
                if len(data) != asset.get("size"):
                    raise UpdateError("轻量包下载不完整。")
                digest = asset.get("digest")
                if isinstance(digest, str) and digest.startswith("sha256:") and digest[7:] != hashlib.sha256(data).hexdigest():
                    raise UpdateError("轻量包 SHA-256 与 GitHub 发布记录不一致。")
                with tempfile.TemporaryDirectory(prefix=".skill-update-", dir=root) as staging:
                    directory = Path(staging)
                    remote = _unpack(root, data, tag, directory)
                    print("轻量包校验完成，正在更新 Skill 文件。", file=sys.stderr, flush=True)
                    removed = sorted(set(current["files"]) - set(remote["files"]))
                    # 原文件只在本次进程内保存，覆盖失败后恢复原安装。
                    originals = {name: (root / name).read_bytes() if (root / name).exists() else None
                                 for name in [*remote["files"], *removed, MANIFEST]}
                    state.update(status="applying", target_version=latest)
                    _write_json(root / STATE, state)
                    applying = True
                    for name in remote["files"]:
                        target = _target(root, name)
                        _prepare_parent(target, created)
                        (directory / name).replace(target)
                        modified.append(name)
                    for name in removed:
                        _target(root, name).unlink(missing_ok=True)
                        modified.append(name)
                    _write_json(root / MANIFEST, remote)
                    modified.append(MANIFEST)
                report.update({"status": "updated", "installed_version": latest, "is_latest": True,
                               "message": "Skill 已更新，请重新读取 SKILL.md 并按当前说明准备工作目录环境。"})
        except (OSError, ValueError, KeyError, BadZipFile, UpdateError) as error:
            message = f"更新请求失败（HTTP {error.code}）。" if isinstance(error, HTTPError) else (
                "更新网络连接失败。" if isinstance(error, URLError) else str(error)
            )
            if applying:
                try:
                    _restore(root, originals, modified, created)
                    applying = False
                    message += " 已恢复更新前的安装版本。"
                except OSError as restore_error:
                    message += " 恢复原安装未完成：" + str(restore_error)
            if not applying:
                report["installed_version"] = current["version"]
                message += f" 可继续使用当前安装 v{current['version']}。"
            report.update({"status": "failed", "repair_required": applying, "message": message})
        if not applying or report["status"] == "updated":
            state["status"] = report["status"]
        state["report"] = report
        try:
            _write_json(root / STATE, state)
        except OSError as error:
            # 文件结果已经确定，检查记录保存失败作为独立问题返回。
            report["record_error"] = str(error)
        return report


def main() -> int:
    """执行一次自动检查入口，并打印适合 Codex 读取的回执。"""
    parser = argparse.ArgumentParser(description="按机器本地日期，每天最多检查一次 Skill 正式更新。")
    parser.add_argument("--check-now", action="store_true", help="按用户明确要求立即检查，并计入当日检查记录")
    options = parser.parse_args()
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        report = update_skill(Path(__file__).resolve().parents[1], check_now=options.check_now)
    except (OSError, ValueError, UpdateError) as error:
        report = {"status": "failed", "repair_required": True, "is_latest": None,
                  "message": f"无法确认当前 Skill 安装状态，请先修复安装或重新安装最新 ZIP。{error}"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get("repair_required") else 0


if __name__ == "__main__":
    raise SystemExit(main())
