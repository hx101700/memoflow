"""通过PyAV探测音频信息并生成单声道副本。"""

from pathlib import Path
from collections.abc import Iterable

import av

from ..models import AudioInfo


class MediaError(ValueError):
    """表示音频读取、转换或结果检查中的错误。"""


def probe_audio(path: Path) -> AudioInfo:
    """读取首个音轨的声道、采样率、时长及文件信息。"""
    try:
        with av.open(str(path), options={"protocol_whitelist": "file"}) as container:
            if not container.streams.audio:
                raise MediaError("文件没有可识别的音轨。")
            stream = container.streams.audio[0]
            duration = None
            if stream.duration is not None and stream.time_base is not None:
                duration = float(stream.duration * stream.time_base)
            elif container.duration is not None:
                duration = container.duration / av.time_base
            channels = len(stream.codec_context.layout.channels)
            rate = stream.codec_context.sample_rate
            if channels < 1 or rate < 1:
                raise MediaError("无法确定音频声道数或采样率。")
            return AudioInfo(channels, rate, duration, path.stat().st_size,
                             container.format.name, len(container.streams.audio))
    except av.FFmpegError as exc:
        raise MediaError("无法读取录音，请检查文件是否损坏或格式是否支持。") from exc


def convert_to_mono(source: Path, destination: Path, source_info: AudioInfo) -> AudioInfo:
    """生成单声道FLAC，并核对副本的声道、采样率和时长。"""
    before = source.stat()
    created = False
    samples = 0
    try:
        with av.open(str(source), options={"protocol_whitelist": "file"}) as original:
            # xb保证不覆盖已有文件；逐帧处理，避免将长音频整体读入内存。
            with destination.open("xb") as file:
                created = True
                with av.open(file, mode="w", format="flac") as output:
                    stream = output.add_stream("flac", rate=source_info.sample_rate)
                    stream.layout = "mono"
                    stream.format = "s32"
                    resampler = av.AudioResampler(format="s32", layout="mono", rate=source_info.sample_rate)

                    def write_frames(frames: Iterable[av.AudioFrame]) -> None:
                        """编码重采样后的音频帧，写入当前FLAC容器。"""
                        for frame in frames:
                            for packet in stream.encode(frame):
                                output.mux(packet)

                    for frame in original.decode(audio=0):
                        samples += frame.samples
                        write_frames(resampler.resample(frame))
                    write_frames(resampler.resample(None))
                    for packet in stream.encode(None):
                        output.mux(packet)

        # 执行准备已核对内容摘要；这里仅检查转换期间常规改动，不再完整读取源文件。
        after = source.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                after.st_size, after.st_mtime_ns, after.st_ino):
            raise MediaError("声道处理期间源文件改变，未上传。")
        converted = probe_audio(destination)
        if (samples == 0 or converted.channels != 1 or converted.sample_rate != source_info.sample_rate
                or converted.duration_seconds is None
                or abs(converted.duration_seconds - samples / source_info.sample_rate) > 1 / source_info.sample_rate):
            raise MediaError("转换后的声道、采样率或有效样本时长检查失败。")
        return converted
    except (av.FFmpegError, OSError, ValueError) as exc:
        # 只删除本次以xb新建的失败副本，原文件及已存在目标不受影响。
        if created:
            destination.unlink(missing_ok=True)
        if isinstance(exc, av.FFmpegError):
            raise MediaError("声道转换失败，请检查录音是否损坏。") from exc
        raise
