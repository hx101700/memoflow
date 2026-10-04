"""为浏览器回归提供隔离的本机服务及合成输入。"""

import argparse
import json
import wave
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from asr_runtime.utils.environment import Runtime
from asr_runtime.web import create_server
from tests.support import SKILL_ROOT


def main() -> None:
    """创建合成音频与词表，输出本机连接信息并启动服务。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    options = parser.parse_args()
    fixtures = options.workspace / "fixtures"
    fixtures.mkdir()
    with wave.open(str(fixtures / "sample.wav"), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\0" * 64000)
    sheets = {
        "invalid.xlsx": [("wrong", "weight"), ("Kubernetes", 4)],
        "invalid-rows.xlsx": [("text", "weight"), ("Kubernetes", 4), ("MemoFlow", 9), ("Kubernetes", 5)],
        "paged.xlsx": [("text", "weight"), *[(f"Term{number}", 4) for number in range(60)], ("LastTerm", 8)],
    }
    for name, rows in sheets.items():
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = "热词"
        for row in rows:
            sheet.append(row)
        workbook.save(fixtures / name)
        workbook.close()
    server = create_server(Runtime(options.workspace, SKILL_ROOT))
    url = f"http://127.0.0.1:{server.server_port}/"
    print(json.dumps({"url": url, "session_id": server.session.session_id}), flush=True)
    try:
        with patch("asr_runtime.utils.path_picker.choose_path", return_value=(fixtures / "sample.wav").resolve()):
            server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
