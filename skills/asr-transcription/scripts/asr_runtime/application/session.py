"""管理本机编辑会话的录音选择、热词导入、配置预览和交接。"""

import secrets
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from io import BufferedIOBase, BytesIO
from pathlib import Path
from typing import BinaryIO, TypedDict, cast

from .. import MODEL
from ..models import (
    AudioSelection, AuthMode, ConfirmationReceipt, EnhancementMode, JobConfig, LocalizedText, SessionEndState,
    SessionPhase, SessionTerminal, TranscriptionSettings,
)
from ..utils.auth import read_api_key, write_api_key
from ..utils.bailian import check_recognition_command, recognition_arguments
from ..utils.path_picker import PathPicker
from ..utils.environment import Runtime, SetupError
from ..utils.files import FileError, check_file_unchanged, resolve_input
from ..utils.hotwords import MAX_XLSX_BYTES
from ..utils.i18n import localize
from ..utils.job_files import job_directory, publish_config, result_path
from ..utils.session_files import session_directory, write_receipt
from .inputs import import_hotwords, validate_audio
from .rules import (
    AUDIO_SUFFIXES, ValidationError, validate_context, validate_hotword_rows, LANGUAGE_CODES, validate_options,
    MAX_CONTEXT_CHARS, MIN_SPEAKERS, MAX_SPEAKERS, MAX_UPLOAD_BYTES,
    MAX_DURATION_SECONDS, MAX_HOTWORDS,
)

SESSION_LIFETIME_SECONDS = 2 * 60 * 60


def output_directory(runtime: Runtime, value: object, field: str, approved: Path | None = None) -> Path:
    """解析并校验本次会话的保存目录。"""
    try:
        if value == "default":
            base = runtime.output_root
            if base.resolve() != base:
                raise ValidationError("默认保存目录不能重定向到其他目录。", field)
            if base.exists() and not base.is_dir():
                raise ValidationError("默认保存位置存在同名文件，请选择其他文件夹。", field)
        else:
            if approved is None or value != str(approved):
                raise ValidationError("请点击“选择文件夹”设置保存位置。", field)
            if approved.resolve() != approved or not approved.is_dir():
                raise ValidationError("所选文件夹已不存在，请重新选择。", field)
            base = approved
        runtime.check_output_path(base)
        return base
    except SetupError as exc:
        raise ValidationError(exc.template, field, **exc.params) from exc
    except OSError as exc:
        raise ValidationError("此文件夹无法保存文件，请选择其他位置。", field) from exc


class Draft(TypedDict):
    """关联一次成功预览及其待确认的配置快照。"""

    id: str
    config: TranscriptionSettings
    form: dict[str, object]
    summary: dict[str, object]
    json_base: Path
    document_base: Path


