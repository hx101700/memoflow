"""预览用例：协调本机文件、媒体和热词读取，再应用输入规则。"""

from dataclasses import asdict
from pathlib import Path
from typing import cast

from ..models import AudioMetadata, AudioRecord, HotwordImport

from ..utils.files import FileError, file_fingerprint, resolve_input
from ..utils.hotwords import HotwordFileError, read_hotwords
from ..utils.i18n import localize
from ..utils.media import MediaError, probe_audio
from .rules import AUDIO_SUFFIXES, ValidationError, check_audio_limits


def validate_audio(path: str | Path, diarization: object) -> AudioRecord:
    """校验所选录音，返回媒体属性、内容摘要和处理提示。"""
    field = "audio_id"
    try:
        source = resolve_input(path, AUDIO_SUFFIXES)
        if not isinstance(diarization, bool):
            raise ValidationError("说话人区分必须为开启或关闭。", "diarization")
        before = source.stat()
        if before.st_size == 0:
            raise ValidationError("录音文件为空。", field)
        info = probe_audio(source)
        check_audio_limits(info, diarization)
        # check_audio_limits已确认时长为有效正数。
        duration = cast(float, info.duration_seconds)
        requires_mono = diarization and info.channels > 1
        warnings = []
        if requires_mono:
            warnings.append(localize(
                "此录音包含 {channels} 个声道。启用说话人区分后，转写前将生成单声道 FLAC 副本，"
                "保留原文件。副本通过大小和时长检查后才会上传。", channels=info.channels))
        if diarization and duration > 2 * 60 * 60:
            warnings.append(localize("录音超过 2 小时。启用说话人区分可能导致转写失败或超时，建议使用 2 小时以内的录音。"))
        if info.audio_tracks > 1:
            warnings.append(localize(
                "此文件包含 {tracks} 个音轨，仅转写第一个音轨（索引0），其余音轨不会转写。", tracks=info.audio_tracks))
        fingerprint = file_fingerprint(source)
        after = source.stat()
        if (fingerprint["size_bytes"] != info.size_bytes
                or (before.st_size, before.st_mtime_ns, before.st_ino)
                != (after.st_size, after.st_mtime_ns, after.st_ino)):
            raise ValidationError("文件在校验期间发生变化，请重新校验。", field)
        return {"path": str(source), "metadata": cast(AudioMetadata, asdict(info)), "fingerprint": fingerprint,
                "requires_mono": requires_mono, "warnings": warnings}
    except FileError as exc:
        raise ValidationError(exc.template, field) from exc
    except (MediaError, OSError) as exc:
        raise ValidationError("无法读取录音，请检查文件是否损坏及格式是否支持。", field) from exc


def import_hotwords(content: bytes) -> HotwordImport:
    """从Excel字节读取可编辑原始行及工作簿提示。"""
    try:
        rows, warnings = read_hotwords(content)
    except HotwordFileError as exc:
        raise ValidationError(exc.template, "hotword_rows") from exc
    return {"rows": rows, "warnings": warnings}
