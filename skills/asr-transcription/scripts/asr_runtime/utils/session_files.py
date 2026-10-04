"""保存本机编辑会话的连接信息与持久交接回执。"""

import json
import re
from pathlib import Path
from typing import TypedDict, cast

from ..models import ConfirmationReceipt
from .environment import Runtime, SetupError
from .files import write_json_atomic
from .job_files import job_directory


class SessionConnection(TypedDict):
    """描述本机控制命令需要的端口与请求令牌。"""

    port: int
    token: str


def session_directory(runtime: Runtime, session_id: str) -> Path:
    """定位指定编辑会话的私有记录目录。"""
    if not re.fullmatch(r"[0-9a-f]{32}", session_id):
        raise SetupError("会话编号无效，请复制预览页中的完整确认文字。")
    return runtime.path(f".state/sessions/{session_id}")


def write_connection(runtime: Runtime, session_id: str, port: int, token: str) -> None:
    """将连接凭据保存在对应会话目录，供本机命令读取。"""
    directory = session_directory(runtime, session_id)
    directory.mkdir(parents=True, exist_ok=True)
    write_json_atomic(directory / "connection.json", {"port": port, "token": token})


def read_connection(runtime: Runtime, session_id: str) -> SessionConnection:
    """读取仍在提供编辑服务的会话连接信息。"""
    try:
        value = json.loads((session_directory(runtime, session_id) / "connection.json").read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or type(value.get("port")) is not int
                or not 1 <= value["port"] <= 65535
                or not isinstance(value.get("token"), str) or not value["token"]):
            raise ValueError("invalid connection")
        return cast(SessionConnection, value)
    except (OSError, ValueError) as exc:
        raise SetupError("此编辑会话已结束或连接信息不可用，请重新打开配置页。") from exc


def remove_connection(runtime: Runtime, session_id: str) -> None:
    """移除已结束会话的临时连接凭据。"""
    (session_directory(runtime, session_id) / "connection.json").unlink(missing_ok=True)


def write_receipt(runtime: Runtime, session_id: str, receipt: ConfirmationReceipt) -> None:
    """持久保存会话对应的唯一任务回执。"""
    directory = session_directory(runtime, session_id)
    directory.mkdir(parents=True, exist_ok=True)
    write_json_atomic(directory / "receipt.json", receipt)


def read_receipt(runtime: Runtime, session_id: str) -> ConfirmationReceipt | None:
    """读取已完成的交接，供响应丢失或服务结束后找回同一任务。"""
    path = session_directory(runtime, session_id) / "receipt.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or value.get("session_id") != session_id
                or not isinstance(value.get("job_id"), str)
                or not re.fullmatch(r"[0-9a-f]{32}", value["job_id"])):
            raise ValueError("invalid receipt")
        # 配置文件在摘要落盘后才原子发布；它是本次交接完成的标记。
        if not (job_directory(runtime, value["job_id"]) / "config.json").is_file():
            return None
        return cast(ConfirmationReceipt, value)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise SetupError("无法读取会话交接回执，请检查工作目录中的会话记录。") from exc
