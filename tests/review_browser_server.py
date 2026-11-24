"""为人工回听浏览器验收提供合成录音、长转写列表和真实本机服务。"""

import argparse
from array import array
import json
import math
from pathlib import Path
import sys
import wave
from unittest.mock import patch
from asr_runtime.utils.path_picker import choose_path

from asr_runtime.application.recovery import finish_session
from asr_runtime.application.session import Session
from asr_runtime.application.transcription import export_job
from asr_runtime.review_web import create_review_server
from asr_runtime.utils.environment import Runtime
from asr_runtime.utils.job_files import job_directory, read_config, result_path, save_record
from asr_runtime.utils.results import load_transcript
from tests.support import ROOT, SKILL_ROOT


def make_review_job(workspace: Path) -> tuple[Runtime, str]:
    """在专用测试工作目录生成千秒录音、千句JSON及原始三格式成品。"""
    workspace = workspace.resolve()
    if not workspace.is_relative_to((ROOT / ".runtime").resolve()):
        raise ValueError("浏览器验收工作目录必须位于仓库.runtime内。")
    workspace.mkdir(parents=True, exist_ok=True)
    fixtures = workspace / "fixtures"
    fixtures.mkdir()
    source = fixtures / "人工回听合成录音.wav"
    sample_rate = 8000
    samples = array("h", (int(5000 * math.sin(2 * math.pi * 440 * index / sample_rate))
                           for index in range(sample_rate)))
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        for _ in range(1000):
            audio.writeframes(samples.tobytes())

    runtime = Runtime(workspace, SKILL_ROOT)
    session = Session(runtime, audio=source)
    try:
        assert session.selected_audio is not None
        preview = session.validate({
            "auth_mode": "console", "audio_id": session.selected_audio["audio_id"],
            "diarization_enabled": True, "enhancement_mode": "none", "hotword_rows": [],
            "context": "", "json_directory": "default", "document_directory": "default",
            "review_enabled": True,
        })
        session.preview_ready(preview["validation_id"])
        receipt = session.confirm()
    finally:
        session.cleanup()
        finish_session(runtime, session.session_id)

    job_id = receipt["job_id"]
    config = read_config(runtime, job_id)
    destination = result_path(config)
    destination.parent.mkdir(parents=True)
    # 每句占独立的一秒，可核对长录音跳转、高亮与跟随。
    sentences = [{
        "text": f"第{index + 1}句合成转写：用于回听定位、文字修改和说话人校验。",
        "begin_time": index * 1000,
        "end_time": (index + 1) * 1000,
        "speaker_id": index % 3,
    } for index in range(1000)]
    sentences[0]["text"] = "\n".join(
        f"合成阅读样例第{number}段：" + "这里是专门编写的本机测试文字，用于检查自然换行、全文展示与就地修改，不包含真实录音内容。" * 3
        for number in range(1, 6)
    )
    destination.write_text(json.dumps({"transcripts": [{"channel_id": 0, "sentences": sentences}]},
                                     ensure_ascii=False), encoding="utf-8")
    execution = job_directory(runtime, job_id) / "execution"
    execution.mkdir()
    save_record(execution, {
        "job_id": job_id, "status": "JSON_READY", "cloud_outcome": "result_received",
        "json_path": str(destination), "result": load_transcript(destination).summary(),
    })
    delivered = export_job(runtime, job_id)
    if not delivered.get("documents_ready"):
        raise RuntimeError("合成原稿未完整生成，未启动浏览器验收服务。")
    return runtime, job_id


def main() -> None:
    """启动长列表回听服务并输出连接回执，结束后保留验收文件。"""
    parser = argparse.ArgumentParser(description="启动人工回听浏览器验收夹具，不调用云端。")
    parser.add_argument("--workspace", type=Path, required=True)
    options = parser.parse_args()
    runtime, job_id = make_review_job(options.workspace)
    server = create_review_server(runtime, job_id)
    print(json.dumps({"event": "listening", "url": f"http://127.0.0.1:{server.server_port}/review",
                      "job_id": job_id, "sentences": 1000}, ensure_ascii=False), flush=True)
    export_directory = options.workspace / "review_exports"
    export_directory.mkdir()

    def select_test_directory(initial, *, mode, audio_suffixes=(), cancel_event=None):
        """模拟系统目录窗口的选择或取消结果。"""
        if mode != "directory":
            return choose_path(initial, mode=mode, audio_suffixes=audio_suffixes, cancel_event=cancel_event)
        cancel_marker = options.workspace / "fixtures/cancel-next-directory"
        if cancel_marker.exists():
            cancel_marker.unlink()
            return None
        return export_directory

    try:
        with patch("asr_runtime.utils.path_picker.choose_path", side_effect=select_test_directory):
            server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
