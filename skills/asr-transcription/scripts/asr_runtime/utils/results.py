"""解析官方转写JSON，提供三种文档共用的内存结果。"""

import hashlib
import json
from pathlib import Path

from ..models import Sentence, Transcript
from .environment import SetupError


def load_transcript(path: Path) -> Transcript:
    """核对JSON结构，返回保留原始顺序和文本的转写结果。"""
    try:
        if path.resolve() != path:
            raise ValueError("redirected result")
        content = path.read_bytes()
        result = json.loads(content.decode("utf-8"))
        if not isinstance(result, dict) or not isinstance(result["transcripts"], list):
            raise ValueError("unexpected document")
        sentences: list[Sentence] = []
        for track_index, track in enumerate(result["transcripts"], 1):
            if not isinstance(track, dict) or not isinstance(track["sentences"], list):
                raise ValueError("unexpected track")
            channel = track.get("channel_id")
            if channel is not None and (type(channel) is not int or channel < 0):
                raise ValueError("unexpected channel")
            for sentence in track["sentences"]:
                begin, end = sentence["begin_time"], sentence["end_time"]
                if (type(begin) is not int or type(end) is not int or not 0 <= begin <= end
                        or not isinstance(sentence["text"], str)):
                    raise ValueError("unexpected sentence")
                speaker = sentence.get("speaker_id")
                if speaker is not None and (type(speaker) is not int or speaker < 0):
                    raise ValueError("unexpected speaker")
                sentences.append(Sentence(len(sentences) + 1, track_index, channel,
                                          begin, end, speaker, sentence["text"]))
        if not any(sentence.text.strip() for sentence in sentences):
            raise ValueError("no usable transcript")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SetupError("BL未生成可用的转写JSON，或结果结构不符合已核实契约。已保留现有文件；未推断失败原因，未重新转写。") from exc
    return Transcript(tuple(sentences), len(result["transcripts"]), len(content),
                      hashlib.sha256(content).hexdigest())