class Session:
    def __init__(self, runtime: Runtime, *, audio: Path | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        """创建两小时编辑会话及其输入、预览和结束状态。"""
        self.runtime = runtime
        self.session_id = uuid.uuid4().hex
        self.token = secrets.token_urlsafe(32)
        self._clock = clock
        self.deadline = clock() + SESSION_LIFETIME_SECONDS
        self.expires_at = datetime.fromtimestamp(self.deadline, timezone.utc).isoformat()
        self._state_lock = threading.Lock()
        self._phase: SessionPhase = "editing"
        self.terminal_event = threading.Event()
        self._terminal: SessionTerminal | None = None
        self.draft: Draft | None = None
        self.receipt: ConfirmationReceipt | None = None
        self.selected_audio: AudioSelection | None = None
        self.audio_error: LocalizedText | None = None
        self.output_directories: dict[str, Path] = {}
        self._picker = PathPicker()
        self._closed = threading.Event()
        self._receiving_hotwords = False
        if audio is not None:
            try:
                self._register_audio(audio)
            except (FileError, OSError) as exc:
                message = exc.template if isinstance(exc, FileError) else "无法读取指定文件，请检查路径和访问权限。"
                self.audio_error = localize(message)

    def _require_open(self) -> None:
        """检查截止时间和会话终态，拒绝继续操作已结束的会话。"""
        self._expire_if_due()
        if self._closed.is_set():
            raise ValidationError("当前编辑会话已关闭。", "session")
        if self._phase == "expired":
            raise ValidationError("编辑会话已失效，请回到 Codex 重新打开配置页。", "session")
        if self._terminal:
            raise ValidationError("当前编辑会话已结束，请回到 Codex 查看转写任务。", "session")

    def _require_editable(self) -> None:
        """检查当前会话的配置编辑权限。"""
        self._require_open()
        if self._phase == "preview":
            raise ValidationError("请先点击“返回修改”再编辑转写设置。", "session")

    def _finish(self, state: SessionEndState) -> SessionTerminal:
        """在状态锁内登记唯一的会话结束结果并通知等待者。"""
        self._phase = state
        self._terminal = {"state": state, "receipt": self.receipt}
        self.terminal_event.set()
        return self._terminal

    def _expire_if_due(self) -> None:
        """在状态锁内结束达到截止时间的编辑会话。"""
        if self._terminal is None and self._clock() >= self.deadline:
            self._finish("expired")

    def remaining_seconds(self) -> float:
        """返回服务端单次到期计时器使用的剩余时间。"""
        return max(0.0, self.deadline - self._clock())

    def terminal_result(self) -> SessionTerminal | None:
        """取得单向事件通道需要发送的最终会话结果。"""
        with self._state_lock:
            return deepcopy(self._terminal)

    def expire(self) -> SessionTerminal | None:
        """按实际截止时间结束编辑会话并返回终态。"""
        with self._state_lock:
            self._expire_if_due()
            return deepcopy(self._terminal)

    def cancel(self) -> SessionTerminal:
        """取消尚未交接的编辑会话并通知页面结束。"""
        with self._state_lock:
            self._expire_if_due()
            if self._terminal:
                return deepcopy(self._terminal)
            return deepcopy(self._finish("cancelled"))

    def _require_import_complete(self) -> None:
        """在热词仍接收时阻止预览与交接。"""
        if self._receiving_hotwords:
            raise ValidationError("文件仍在添加，请稍候。", "hotword_rows")

    def _register_audio(self, value: Path) -> AudioSelection:
        """登记录音原路径与大小，更新当前选择并清除旧预览。"""
        path = resolve_input(value, AUDIO_SUFFIXES)
        size = path.stat().st_size
        with self._state_lock:
            self._require_editable()
            self.selected_audio = {"audio_id": uuid.uuid4().hex, "path": str(path), "name": path.name,
                                   "size_bytes": size}
            self.audio_error = None
            self.draft = None
            return self.selected_audio

    def select_audio(self, picker_id: object) -> dict[str, object]:
        """打开原生录音选择窗口并登记用户选中的原始文件。"""
        with self._state_lock:
            self._require_editable()
            initial = Path(self.selected_audio["path"]).parent if self.selected_audio else self.runtime.workspace
        if not initial.is_dir():
            initial = self.runtime.workspace
        try:
            selected = self._picker.select(initial, picker_id, mode="audio", audio_suffixes=tuple(sorted(AUDIO_SUFFIXES)))
            if selected is None:
                return {"ok": True, "cancelled": True}
            audio = self._register_audio(selected)
        except (FileError, SetupError, OSError) as exc:
            message = exc.template if isinstance(exc, (FileError, SetupError)) else "无法读取指定文件，请检查路径和访问权限。"
            params = exc.params if isinstance(exc, SetupError) else {}
            raise ValidationError(message, "audio_id", **params) from exc
        return {"ok": True, "cancelled": False, **audio}

    def select_directory(self, kind: object, picker_id: object) -> dict[str, object]:
        """打开原生目录窗口，校验并登记所选保存位置。"""
        if kind not in ("json", "document"):
            raise ValidationError("未知的保存位置。", "directory")
        kind = cast(str, kind)
        with self._state_lock:
            self._require_editable()
            initial = self.output_directories.get(kind, self.runtime.output_root)
        if not initial.is_dir():
            initial = self.runtime.workspace
        try:
            selected = self._picker.select(initial, picker_id, mode="directory")
        except SetupError as exc:
            raise ValidationError(exc.template, f"{kind}_directory", **exc.params) from exc
        if selected is None:
            return {"ok": True, "cancelled": True}
        path = selected  # 选择器已核对现有目录；这里只检查一次实际可写性。
        try:
            self.runtime.check_output_path(path)
            # 选择时检查一次可写性；预览和确认不反复创建探针文件。
            with tempfile.TemporaryFile(dir=path):
                pass
        except SetupError as exc:
            raise ValidationError(exc.template, f"{kind}_directory", **exc.params) from exc
        except OSError as exc:
            raise ValidationError("此文件夹无法保存文件，请选择其他位置。", f"{kind}_directory") from exc
        with self._state_lock:
            self._require_editable()
            self.output_directories[kind] = path
            self.draft = None
        return {"ok": True, "cancelled": False, "path": str(path)}

    def cancel_picker(self, picker_id: object) -> dict[str, bool]:
        """取消指定原生文件或目录窗口的等待。"""
        # 取消仅经过选择器自己的短锁，不等待文件接收、指纹或Excel校验。
        try:
            self._picker.cancel(picker_id)
        except SetupError as exc:
            raise ValidationError(exc.template, "directory", **exc.params) from exc
        return {"ok": True}

    def api_key_display(self) -> dict[str, str | bool]:
        """读取工作目录中的API Key，返回本机页面所需的显示数据。"""
        with self._state_lock:
            self._require_open()
            try:
                return {"ok": True, "value": read_api_key(self.runtime, required=False)}
            except (SetupError, OSError, UnicodeError) as exc:
                message = exc.template if isinstance(exc, SetupError) else "无法读取 .env 文件。"
                params = exc.params if isinstance(exc, SetupError) else {}
                raise ValidationError(message, "auth_mode", **params) from exc

    def save_api_key(self, value: object) -> dict[str, bool]:
        """保存当前页面填写的 API Key，返回完成状态。"""
        with self._state_lock:
            self._require_editable()
            try:
                write_api_key(self.runtime, value, staging_directory=session_directory(self.runtime, self.session_id))
            except (SetupError, OSError, UnicodeError) as exc:
                message = exc.template if isinstance(exc, SetupError) else "无法保存 API Key，请检查工作目录的访问权限。"
                params = exc.params if isinstance(exc, SetupError) else {}
                raise ValidationError(message, "auth_mode", **params) from exc
        return {"ok": True}

    def description(self) -> dict[str, object]:
        """返回页面选项、当前预览和编辑会话的生命周期信息。"""
        with self._state_lock:
            self._expire_if_due()
            preview = None
            if self.draft and self._terminal is None:
                preview = {"validation_id": self.draft["id"], "summary": self.draft["summary"],
                           **self._restored_form()}
            return {"session_id": self.session_id, "phase": self._phase, "expires_at": self.expires_at,
                    "model": MODEL, "region": "cn-beijing",
                    "output_defaults": {"json": str(self.runtime.output_root),
                                        "document": str(self.runtime.output_root)},
                    "languages": LANGUAGE_CODES,
                    "audio_suffixes": sorted(AUDIO_SUFFIXES),
                    "limits": {"hotwords_bytes": MAX_XLSX_BYTES,
                               "upload_bytes": MAX_UPLOAD_BYTES, "audio_seconds": MAX_DURATION_SECONDS,
                               "hotwords_count": MAX_HOTWORDS,
                               "context_chars": MAX_CONTEXT_CHARS, "speaker_min": MIN_SPEAKERS,
                               "speaker_max": MAX_SPEAKERS},
                    "audio": deepcopy(self.selected_audio), "audio_error": deepcopy(self.audio_error),
                    "preview": deepcopy(preview), "terminal": deepcopy(self._terminal)}

    def receive_hotwords(self, name: str, source: BinaryIO | BufferedIOBase, size: int) -> dict[str, object]:
        """在内存中接收Excel并返回可编辑的原始词条。"""
        field = "hotword_rows"
        if (not name or len(name) > 255 or any(char in name for char in "/\\\0")
                or any(ord(char) < 32 for char in name) or Path(name).suffix.lower() != ".xlsx"):
            raise ValidationError("所选文件名或格式不符合要求。", field)
        if not 0 < size <= MAX_XLSX_BYTES:
            raise ValidationError("文件为空或超过本机接收上限。", field)
        with self._state_lock:
            self._require_editable()
            if self._receiving_hotwords:
                raise ValidationError("此类文件正在添加，请稍候。", field)
            self._receiving_hotwords = True
            self.draft = None
        try:
            with BytesIO() as content:
                remaining = size
                while remaining:
                    with self._state_lock:
                        self._require_open()
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValidationError("传入的文件不完整，请重新选择。", field)
                    content.write(chunk)
                    remaining -= len(chunk)
                result = import_hotwords(content.getvalue())
            with self._state_lock:
                self._require_editable()
            return {"ok": True, "name": name, **result}
        finally:
            with self._state_lock:
                self._receiving_hotwords = False

    def audio_selection(self, identifier: object) -> AudioSelection:
        """按当前编辑会话的选择编号取得录音原文件信息。"""
        if not self.selected_audio or identifier != self.selected_audio["audio_id"]:
            raise ValidationError("请选择录音。", "audio_id")
        return self.selected_audio

    def cleanup(self) -> None:
        """关闭编辑会话和原生窗口，并通知热词接收请求结束。"""
        # 状态关闭与输入结果登记使用同一短锁，迟到结果会被拒绝。
        with self._state_lock:
            self._closed.set()
            if self._terminal is None:
                self._finish("cancelled")
        self._picker.close()

    def validate(self, payload: Mapping[str, object]) -> dict[str, object]:
        """读取所选录音原文件并检查当前表单，生成预览快照。"""
        with self._state_lock:
            self._require_editable()
            self._require_import_complete()
            self.draft = None  # 即使新校验失败，旧预览也不再可确认。
            allowed = {"auth_mode", "audio_id", "diarization_enabled", "enhancement_mode",
                       "hotword_rows", "context", "json_directory", "document_directory",
                       "language_hint", "speaker_count"}
            if set(payload) - allowed:
                raise ValidationError("请求含不支持的配置字段。", "form")
            mode_value = payload.get("auth_mode")
            if mode_value not in ("console", "api_key"):
                raise ValidationError("请选择有效的鉴权方式。", "auth_mode")
            mode = cast(AuthMode, mode_value)
            diarization = payload.get("diarization_enabled")
            recognition_options = validate_options(payload, diarization)
            enhancement_value = payload.get("enhancement_mode")
            hotwords = None
            context = None
            if enhancement_value not in ("none", "hotwords", "context", "both"):
                raise ValidationError("请选择有效的识别增强方式。", "enhancement_mode")
            enhancement = cast(EnhancementMode, enhancement_value)
            if enhancement in ("hotwords", "both"):
                hotwords = validate_hotword_rows(payload.get("hotword_rows"))
            if enhancement in ("context", "both"):
                context = validate_context(payload.get("context"))
            # 先报告可直接修改的文本问题，再读取可能较大的录音。
            source = self.audio_selection(payload.get("audio_id"))
            audio = validate_audio(source["path"], diarization)
            audio["name"] = source["name"]
            warnings = [*audio["warnings"], *(hotwords["warnings"] if hotwords else [])]

            json_base = output_directory(self.runtime, payload.get("json_directory"), "json_directory", self.output_directories.get("json"))
            document_base = output_directory(self.runtime, payload.get("document_directory"), "document_directory", self.output_directories.get("document"))
            config: TranscriptionSettings = {
                "model": MODEL, "region": "cn-beijing",
                "auth_mode": mode, "audio": audio, "diarization_enabled": cast(bool, diarization),
                "recognition_options": recognition_options,
                "enhancement": {"mode": enhancement, "hotwords": hotwords, "context": context},
            }
            summary: dict[str, object] = {
                "auth_mode": mode,
                "audio": {"name": audio["name"], "path": audio["path"], **{
                    field: value for field, value in audio["metadata"].items() if field != "audio_tracks"}},
                "enhancement": {"mode": enhancement, "count": hotwords["count"] if hotwords else 0,
                                "context_chars": len(context) if context else 0},
                "json_directory": str(json_base), "document_directory": str(document_base),
                "warnings": warnings,
            }
            self._require_open()  # 大文件检查可能跨过截止时间，发布预览前再次核对时限。
            self.draft = {"id": secrets.token_urlsafe(24), "config": config, "form": deepcopy(dict(payload)),
                          "summary": summary, "json_base": json_base, "document_base": document_base}
            return {"ok": True, "validation_id": self.draft["id"], "summary": summary}

    def _restored_form(self) -> dict[str, object]:
        """整理当前预览的输入快照及网页需要的录音显示信息。"""
        assert self.draft is not None
        form = self.draft["form"]
        audio = self.draft["config"]["audio"]
        return {"configuration": deepcopy(form),
                "audio": {"audio_id": form["audio_id"], "name": audio["name"], "path": audio["path"],
                          "size_bytes": audio["fingerprint"]["size_bytes"]}}

    def preview_ready(self, validation_id: object) -> dict[str, bool]:
        """登记页面已展示的当前预览，允许Codex随后确认交接。"""
        with self._state_lock:
            self._require_open()
            if not self.draft or validation_id != self.draft["id"]:
                raise ValidationError("转写设置已变更，请重新检查并预览。", "confirmation")
            self._phase = "preview"
            return {"ok": True}

    def edit(self, validation_id: object) -> dict[str, object]:
        """退出当前预览并恢复表单，使旧预览立即失去交接资格。"""
        with self._state_lock:
            self._require_open()
            if not self.draft or validation_id != self.draft["id"]:
                raise ValidationError("转写设置已变更，请重新检查并预览。", "confirmation")
            restored = self._restored_form()
            self._phase = "editing"
            self.draft = None
            return {"ok": True, **restored}

    def confirm(self) -> ConfirmationReceipt:
        """将已展示的预览交接为一个不可变转写任务，并持久保存交接回执。"""
        with self._state_lock:
            if self.receipt:
                return deepcopy(self.receipt)
            self._require_open()
            self._require_import_complete()
            if self._phase != "preview" or not self.draft:
                raise ValidationError("请先在网页完成填写并进入预览页，再回到 Codex 确认。", "confirmation")
            # 确认复用预览快照；执行前再比较完整摘要。
            audio = self.draft["config"]["audio"]
            try:
                path = resolve_input(audio["path"], AUDIO_SUFFIXES)
                check_file_unchanged(path, audio["fingerprint"])
            except FileError as exc:
                self.draft = None
                self._phase = "editing"
                raise ValidationError(exc.template, "audio_id") from exc
            self._require_open()
            job_id = uuid.uuid4().hex
            config: JobConfig = {
                **self.draft["config"], "schema_version": 1, "job_id": job_id,
                "json_directory": str(self.draft["json_base"] / job_id / "json"),
                "document_directory": str(self.draft["document_base"] / job_id / "documents"),
                "status": "CONFIGURED", "execution_authorized": True,
                "confirmed_at": datetime.fromtimestamp(self._clock(), timezone.utc).isoformat(),
            }
            directory = job_directory(self.runtime, job_id)
            source = directory / "execution/mono.flac" if audio["requires_mono"] else Path(audio["path"])
            try:
                check_recognition_command(self.runtime, recognition_arguments(config, source, result_path(config)))
            except SetupError as exc:
                raise ValidationError(exc.template, "form", **exc.params) from exc
            receipt: ConfirmationReceipt = {
                "ok": True, "session_id": self.session_id, "job_id": job_id,
                "config_path": str(directory / "config.json"),
                "auth_mode": config["auth_mode"], "json_directory": config["json_directory"],
                "document_directory": config["document_directory"], "execution_started": False,
            }
            # config.json由publish_config最后原子发布；回执读取以它作为交接完成标记。
            write_receipt(self.runtime, self.session_id, receipt)
            publish_config(self.runtime, config)
            self.receipt = receipt
            self._finish("handed_off")
            return deepcopy(self.receipt)
