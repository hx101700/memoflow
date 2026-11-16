"""提供指定转写任务的本机回听页面、草稿操作和音频分段读取。"""

import http.client
import json
import mimetypes
import os
from pathlib import Path
import re
import select
import secrets
import socket
import sys
from threading import Event, Lock, Timer
from typing import Literal, cast
from urllib.parse import urlsplit
import webbrowser

from .application.review import ReviewSession, ReviewConflict
from .application.rules import ValidationError
from .utils.environment import Runtime, SetupError, process_is_running
from .utils.files import write_json_atomic
from .utils.i18n import language_scope, localize
from .utils.job_files import job_directory
from .utils.local_http import LocalHTTPServer, LocalHandler, RequestError, STATIC, STATIC_ROUTES


class ReviewServer(LocalHTTPServer):
    """管理一个任务的校验页面和本次服务连接信息。"""

    session: ReviewSession
    connection_path: Path
    page_close_grace = 10.0

    def __init__(self, address: tuple[str, int], handler: type[LocalHandler], *, bind_and_activate: bool = True) -> None:
        """跟踪打开的页面连接，为刷新保留短暂的重新连接时间。"""
        self._page_lock = Lock()
        self._pages = 0
        self._close_timer: Timer | None = None
        self.stopping = Event()
        super().__init__(address, handler, bind_and_activate=bind_and_activate)

    def page_connected(self) -> bool:
        """登记实际打开的页面，并取消等待中的无人使用关闭计时。"""
        with self._page_lock:
            if self.stopping.is_set():
                return False
            self._pages += 1
            if self._close_timer is not None:
                self._close_timer.cancel()
                self._close_timer = None
            return True

    def page_disconnected(self) -> None:
        """最后一个页面离开后安排收尾，刷新重连可以继续使用服务。"""
        with self._page_lock:
            self._pages -= 1
            if self._pages == 0 and not self.stopping.is_set():
                self._close_timer = Timer(self.page_close_grace, self._close_unused)
                self._close_timer.daemon = True
                self._close_timer.start()

    def _close_unused(self) -> None:
        """到宽限期仍无页面连接时停止本次服务，保留已保存稿件。"""
        with self._page_lock:
            if self._pages or self.stopping.is_set():
                return
            self.stopping.set()
        self.session.close()
        self.shutdown()

    def server_close(self) -> None:
        """释放原生窗口及请求线程，然后移除本次连接信息。"""
        try:
            self.stopping.set()
            if self._close_timer is not None:
                self._close_timer.cancel()
            self.session.close()
            super().server_close()
        finally:
            self.connection_path.unlink(missing_ok=True)


def audio_range(value: str | None, size: int) -> tuple[int, int]:
    """解析浏览器单段或尾部字节范围，返回包含端点的读取区间。"""
    if value is None:
        return 0, size - 1
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if not match or not any(match.groups()) or size <= 0:
        raise ValueError("invalid range")
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if suffix <= 0:
            raise ValueError("invalid suffix")
        return max(0, size - suffix), size - 1
    start, end = int(first), min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise ValueError("unsatisfied range")
    return start, end


