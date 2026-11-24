"""定义用例与工具共享的音频、热词和转写数据结构。"""

from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict


AuthMode = Literal["console", "api_key"]
EnhancementMode = Literal["none", "hotwords", "context", "both"]
MAX_HOTWORD_ROWS = 10_000


class LocalizedText(TypedDict):
    """保存同一网页提示的中英文文本。"""

    zh: str
    en: str


class FileStat(TypedDict):
    """描述确认时比较的文件大小与修改时间。"""

    size_bytes: int
    mtime_ns: int


class FileFingerprint(FileStat):
    """描述已完整读取文件的内容身份。"""

    sha256: str


class AudioMetadata(TypedDict):
    """描述音频探测结果在确认配置中的JSON字段。"""

    channels: int
    sample_rate: int
    duration_seconds: float | None
    size_bytes: int
    format_name: str
    audio_tracks: int


class AudioRecord(TypedDict):
    """保存已预览录音的本机身份与媒体信息。"""

    path: str
    metadata: AudioMetadata
    fingerprint: FileFingerprint
    requires_mono: bool
    warnings: list[LocalizedText]
    name: str


class AudioSelection(TypedDict):
    """关联已登记的录音原文件与当前编辑会话的选择编号。"""

    audio_id: str
    path: str
    name: str
    size_bytes: int


class HotwordIssue(TypedDict):
    """定位热词表中需要用户修正的单元格。"""

    row: int
    field: str
    message: LocalizedText
    duplicate_group: NotRequired[int]


HotwordValue = str | int | float | bool | None
HotwordField = Literal["text", "weight"]


class HotwordRow(TypedDict):
    """保留可编辑的单元格值及待改写的Excel单元格类型。"""

    text: HotwordValue
    weight: HotwordValue
    invalid_fields: NotRequired[list[HotwordField]]


class HotwordImport(TypedDict):
    """返回Excel导入后的可编辑原始行及读取提示。"""

    rows: list[HotwordRow]
    warnings: list[LocalizedText]


class HotwordConfig(TypedDict):
    """保存随转写请求发送的即时热词及校验提示。"""

    vocabulary: dict[str, int]
    count: int
    warnings: list[LocalizedText]


class RecognitionOptions(TypedDict):
    """保存已经校验的 BL 转写选项。"""

    language_hints: list[str]
    speaker_count: int | None


class EnhancementConfig(TypedDict):
    """保存可独立启用的热词增强与上下文增强配置。"""

    mode: EnhancementMode
    hotwords: HotwordConfig | None
    context: str | None


class TranscriptionSettings(TypedDict):
    """描述预览与执行共用的已校验转写输入。"""

    model: str
    region: str
    auth_mode: AuthMode
    audio: AudioRecord
    diarization_enabled: bool
    recognition_options: RecognitionOptions
    enhancement: EnhancementConfig
    review_enabled: NotRequired[bool]


class JobConfig(TranscriptionSettings):
    """保存转写任务交接时冻结的输入、执行授权和输出位置。"""

    schema_version: int
    job_id: str
    json_directory: str
    document_directory: str
    status: Literal["CONFIGURED"]
    execution_authorized: Literal[True]
    confirmed_at: str


class ConfirmationReceipt(TypedDict):
    """描述编辑会话交接给 Codex 后生成的唯一转写任务回执。"""

    ok: bool
    session_id: str
    job_id: str
    config_path: str
    auth_mode: AuthMode
    json_directory: str
    document_directory: str
    execution_started: bool


SessionEndState = Literal["handed_off", "expired", "cancelled"]
SessionPhase = Literal["editing", "preview", "handed_off", "expired", "cancelled"]


class SessionTerminal(TypedDict):
    """向网页和控制入口公布编辑会话的最终结果。"""

    state: SessionEndState
    receipt: ConfirmationReceipt | None


class ReviewSentence(TypedDict):
    """保存一句可编辑正文及说话人归属，时间和顺序来自原JSON。"""

    index: int
    text: str
    speaker_id: int | None


class ReviewSpeaker(TypedDict):
    """保存说话人编号及人工姓名，空姓名沿用默认编号标签。"""

    id: int
    name: str


class ReviewDraft(TypedDict):
    """保存与原JSON绑定的校对改动及重新选择的录音路径。"""

    revision: int
    source_sha256: str
    sentences: list[ReviewSentence]
    speakers: list[ReviewSpeaker]
    audio_path: str | None


class ResultSummary(TypedDict):
    """描述已解析JSON的规模与内容摘要。"""

    audio_tracks: int
    sentences: int
    json_bytes: int
    sha256: str


class ErrorReport(TypedDict):
    """描述可公开的本机或BL错误及其来源。"""

    source: str
    explanation: str
    code: NotRequired[str | None]
    phase: NotRequired[str]
    error_type: NotRequired[str]
    attempted_status: NotRequired[str]
    cli_exit_code: NotRequired[int]
    http_status: NotRequired[int | None]
    request_id: NotRequired[str | None]
    message: NotRequired[str]
    source_url: NotRequired[str | None]


class DocumentReport(TypedDict):
    """记录单种格式的文件位置或生成失败原因。"""

    status: Literal["READY", "FAILED"]
    path: NotRequired[str]
    bytes: NotRequired[int]
    message: NotRequired[str]
    error_type: NotRequired[str]


class DeliveryReport(TypedDict):
    """描述本次三格式导出的结果，不作为成品持久状态。"""

    status: Literal["COMPLETE", "PARTIAL", "FAILED"]
    message: str
    job_id: NotRequired[str]
    files: dict[str, DocumentReport]
    error_type: NotRequired[str]


class ExecutionReport(TypedDict):
    """记录一次BL执行的状态、JSON结果与附带交付结果。"""

    job_id: str
    status: Literal["CONFIGURED", "PREPARING", "RUNNING", "STOPPED", "JSON_READY", "OUTCOME_UNKNOWN"]
    message: NotRequired[str]
    execution_authorized: NotRequired[bool]
    authorization_source: NotRequired[str]
    cloud_outcome: NotRequired[str]
    started_at: NotRequired[str]
    updated_at: NotRequired[str]
    executor_pid: NotRequired[int]
    json_path: NotRequired[str]
    result: NotRequired[ResultSummary]
    error: NotRequired[ErrorReport]
    record_error: NotRequired[ErrorReport]
    delivery: NotRequired[DeliveryReport]
    documents_ready: NotRequired[bool]
    review_enabled: NotRequired[bool]
    review: NotRequired[dict[str, object]]


@dataclass(frozen=True)
class AudioInfo:
    channels: int
    sample_rate: int
    duration_seconds: float | None
    size_bytes: int
    format_name: str
    audio_tracks: int


@dataclass(frozen=True)
class Sentence:
    index: int
    track_index: int
    channel_id: int | None
    begin_ms: int
    end_ms: int
    speaker_id: int | None
    text: str
    speaker_name: str | None = None


@dataclass(frozen=True)
class Transcript:
    sentences: tuple[Sentence, ...]
    audio_tracks: int
    json_bytes: int
    sha256: str

    def summary(self) -> ResultSummary:
        """提取结果规模和内容摘要，供执行记录核对来源。"""
        return {"audio_tracks": self.audio_tracks, "sentences": len(self.sentences),
                "json_bytes": self.json_bytes, "sha256": self.sha256}
