"""验证回听页面连接断开、刷新和多标签页的服务收尾。"""

import http.client
import json
import threading
import time

from asr_runtime.review_web import create_review_server
from tests.test_review_web import ReviewFixture


class ReviewLifecycleTests(ReviewFixture):
    def setUp(self) -> None:
        """启动真实本机服务，将关页宽限缩短以验证生命周期。"""
        super().setUp()
        self.server = create_review_server(self.runtime, self.job_id)
        self.server.page_close_grace = 0.3
        self.worker = threading.Thread(target=self.run_server, daemon=True)
        self.worker.start()
        self.connections: list[tuple[http.client.HTTPConnection, http.client.HTTPResponse]] = []

    def run_server(self) -> None:
        """服务结束后执行与正式入口相同的连接记录清理。"""
        try:
            self.server.serve_forever(poll_interval=0.02)
        finally:
            self.server.server_close()

    def tearDown(self) -> None:
        """关闭本例连接并等待自身服务退出，再删除合成数据。"""
        try:
            for connection, response in self.connections:
                response.close()
                connection.close()
            if self.worker.is_alive():
                self.server.stopping.set()
                self.server.shutdown()
            self.worker.join(timeout=3)
        finally:
            super().tearDown()

    def connect_page(self) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
        """打开带有效令牌的页面持久连接并读取初始握手。"""
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        connection.request("GET", "/api/review/presence", headers={"X-ASR-Token": self.server.token})
        response = connection.getresponse()
        self.connections.append((connection, response))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.readline(), b": connected\n")
        self.assertEqual(response.readline(), b"\n")
        return connection, response

    @staticmethod
    def disconnect_page(page: tuple[http.client.HTTPConnection, http.client.HTTPResponse]) -> None:
        """模拟浏览器释放页面连接。"""
        page[1].close()
        page[0].close()

    def test_last_page_close_stops_service_and_preserves_draft(self) -> None:
        """最后页面关闭后服务自动退出，已保存草稿和原结果仍存在。"""
        self.server.session.save({"revision": 0, "sentences": [
            {"index": 1, "text": "已保存的修改", "speaker_id": 0}]})
        page = self.connect_page()
        self.disconnect_page(page)
        self.worker.join(timeout=3)
        self.assertFalse(self.worker.is_alive())
        self.assertFalse(self.server.connection_path.exists())
        draft = json.loads((self.job_root / "review/draft.json").read_bytes())
        self.assertEqual(draft["sentences"][0]["text"], "已保存的修改")
        self.assertEqual(self.json_path.read_bytes(), self.original_json)

    def test_refresh_connection_cancels_pending_shutdown(self) -> None:
        """刷新后及时恢复连接，服务和草稿继续可用。"""
        first = self.connect_page()
        self.disconnect_page(first)
        second = self.connect_page()
        time.sleep(self.server.page_close_grace + 0.1)
        self.assertTrue(self.worker.is_alive())
        self.assertFalse(self.server.stopping.is_set())
        self.assertEqual(self.server.session.description()["job_id"], self.job_id)
        self.disconnect_page(second)
        self.worker.join(timeout=3)
        self.assertFalse(self.worker.is_alive())

    def test_one_remaining_tab_keeps_service_running(self) -> None:
        """关闭一个标签不影响另一个仍打开的校对页面。"""
        first, second = self.connect_page(), self.connect_page()
        self.disconnect_page(first)
        time.sleep(self.server.page_close_grace + 0.1)
        self.assertTrue(self.worker.is_alive())
        self.disconnect_page(second)
        self.worker.join(timeout=3)
        self.assertFalse(self.worker.is_alive())

    def test_presence_requires_current_session_token(self) -> None:
        """未认证请求不能占用页面生命周期。"""
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            connection.request("GET", "/api/review/presence")
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
        finally:
            connection.close()
        self.assertEqual(self.server._pages, 0)

    def test_control_close_ends_attached_presence(self) -> None:
        """Codex主动收尾时连接线程也能释放，不等待用户关标签。"""
        self.connect_page()
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            connection.request("POST", "/api/review/close", body=b"{}", headers={
                "X-ASR-Token": self.server.token, "Content-Type": "application/json",
                "Origin": f"http://127.0.0.1:{self.server.server_port}"})
            response = connection.getresponse()
            self.assertEqual(json.loads(response.read()), {"closed": True})
        finally:
            connection.close()
        self.worker.join(timeout=3)
        self.assertFalse(self.worker.is_alive())
