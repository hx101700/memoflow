"""检查本机文件路径与内容身份，并提供JSON原子写入。"""

import hashlib
import json
import os
import tempfile
from collections.abc import Collection, Mapping
from pathlib import Path
from .i18n import translate

from ..models import FileFingerprint, FileStat


class FileError(ValueError):
    """表示可向用户展示的本机文件错误。"""

    def __init__(self, message: str) -> None:
        """保留文件错误原文，并提供当前语言的异常说明。"""
        super().__init__(translate(message))
        self.template = message


def resolve_input(value: object, allowed_suffixes: Collection[str]) -> Path:
    """将所选绝对文件路径规范化，并核对文件类型和扩展名。"""
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise FileError("本机文件位置无效，请重新添加文件。")
    try:
        path = Path(value)
        if not path.is_absolute():
            raise FileError("本机文件位置无效，请重新添加文件。")
        path = path.resolve(strict=True)
        if not path.is_file():
            raise FileError("请选择普通文件，不能选择目录。")
        if path.suffix.lower() not in allowed_suffixes:
            raise FileError("文件扩展名不在允许的格式范围内。")
        return path
    except (OSError, RuntimeError) as exc:
        raise FileError("无法读取指定文件，请检查路径和访问权限。") from exc


def file_fingerprint(path: Path) -> FileFingerprint:
    """读取完整内容建立SHA基线，并检查读取期间的常规修改。"""
    try:
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                after.st_size, after.st_mtime_ns, after.st_ino):
            raise FileError("文件在校验期间发生变化，请重新校验。")
        return {"size_bytes": after.st_size, "mtime_ns": after.st_mtime_ns,
                "sha256": digest.hexdigest()}
    except OSError as exc:
        raise FileError("无法读取文件，请检查访问权限后重新校验。") from exc


def check_file_unchanged(path: Path, fingerprint: FileStat) -> None:
    """比较文件大小与修改时间，检查文件是否发生变化。"""
    current = path.stat()
    if (current.st_size, current.st_mtime_ns) != (
            fingerprint["size_bytes"], fingerprint["mtime_ns"]):
        raise FileError("文件在校验期间发生变化，请重新校验。")


def write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    """写入JSON临时文件，再原子替换目标记录。"""
    stream = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f"{path.name}.pid-{os.getpid()}-", suffix=".tmp", delete=False)
    temporary = Path(stream.name)
    try:
        with stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
