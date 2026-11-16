"""本机HTTP入口：协议检查、静态资源和用例结果到响应的转换。"""

import http.client
import json
import os
import sys
import threading
import webbrowser
from collections.abc import Mapping
from pathlib import Path
from .utils.local_http import LocalHTTPServer, LocalHandler, RequestError, STATIC, STATIC_ROUTES
from typing import Literal
from urllib.parse import unquote, urlsplit

from .utils.environment import Runtime, SetupError
from .utils.hotwords import hotwords_template
from .utils.i18n import language_scope, localize
from .utils.session_files import read_connection, read_terminal, write_connection
from .application.recovery import CleanupReport, finish_session, recover_workspace
from .application.session import Session
from .application.rules import ValidationError

# JSON词表保留编辑值和类型标记，需容纳模型支持的2000条词语。
MAX_REQUEST_BYTES = 512 * 1024


class LocalServer(LocalHTTPServer):
    """提供带编辑会话的本机 HTTP 服务。"""

    session: Session
    recovery: CleanupReport

    def serve_forever(self, poll_interval: float = 0.1) -> None:
        """启动一次到期计时器，运行到会话结束或调用方停止服务。"""
        timer = threading.Timer(self.session.remaining_seconds(), self.expire_session)
        timer.daemon = True
        timer.start()
        try:
            super().serve_forever(poll_interval)
        finally:
            timer.cancel()

    def expire_session(self) -> None:
        """结束达到截止时间的编辑会话并停止接收请求。"""
        if self.session.expire() is not None:
            self.shutdown()

    def server_close(self) -> None:
        """关闭会话并等待请求结束，再回收会话的磁盘暂存。"""
        try:
            self.session.cleanup()
        finally:
            try:
                super().server_close()
            finally:
                report = finish_session(self.session.runtime, self.session.session_id)
                if report["warnings"]:
                    print(json.dumps({"event": "cleanup_warning", **report}, ensure_ascii=False), file=sys.stderr, flush=True)