def create_review_server(runtime: Runtime, job_id: str, port: int = 0) -> ReviewServer:
    """打开已完成任务的校验用例并注册受保护的本机接口。"""
    session = ReviewSession(runtime, job_id)

    class Handler(LocalHandler):
        server: ReviewServer

        def track_page(self) -> None:
            """通过持久连接读取浏览器断开信号，跟踪页面生命周期。"""
            if not self.server.page_connected():
                self.json(410, {"ok": False, "error": localize("当前编辑会话已关闭。")})
                return
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while not self.server.stopping.is_set():
                    readable, _, _ = select.select([self.connection], [], [], 1)
                    if readable:
                        # EventSource不会继续发送请求体；EOF说明页面已释放此连接。
                        self.connection.recv(1, socket.MSG_PEEK)
                        break
            except (OSError, ValueError):
                pass  # 标签关闭或浏览器退出会取消连接。
            finally:
                self.server.page_disconnected()

        def send_audio(self, *, head: bool = False) -> None:
            """按Range读取当前任务绑定的音频，支持跳转与HEAD请求。"""
            path = session.audio_path()
            with path.open("rb") as audio:
                size = os.fstat(audio.fileno()).st_size
                requested = self.headers.get("Range")
                try:
                    start, end = audio_range(requested, size)
                except ValueError:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(206 if requested else 200)
                self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(max(0, end - start + 1)))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                if requested:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                if head:
                    return
                audio.seek(start)
                remaining = end - start + 1
                try:
                    while remaining > 0:
                        chunk = audio.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                except ConnectionError:
                    return  # 浏览器跳转时会取消原来的媒体读取。

        def error_response(self, error: Exception) -> None:
            """返回字段诊断及保存冲突，文件异常给出可操作的双语说明。"""
            if isinstance(error, ValidationError):
                self.json(409 if isinstance(error, ReviewConflict) else 422,
                          {"ok": False, "error": error.message, "field": error.field, "details": error.details})
            else:
                self.json(422, {"ok": False, "error": localize("本地文件操作未完成，请检查路径与访问权限。")})

        def do_GET(self) -> None:
            """读取校验页面、当前草稿及本任务音频。"""
            with language_scope(self.headers.get("Accept-Language", "zh-CN")):
                path = urlsplit(self.path).path
                static = {**STATIC_ROUTES, "/review": STATIC_ROUTES["/"]}
                if not self.allowed(authenticated=path not in static):
                    return
                try:
                    if path in static:
                        name, content_type = static[path]
                        self.send(200, (STATIC / name).read_bytes(), content_type, cookie=path in ("/", "/review"))
                    elif path == "/api/review":
                        self.json(200, session.description())
                    elif path == "/api/review/audio":
                        self.send_audio()
                    elif path == "/api/review/presence":
                        self.track_page()
                    else:
                        self.json(404, {"ok": False, "error": localize("未找到此页面或接口。")})
                except (ValidationError, SetupError, OSError) as error:
                    self.error_response(error)

        def do_HEAD(self) -> None:
            """提供音频元信息而不发送文件正文。"""
            if not self.allowed():
                return
            if urlsplit(self.path).path != "/api/review/audio":
                self.send_error(404)
                return
            try:
                self.send_audio(head=True)
            except (ValidationError, SetupError, OSError):
                self.send_response(422)
                self.send_header("Content-Length", "0")
                self.end_headers()

        def do_POST(self) -> None:
            """分派保存、音频定位、本机导出和结束校验操作。"""
            with language_scope(self.headers.get("Accept-Language", "zh-CN")):
                if not self.allowed():
                    return
                path = urlsplit(self.path).path
                try:
                    payload = self.read_json()
                    if path == "/api/review/save":
                        self.json(200, session.save(payload))
                    elif path == "/api/review/export":
                        self.json(200, session.export(payload))
                    elif path == "/api/review/select-audio":
                        self.json(200, session.select_audio(payload.get("picker_id")))
                    elif path == "/api/review/prepare-audio":
                        self.json(200, session.prepare_audio())
                    elif path == "/api/review/close":
                        self.server.stopping.set()
                        session.close()
                        try:
                            self.json(200, {"closed": True})
                        finally:
                            # 浏览器取消响应也必须收尾，避免留下已关闭但仍占用任务的服务。
                            self.server.shutdown()
                    else:
                        self.json(404, {"ok": False, "error": localize("未找到此接口。")})
                except (ValidationError, SetupError, OSError) as error:
                    self.error_response(error)
                except RequestError as error:
                    self.json(error.status, {"ok": False, "error": localize(str(error))})
                except (ValueError, TypeError):
                    self.json(400, {"ok": False, "error": localize("请求格式不正确。")})

    directory = job_directory(runtime, job_id) / "review"
    directory.mkdir(exist_ok=True)
    server = ReviewServer(("127.0.0.1", port), Handler, bind_and_activate=False)
    server.session = session
    server.token = secrets.token_urlsafe(32)
    server.connection_path = directory / "connection.json"
    try:
        server.server_bind()
        server.server_activate()
        write_json_atomic(server.connection_path, {"port": server.server_port, "token": server.token, "pid": os.getpid()})
    except BaseException:
        server.server_close()
        raise
    return server


