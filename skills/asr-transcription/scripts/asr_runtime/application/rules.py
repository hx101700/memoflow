"""校验固定模型的音频属性、识别选项和增强内容。"""

import math
from collections.abc import Iterable, Mapping
from typing import cast

from ..models import MAX_HOTWORD_ROWS, AudioInfo, HotwordConfig, HotwordIssue, HotwordRow, RecognitionOptions
from ..utils.i18n import translate


# 官方模型/临时OSS限制见Skill的references/model.md A02、A04、A06。
AUDIO_SUFFIXES = frozenset(f".{name}" for name in (
    "aac", "amr", "avi", "flac", "flv", "m4a", "mkv", "mov", "mp3",
    "mp4", "mpeg", "ogg", "opus", "wav", "webm", "wma", "wmv",
))
SUPPORTED_CONTAINERS = frozenset({
    "aac", "amr", "avi", "flac", "flv", "mov", "mp3", "mpeg", "ogg",
    "wav", "matroska", "webm", "asf",
})
MAX_UPLOAD_BYTES = 1_000_000_000
MAX_DURATION_SECONDS = 12 * 60 * 60
MAX_HOTWORDS = 2000
MAX_CONTEXT_CHARS = 400
MIN_SPEAKERS = 2
MAX_SPEAKERS = 100


class ValidationError(ValueError):
    """携带表单字段和修改提示的输入校验错误。"""

    def __init__(self, message: str, field: str, details: list[HotwordIssue] | None = None) -> None:
        """携带可公开的说明、表单字段和可选行级错误。"""
        super().__init__(translate(message))
        self.field = field
        self.details: list[HotwordIssue] = [
            {**detail, "message": translate(detail["message"])} for detail in details or []
        ]


def check_audio_limits(info: AudioInfo, diarization: bool) -> None:
    """根据模型和临时存储规格校验音频属性。"""
    if not set(info.format_name.split(",")) & SUPPORTED_CONTAINERS:
        raise ValidationError("实际媒体格式不在固定模型支持范围内。", "audio_id")
    duration = info.duration_seconds
    if duration is None or not math.isfinite(duration) or duration <= 0:
        raise ValidationError("无法确定有效音频时长，不能完成上传前校验。", "audio_id")
    if duration > MAX_DURATION_SECONDS:
        raise ValidationError("音频时长超过模型允许的12小时。", "audio_id")
    if not (diarization and info.channels > 1) and info.size_bytes > MAX_UPLOAD_BYTES:
        raise ValidationError("待上传音频超过临时OSS的1 GB上限。", "audio_id")


def validate_context(text: object) -> str:
    """校验参考文本的长度与字符要求，保留用户原文。"""
    if not isinstance(text, str):
        raise ValidationError("参考文本必须为文字，请重新输入。", "context")
    if not text.strip():
        raise ValidationError("参考文本为空，请输入与录音相关的术语或参考文字，或关闭上下文增强。", "context")
    if len(text) > MAX_CONTEXT_CHARS:
        raise ValidationError(translate(
            "参考文本共 {count} 个字符，最多支持 {maximum} 个，超出 {excess} 个。请精简后重新检查。"
        ).format(count=len(text), maximum=MAX_CONTEXT_CHARS, excess=len(text) - MAX_CONTEXT_CHARS), "context")
    for position, char in enumerate(text, start=1):
        if char == "\x00" or 0xD800 <= ord(char) <= 0xDFFF:
            raise ValidationError(translate(
                "参考文本第 {position} 个字符无法传输（{codepoint}），请删除或重新输入。"
            ).format(position=position, codepoint=f"U+{ord(char):04X}"), "context")
    return text


def validate_hotword_rows(payload: object) -> HotwordConfig:
    """检查网页热词表格的数据形状，并应用统一词表规则。"""
    if not isinstance(payload, list):
        raise ValidationError("热词表格格式无效，请重新填写或导入。", "hotword_rows")
    if len(payload) > MAX_HOTWORD_ROWS:
        raise ValidationError("热词表格最多支持10000行，请减少后重新检查。", "hotword_rows")
    for index, value in enumerate(payload, start=1):
        if (not isinstance(value, dict) or not {"text", "weight"} <= value.keys()
                or value.keys() - {"text", "weight", "invalid_fields"}):
            raise ValidationError("热词表格格式无效，请重新填写或导入。", "hotword_rows")
        for field in ("text", "weight"):
            if value[field] is not None and not isinstance(value[field], (str, int, float, bool)):
                raise ValidationError("热词表格格式无效，请重新填写或导入。", "hotword_rows",
                                      [{"row": index, "field": field, "message": "单元格必须为文本或数值。"}])
        invalid_fields = value.get("invalid_fields", [])
        if not isinstance(invalid_fields, list) or any(field not in ("text", "weight") for field in invalid_fields):
            raise ValidationError("热词表格格式无效，请重新填写或导入。", "hotword_rows")
    return build_vocabulary(cast(list[HotwordRow], payload))


