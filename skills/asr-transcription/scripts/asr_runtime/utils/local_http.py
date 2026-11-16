"""提供本机网页共用的HTTP响应、来源验证与静态资源。"""

import hmac
import json
import os
import socket
from collections.abc import Mapping
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast

from .i18n import localize

STATIC = Path(__file__).resolve().parents[1] / "static"
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}


class RequestError(ValueError):
    """表示请求格式或大小错误，携带对应HTTP状态。"""

    def __init__(self, status: int, message: str) -> None:
        """保存可展示的协议错误及响应状态。"""
        super().__init__(message)
        self.status = status


class LocalHTTPServer(ThreadingHTTPServer):
    """独占绑定本机端口，等待自身请求线程正常收尾。"""

    allow_reuse_address = False
    daemon_threads = False
    token: str

    def server_bind(self) -> None:
        """在Windows独占绑定端口，防止服务互相覆盖。"""
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class LocalHandler(BaseHTTPRequestHandler):
    """在本机页面与代码入口之间校验来源、传递JSON和静态内容。"""

    server: LocalHTTPServer

    def read_json(self, max_bytes: int = 512 * 1024) -> dict[str, object]:
        """读取有界JSON对象，供两个本机页面共用协议检查。"""
        if self.headers.get("Transfer-Encoding") or self.headers.get_content_type() != "application/json":
            raise RequestError(400, "请求必须为JSON。")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > max_bytes:
                raise RequestError(413, "表格或文本内容过大，请减少后重新检查。")
            if length <= 0:
                raise RequestError(400, "请求体不能为空。")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("invalid object")
            return cast(dict[str, object], payload)
        except RequestError:
            raise
        except (ValueError, UnicodeError) as error:
            raise RequestError(400, "请求格式不正确。") from error

    def log_message(self, *_args: object) -> None:
        """关闭默认HTTP访问日志。"""
        # 请求URL和请求头可能携带会话令牌。
        pass

    def setup(self) -> None:
        """初始化连接并设置网络读写超时。"""
        super().setup()
        self.connection.settimeout(10)

    def send(self, status: int, data: bytes, content_type: str = "application/json; charset=utf-8", cookie: bool = False) -> None:
        """发送响应内容及缓存控制头，按需设置会话Cookie。"""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if cookie:
            self.send_header("Set-Cookie", f"asr_ui_{self.server.server_port}={self.server.token}; Path=/; HttpOnly; SameSite=Strict")
        self.end_headers()
        self.wfile.write(data)

    def json(self, status: int, payload: Mapping[str, object], cookie: bool = False) -> None:
        """将用例回执编码为UTF-8 JSON响应。"""
        self.send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), cookie=cookie)

    def allowed(self, authenticated: bool = True, *, control: bool = False) -> bool:
        """核对本机请求来源及必要的会话令牌，拒绝时直接回复403。"""
        expected_host = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        if self.headers.get("Host") != expected_host or (origin is not None and origin != f"http://{expected_host}"):
            self.json(403, {"ok": False, "error": localize("请求来源不被允许。")})
            return False
        if self.command == "POST" and origin != f"http://{expected_host}":
            self.json(403, {"ok": False, "error": localize("缺少有效的本地页面来源。")})
            return False
        if authenticated:
            token = self.headers.get("X-ASR-Token", "")
            if not token and not control:
                try:
                    cookies = SimpleCookie(self.headers.get("Cookie", ""))
                    value = cookies.get(f"asr_ui_{self.server.server_port}")
                    token = value.value if value else ""
                except CookieError:
                    token = ""
            if not hmac.compare_digest(token.encode("utf-8"), self.server.token.encode("ascii")):
                self.json(403, {"ok": False, "error": localize("会话无效，请从Codex重新打开本地页面链接。")})
                return False
        return True