def _connection(runtime: Runtime, job_id: str) -> dict[str, object] | None:
    """读取该任务的临时连接资料，缺失时表示没有登记服务。"""
    path = job_directory(runtime, job_id) / "review/connection.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_bytes())
        if (not isinstance(value, dict) or type(value.get("port")) is not int
                or not 0 < value["port"] < 65536 or not isinstance(value.get("token"), str)
                or type(value.get("pid")) is not int):
            raise ValueError("invalid connection")
        return cast(dict[str, object], value)
    except (ValueError, OSError) as error:
        raise SetupError("无法读取本次校验页面的连接记录，请检查任务目录。") from error


def _request(info: dict[str, object], *, close: bool) -> dict[str, object]:
    """通过现有服务的私有令牌查询或关闭校验页面。"""
    origin = f"http://127.0.0.1:{info['port']}"
    connection = http.client.HTTPConnection("127.0.0.1", cast(int, info["port"]), timeout=15)
    try:
        connection.request("POST" if close else "GET", "/api/review/close" if close else "/api/review",
                           body=b"{}" if close else None, headers={"Origin": origin,
                           "Content-Type": "application/json", "X-ASR-Token": cast(str, info["token"])})
        response = connection.getresponse()
        payload = json.loads(response.read())
        if response.status != 200 or not isinstance(payload, dict):
            raise SetupError("校验页面未完成本次操作，请检查原服务。")
        return cast(dict[str, object], payload)
    finally:
        connection.close()


def control_review(runtime: Runtime, job_id: str) -> dict[str, object]:
    """结束该任务的活动校验服务，保留已保存的草稿和文件。"""
    info = _connection(runtime, job_id)
    if info is None:
        return {"closed": True, "job_id": job_id}
    try:
        return {**_request(info, close=True), "job_id": job_id}
    except (OSError, ValueError, http.client.HTTPException) as error:
        raise SetupError("未取得结束校验回执，请检查原服务；已保存草稿保留。") from error


def serve_review(runtime: Runtime, job_id: str, *, port: int = 0, open_browser: bool = True) -> None:
    """启动或复用同一任务的校验页面，输出不含令牌的启动回执。"""
    info = _connection(runtime, job_id)
    server: ReviewServer | None = None
    if info is not None:
        try:
            existing = _request(info, close=False)
            if existing.get("job_id") != job_id:
                raise SetupError("活动校验页面与任务编号不符。")
            if existing.get("closed"):
                raise SetupError("原校验页面正在结束，请等待原进程退出后重新打开。")
        except (OSError, ValueError, http.client.HTTPException):
            if process_is_running(cast(int, info["pid"])) is not False:
                raise SetupError("原校验进程仍在运行或状态不明，请先检查原服务。")
            info = None
    if info is None:
        server = create_review_server(runtime, job_id, port)
        info = {"port": server.server_port, "pid": os.getpid()}
    url = f"http://127.0.0.1:{info['port']}/review"
    try:
        opened: Literal["skipped", "requested", "failed"] = "skipped"
        if open_browser:
            try:
                opened = "requested" if webbrowser.open(url) else "failed"
            except (OSError, webbrowser.Error):
                opened = "failed"
        print(json.dumps({"event": "listening", "job_id": job_id, "url": url, "pid": info["pid"],
                          "reused": server is None, "browser_request": opened}, ensure_ascii=False), flush=True)
        if server is not None:
            server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.server_close()
