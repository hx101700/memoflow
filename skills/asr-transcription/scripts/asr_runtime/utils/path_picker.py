"""通过本机窗口取得用户选择的音频文件或保存目录。"""

import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Event, Lock
from typing import Literal, cast

from .environment import SetupError
from .i18n import translate

WAIT_SLICE_SECONDS = 0.2


class PathPicker:
    """管理单个文件或目录窗口的打开、取消和关闭。"""

    def __init__(self) -> None:
        """初始化选择窗口状态和取消信号。"""
        self._lock = Lock()
        self._active_id: str | None = None
        self._cancel_event: Event | None = None
        self._cancelled_id: str | None = None
        self._closed = False
        self._finished = Event()
        self._finished.set()

    @staticmethod
    def _check_id(request_id: object) -> str:
        """检查用于关联窗口打开与取消操作的请求编号。"""
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 64:
            raise SetupError("选择请求无效。")
        return request_id

    def select(self, initial: Path, request_id: object, *, mode: Literal["audio", "directory"],
               audio_suffixes: tuple[str, ...] = ()) -> Path | None:
        """等待当前窗口选择，返回所选文件、目录或取消结果。"""
        request_id = self._check_id(request_id)
        with self._lock:
            if self._closed:
                raise SetupError("当前会话已关闭。")
            if self._active_id is not None:
                raise SetupError("请先关闭已打开的选择窗口。")
            if request_id == self._cancelled_id:
                self._cancelled_id = None
                return None
            cancel_event = Event()
            self._active_id = request_id
            self._cancel_event = cancel_event
            self._finished.clear()
        try:
            selected = choose_path(initial, mode=mode, audio_suffixes=audio_suffixes, cancel_event=cancel_event)
            with self._lock:
                return None if self._closed or cancel_event.is_set() else selected
        finally:
            with self._lock:
                self._active_id = None
                self._cancel_event = None
                self._finished.set()

    def cancel(self, request_id: object) -> None:
        """取消指定请求，也允许取消先于该请求的打开操作到达。"""
        request_id = self._check_id(request_id)
        with self._lock:
            if request_id == self._active_id:
                # 活动请求编号与取消事件在select的同一临界区成对登记。
                cast(Event, self._cancel_event).set()
            else:
                # 允许取消先于打开抵达；仅作用于这个ID，不影响下一次选择。
                self._cancelled_id = request_id

    def close(self) -> None:
        """关闭选择器并通知活动窗口取消，短暂等待其回收。"""
        with self._lock:
            self._closed = True
            if self._cancel_event is not None:
                self._cancel_event.set()
        self._finished.wait(timeout=2)


def validate_path(path: Path, *, mode: Literal["audio", "directory"]) -> Path:
    """核对文件或目录的存在性和类型，返回绝对路径。"""
    try:
        resolved = path.resolve(strict=True)
        if mode == "audio" and not resolved.is_file():
            raise SetupError("所选位置不是普通文件，请重新选择。")
        if mode == "directory" and not resolved.is_dir():
            raise SetupError("所选位置不是文件夹，请重新选择。")
        return resolved
    except (OSError, RuntimeError) as exc:
        raise SetupError("所选文件或文件夹不存在或无法访问，请重新选择。") from exc


def choose_path(initial: Path, *, mode: Literal["audio", "directory"],
                audio_suffixes: tuple[str, ...] = (), cancel_event: Event | None = None) -> Path | None:
    """等待用户选择或取消；取消时回收自己的窗口子进程。"""
    if sys.platform != "win32":
        raise SetupError("路径选择窗口目前仅支持 Windows。")
    initial = validate_path(initial, mode="directory")
    cancelled = cancel_event or Event()
    if cancelled.is_set():
        return None
    # GUI只接收系统环境；CREATE_NO_WINDOW隐藏控制台并保留原生选择窗口。
    # Windows Shell用SystemDrive/ProgramData展开系统缓存位置，不能随凭据一起删掉。
    # Tk窗口只依赖基础Python；直接启动它，使取消时终止的就是窗口进程。
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"SYSTEMROOT", "SYSTEMDRIVE", "PROGRAMDATA", "WINDIR", "PATH", "TEMP", "TMP"}}
    try:
        process = subprocess.Popen(
            [str(Path(sys.base_prefix) / "python.exe"), "-I", "-X", "utf8", str(Path(__file__).with_name("_path_dialog.py")),
             str(initial), translate("录音转写 · 选择音频文件" if mode == "audio" else "录音转写 · 选择保存位置"),
             mode, json.dumps(audio_suffixes), translate("音频文件")],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=env, shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError as exc:
        raise SetupError("无法启动选择窗口，请检查 Python 运行环境。") from exc
    try:
        while True:
            if cancelled.is_set():
                return None
            try:
                output, _ = process.communicate(timeout=WAIT_SLICE_SECONDS)
                break
            except subprocess.TimeoutExpired:
                continue  # 仅等待本机窗口；不重开窗口，不重发请求。
        if cancelled.is_set():
            return None
        if process.returncode:
            raise SetupError("选择窗口异常退出，请重新选择。")
        try:
            result = json.loads(output)
            if not isinstance(result, dict):
                raise ValueError
            if "error" in result:
                raise SetupError(str(result["error"]))
            selected = result["path"]
            if selected is not None and not isinstance(selected, str):
                raise ValueError
        except (ValueError, KeyError) as exc:
            raise SetupError("无法读取路径选择结果，请重新选择。") from exc
        return validate_path(Path(selected), mode=mode) if selected else None
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()