def create_server(runtime: Runtime, port: int = 0, *, audio: Path | None = None) -> LocalServer:
    """建立绑定127.0.0.1的HTTP服务与独立编辑会话。"""
    recovery = recover_workspace(runtime)
    session = Session(runtime, audio=audio)

    class Handler(LocalHandler):
        server: LocalServer

        def do_GET(self) -> None:
            """分派静态资源、会话描述和热词模板的读取请求。"""
            with language_scope(self.headers.get("Accept-Language", "zh-CN")):
                path = urlsplit(self.path)
                static = STATIC_ROUTES
                if not self.allowed(authenticated=path.path not in static):
                    return
                try:
                    if path.path in static:
                        name, kind = static[path.path]
                        self.send(200, (STATIC / name).read_bytes(), kind, cookie=path.path == "/")
                    elif path.path == "/api/session":
                        self.json(200, session.description(), cookie=True)
                    elif path.path == "/api/events":
                        self.session_events()
                    elif path.path == "/api/hotwords-template":
                        self.send(200, hotwords_template(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    else:
                        self.json(404, {"ok": False, "error": localize("未找到此页面或接口。")})
                except (ValidationError, SetupError, OSError) as exc:
                    self.error_response(exc)

        def session_events(self) -> None:
            """保持单向连接，在会话结束时发送一次终态并关闭。"""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.flush()
            session.terminal_event.wait()
            payload = json.dumps(session.terminal_result(), ensure_ascii=False)
            try:
                self.wfile.write(f"event: ended\ndata: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            except OSError:
                pass  # 页面可能已由用户关闭，会话仍按服务端状态结束。

        def error_response(self, exc: Exception) -> None:
            """将字段错误或本机文件失败转换为网页可呈现的响应。"""
            if isinstance(exc, ValidationError):
                self.json(422, {"ok": False, "error": exc.message, "field": exc.field, "details": exc.details})
            else:
                self.json(422, {"ok": False, "error": localize("本地文件操作未完成，请检查路径与访问权限。")})

        def do_POST(self) -> None:
            """解析受保护请求，分派编辑操作与转写任务交接。"""
            with language_scope(self.headers.get("Accept-Language", "zh-CN")):
                path = urlsplit(self.path).path
                if not self.allowed(control=path in ("/api/confirm", "/api/cancel")):
                    return
                try:
                    if path == "/api/import-hotwords":
                        if self.headers.get("Transfer-Encoding") or self.headers.get_content_type() != "application/octet-stream":
                            raise ValidationError("请选择文件后传入本机。", "upload")
                        size = int(self.headers.get("Content-Length", "0"))
                        name = unquote(self.headers.get("X-File-Name", ""), errors="strict")
                        self.json(200, session.receive_hotwords(name, self.rfile, size))
                        return
                    payload = self.read_json(MAX_REQUEST_BYTES)
                    if path == "/api/validate":
                        self.json(200, session.validate(payload))
                    elif path == "/api/preview-ready":
                        self.json(200, session.preview_ready(payload.get("validation_id")))
                    elif path == "/api/edit":
                        self.json(200, session.edit(payload.get("validation_id")))
                    elif path == "/api/confirm":
                        self.json(200, session.confirm())
                    elif path == "/api/cancel":
                        self.json(200, session.cancel())
                    elif path == "/api/api-key":
                        self.json(200, session.api_key_display())
                    elif path == "/api/save-api-key":
                        self.json(200, session.save_api_key(payload.get("value")))
                    elif path == "/api/select-directory":
                        self.json(200, session.select_directory(payload.get("kind"), payload.get("picker_id")))
                    elif path == "/api/select-audio":
                        self.json(200, session.select_audio(payload.get("picker_id")))
                    elif path == "/api/cancel-picker":
                        self.json(200, session.cancel_picker(payload.get("picker_id")))
                    else:
                        self.json(404, {"ok": False, "error": localize("未找到此接口。")})
                except (ValidationError, SetupError, OSError) as exc:
                    self.error_response(exc)
                except RequestError as exc:
                    self.json(exc.status, {"ok": False, "field": "form", "error": localize(str(exc))})
                except (ValueError, TypeError):
                    self.json(400, {"ok": False, "error": localize("请求格式不正确。")})
                finally:
                    if session.terminal_event.is_set():
                        self.server.shutdown()

    server = LocalServer(("127.0.0.1", port), Handler, bind_and_activate=False)
    server.session = session
    server.token = session.token
    server.recovery = recovery
    try:
        server.server_bind()
        server.server_activate()
        write_connection(runtime, session.session_id, server.server_port, session.token, session.deadline)
    except (OSError, SetupError):
        server.server_close()
        raise
    return server


def serve(runtime: Runtime, *, port: int = 0, open_browser: bool = True, audio: Path | None = None) -> None:
    """持续提供配置网页与进程回执，退出时释放本次服务资源。"""
    server = create_server(runtime, port, audio=audio)
    url = f"http://127.0.0.1:{server.server_port}/"
    try:
        browser_request: Literal["skipped", "requested", "failed"] = "skipped"
        if open_browser:
            try:
                browser_request = "requested" if webbrowser.open(url) else "failed"
            except (OSError, webbrowser.Error):
                browser_request = "failed"
        print(json.dumps({"event": "listening", "session_id": server.session.session_id,
                          "expires_at": server.session.expires_at, "url": url, "pid": os.getpid(),
                          "browser_request": browser_request, "cleanup": server.recovery}, ensure_ascii=False), flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def control_session(runtime: Runtime, session_id: str, action: Literal["confirm", "cancel"]) -> Mapping[str, object]:
    """按明确编辑会话编号请求交接或取消，并恢复已经持久保存的回执。"""
    terminal = read_terminal(runtime, session_id)
    if terminal is None:
        connection = None
        try:
            connection_info = read_connection(runtime, session_id)
            origin = f"http://127.0.0.1:{connection_info['port']}"
            connection = http.client.HTTPConnection("127.0.0.1", connection_info["port"], timeout=15)
            connection.request("POST", f"/api/{action}", body=b"{}", headers={
                "Origin": origin, "Content-Type": "application/json", "X-ASR-Token": connection_info["token"],
            })
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            if response.status != 200 or not isinstance(payload, dict):
                localized = payload.get("error") if isinstance(payload, dict) else None
                message = localized.get("zh") if isinstance(localized, dict) else None
                raise SetupError(message or "会话操作未完成，请检查当前配置页面。")
            return payload
        except (SetupError, OSError, http.client.HTTPException, ValueError) as exc:
            # 已处理请求的HTTP响应可能丢失；只读取原结果，不重新发送操作。
            terminal = read_terminal(runtime, session_id)
            if terminal is None:
                if isinstance(exc, SetupError):
                    raise
                raise SetupError("无法取得会话操作结果。请检查网页服务与同一会话的记录。") from exc
        finally:
            if connection is not None:
                connection.close()
    if action == "cancel":
        return terminal
    if terminal["receipt"] is not None:
        return terminal["receipt"]
    raise SetupError("此编辑会话已取消，请重新打开配置页。")