def build_vocabulary(rows: Iterable[HotwordRow]) -> HotwordConfig:
    """校验热词行并构建即时词典，汇总行级错误和导入提示。"""
    vocabulary: dict[str, int] = {}
    word_rows: dict[str, list[int]] = {}
    details: list[HotwordIssue] = []
    warnings = []
    ignored_blank_rows = 0
    super_count = 0
    for row_number, row in enumerate(rows, start=1):
        text, weight = row["text"], row["weight"]
        invalid_fields = row.get("invalid_fields", [])
        if text in (None, "") and weight in (None, "") and not invalid_fields:
            ignored_blank_rows += 1
            continue
        # 重复问题属于整组词条，首行和权重不合法的行也需要显示。
        if isinstance(text, str) and text.strip():
            word_rows.setdefault(text, []).append(row_number)
        row_errors = []
        if "text" in invalid_fields:
            message = ("不接受公式，请填写固定文本和数值。" if isinstance(text, str) and text.startswith("=")
                       else "Excel单元格类型不受支持，请在此重新填写文本或权重整数。")
            row_errors.append(("text", message))
        elif not isinstance(text, str) or not text.strip():
            row_errors.append(("text", "热词必须为非空文本。"))
        elif text != text.strip() or any(ord(char) < 32 or ord(char) == 127
                                        or 0xD800 <= ord(char) <= 0xDFFF for char in text):
            row_errors.append(("text", "请移除热词首尾空白、换行或控制字符；程序不会自动修改。"))
        elif not text.isascii() and len(text) > 15:
            row_errors.append(("text", "含非ASCII字符时，热词总长度最多15个字符。"))
        elif text.isascii() and len([part for part in text.split(" ") if part]) > 7:
            row_errors.append(("text", "纯ASCII热词按空格切分后最多7段。"))
        allowed_weights = (1, 2, 3, 4, 5, 50)
        # 网页输入框传递字符串；只转换明确写出的允许整数，保留其他原值供用户修正。
        if isinstance(weight, str) and weight in ("1", "2", "3", "4", "5", "50"):
            weight = int(weight)
        if "weight" in invalid_fields:
            message = ("不接受公式，请填写固定文本和数值。" if isinstance(weight, str) and weight.startswith("=")
                       else "Excel单元格类型不受支持，请在此重新填写文本或权重整数。")
            row_errors.append(("weight", message))
        elif (isinstance(weight, bool) or not isinstance(weight, (int, float))
                or weight not in allowed_weights):
            row_errors.append(("weight", "权重必须为1至5的整数或50。"))
        if row_errors:
            details.extend({"row": row_number, "field": name, "message": message}
                           for name, message in row_errors)
            continue
        # 行级错误已排除非文本热词与非法权重，转换只保留已接受的值。
        text = cast(str, text)
        weight = int(cast(int | float, weight))
        if text in vocabulary:
            continue
        vocabulary[text] = weight
        if len(vocabulary) > MAX_HOTWORDS:
            details.append({"row": row_number, "field": "text", "message": "热词总数超过2000个，请减少。"})
        if weight == 50:
            super_count += 1
            if super_count > 50:
                details.append({"row": row_number, "field": "weight", "message": "超级热词（权重50）最多50个。"})
    for repeated in word_rows.values():
        if len(repeated) > 1:
            for number in repeated:
                other = repeated[1] if number == repeated[0] else repeated[0]
                details.append({"row": number, "field": "text", "message": translate(
                    "与第{other_row}行热词重复，请删除重复行，仅保留一行。"
                ).format(other_row=other)})
    if details:
        details.sort(key=lambda issue: issue["row"])
        raise ValidationError("请修改热词表格中标红的单元格后重新检查。", "hotword_rows", details)
    if not vocabulary:
        raise ValidationError("请至少填写一个热词及其权重，或关闭热词增强。", "hotword_rows",
                              [{"row": 1, "field": "text", "message": "热词必须为非空文本。"}])
    if ignored_blank_rows:
        warnings.append(translate("已忽略{count}个完全空白行。").format(count=ignored_blank_rows))
    return {"vocabulary": vocabulary, "count": len(vocabulary), "warnings": warnings}


# 语言代码来自 Filetrans HTTP API；CLI 的 --language 当前只接受单个值。
LANGUAGE_CODES = (
    "zh", "en", "ja", "ko", "vi", "th", "id", "ms", "tl", "hi", "ar", "fr",
    "de", "es", "pt", "ru", "it", "nl", "sv", "da", "fi", "no", "el", "pl",
    "cs", "hu", "ro", "bg", "hr", "sk",
)


def validate_options(payload: Mapping[str, object], diarization: object) -> RecognitionOptions:
    """核对语言和参考人数，形成执行所用的识别选项。"""
    language = payload.get("language_hint")
    if language is not None and (
        not isinstance(language, str) or language not in LANGUAGE_CODES
    ):
        raise ValidationError("请选择一种语言，或使用自动识别。", "language_hint")

    speaker_count = payload.get("speaker_count")
    if speaker_count is not None:
        if not diarization:
            raise ValidationError("设置发言人数前，请开启区分发言人。", "speaker_count")
        # bool 是 int 的子类，但不能把勾选状态当作人数。
        if type(speaker_count) is not int or not MIN_SPEAKERS <= speaker_count <= MAX_SPEAKERS:
            raise ValidationError(translate(
                "发言人数需为 {minimum}–{maximum} 的整数，或使用自动识别。"
            ).format(minimum=MIN_SPEAKERS, maximum=MAX_SPEAKERS), "speaker_count")

    return {
        "language_hints": [] if language is None else [language],
        "speaker_count": speaker_count,
    }
