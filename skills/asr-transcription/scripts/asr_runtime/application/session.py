"""管理本机会话的文件上传、配置预览和确认流程。"""

import secrets
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from io import BufferedIOBase
from pathlib import Path
from typing import BinaryIO, TypedDict, cast

from .. import MODEL
from ..models import (
    AuthMode, ConfirmationReceipt, EnhancementMode, JobConfig, SessionEndState,
    SessionPhase, SessionTerminal, TranscriptionSettings,
)
from ..utils.auth import read_api_key, write_api_key
from ..utils.directory_picker import DirectoryPicker
from ..utils.environment import Runtime, SetupError
from ..utils.files import FileError, check_file_unchanged, resolve_input
from ..utils.hotwords import MAX_XLSX_BYTES
from ..utils.job_files import job_directory, publish_config
from ..utils.session_files import write_receipt
from .inputs import import_hotwords, validate_audio
from .rules import (
    AUDIO_SUFFIXES, ValidationError, validate_context, validate_hotword_rows, LANGUAGE_CODES, validate_options,
    MAX_CONTEXT_CHARS, MIN_SPEAKERS, MAX_SPEAKERS, MAX_UPLOAD_BYTES,
    MAX_DURATION_SECONDS, MAX_HOTWORDS,
)

MAX_LOCAL_AUDIO_BYTES = 2_000_000_000
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
        raise ValidationError(str(exc), field) from exc
    except OSError as exc:
        raise ValidationError("此文件夹无法保存文件，请选择其他位置。", field) from exc


class UploadRecord(TypedDict):
    """保存当前会话已完整接收音频的本机位置。"""

    path: str
    name: str


class Draft(TypedDict):
    """关联一次成功预览及其待确认的配置快照。"""

    id: str
    config: TranscriptionSettings
    form: dict[str, object]
    summary: dict[str, object]
    json_base: Path
    document_base: Path


class Session:
    def __init__(self, runtime: Runtime, *, clock: Callable[[], float] = time.time) -> None:
        """创建两小时编辑会话及其上传、预览和结束状态。"""
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
        self.upload_directory = runtime.root.resolve() / ".state/web-uploads" / self.session_id
        self.uploads: dict[str, UploadRecord] = {}
        self.output_directories: dict[str, Path] = {}
        self._picker = DirectoryPicker()
        self._closed = threading.Event()
        self._pending_uploads: set[str] = set()

    def _require_open(self) -> None:
        """检查截止时间和会话终态，拒绝继续操作已结束的会话。"""
        self._expire_if_due()
        if self._closed.is_set():
            raise ValidationError("当前会话已关闭。", "session")
        if self._phase == "expired":
            raise ValidationError("会话已失效，请回到 Codex 重新打开配置页。", "session")
        if self._terminal:
            raise ValidationError("当前编辑会话已结束，请回到 Codex 查看任务。", "session")

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

    def _require_uploads_complete(self) -> None:
        """检查上传完成状态，报告仍在接收的文件类型。"""
        if self._pending_uploads:
            kind = next(iter(self._pending_uploads))
            field = "audio_upload_id" if kind == "audio" else "hotword_rows"
            raise ValidationError("文件仍在添加，请稍候。", field)

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
            selected = self._picker.select(initial, picker_id)
        except SetupError as exc:
            raise ValidationError(str(exc), f"{kind}_directory") from exc
        if selected is None:
            return {"ok": True, "cancelled": True}
        path = selected  # 选择器已核对现有目录；这里只检查一次实际可写性。
        try:
            self.runtime.check_output_path(path)
            # 选择时检查一次可写性；预览和确认不反复创建探针文件。
            with tempfile.TemporaryFile(dir=path):
                pass
        except SetupError as exc:
            raise ValidationError(str(exc), f"{kind}_directory") from exc
        except OSError as exc:
            raise ValidationError("此文件夹无法保存文件，请选择其他位置。", f"{kind}_directory") from exc
        with self._state_lock:
            self._require_editable()
            self.output_directories[kind] = path
            self.draft = None
        return {"ok": True, "cancelled": False, "path": str(path)}

    def cancel_directory(self, picker_id: object) -> dict[str, bool]:
        """取消指定请求的目录选择等待。"""
        # 取消仅经过选择器自己的短锁，不等待文件接收、指纹或Excel校验。
        try:
            self._picker.cancel(picker_id)
        except SetupError as exc:
            raise ValidationError(str(exc), "directory") from exc
        return {"ok": True}

    def api_key_display(self) -> dict[str, str | bool]:
        """读取工作目录中的API Key，返回本机页面所需的显示数据。"""
        with self._state_lock:
            self._require_open()
            try:
                return {"ok": True, "value": read_api_key(self.runtime, required=False)}
            except (SetupError, OSError, UnicodeError) as exc:
                message = str(exc) if isinstance(exc, SetupError) else "无法读取 .env 文件。"
                raise ValidationError(message, "auth_mode") from exc

    def save_api_key(self, value: object) -> dict[str, bool]:
        """保存当前页面填写的Key，返回完成状态。"""
        with self._state_lock:
            self._require_editable()
            try:
                write_api_key(self.runtime, value)
            except (SetupError, OSError, UnicodeError) as exc:
                message = str(exc) if isinstance(exc, SetupError) else "无法保存 API Key，请检查工作目录的访问权限。"
                raise ValidationError(message, "auth_mode") from exc
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
                    "limits": {"audio_bytes": MAX_LOCAL_AUDIO_BYTES, "hotwords_bytes": MAX_XLSX_BYTES,
                               "upload_bytes": MAX_UPLOAD_BYTES, "audio_seconds": MAX_DURATION_SECONDS,
                               "hotwords_count": MAX_HOTWORDS,
                               "context_chars": MAX_CONTEXT_CHARS, "speaker_min": MIN_SPEAKERS,
                               "speaker_max": MAX_SPEAKERS},
                    "preview": deepcopy(preview), "terminal": deepcopy(self._terminal)}

    def upload(self, kind: str, name: str, source: BinaryIO | BufferedIOBase, size: int) -> dict[str, object]:
        """接收音频副本或导入热词，返回页面所需数据。"""
        if kind not in ("audio", "hotwords"):
            raise ValidationError("不支持的文件用途。", "upload")
        field = "audio_upload_id" if kind == "audio" else "hotword_rows"
        suffixes = AUDIO_SUFFIXES if kind == "audio" else {".xlsx"}
        maximum = MAX_LOCAL_AUDIO_BYTES if kind == "audio" else MAX_XLSX_BYTES
        if (not name or len(name) > 255 or any(char in name for char in "/\\\0")
                or any(ord(char) < 32 for char in name) or Path(name).suffix.lower() not in suffixes):
            raise ValidationError("所选文件名或格式不符合要求。", field)
        if not 0 < size <= maximum:
            raise ValidationError("文件为空或超过本机接收上限。", field)
        identifier = uuid.uuid4().hex
        destination = self.upload_directory / (identifier + Path(name).suffix.lower())
        partial = destination.with_suffix(destination.suffix + ".part")
        with self._state_lock:
            self._require_editable()
            if kind in self._pending_uploads:
                raise ValidationError("此类文件正在添加，请稍候。", field)
            if self.upload_directory.resolve() != self.upload_directory:
                raise ValidationError("本地文件暂存目录不能重定向。", field)
            self.upload_directory.mkdir(parents=True, exist_ok=True)
            # 在关闭标记和暂存文件之间保持原子登记；cleanup不删除活动上传拥有的文件。
            output = partial.open("xb")
            self._pending_uploads.add(kind)
            self.draft = None
        published = False
        try:
            with output:
                remaining = size
                while remaining:
                    with self._state_lock:
                        self._require_open()
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValidationError("传入的文件不完整，请重新选择。", field)
                    output.write(chunk)
                    remaining -= len(chunk)
            if kind == "hotwords":
                result = import_hotwords(partial)
                with self._state_lock:
                    self._require_editable()
                # Excel只作导入来源，编辑后的行随预览提交；读取完成即清理副本。
                return {"ok": True, "name": name, "size_bytes": size, **result}
            with self._state_lock:
                self._require_editable()
                partial.replace(destination)
                # 新文件完整后再替换旧副本；失败也不会恢复已废弃的旧预览。
                for old_id, old in list(self.uploads.items()):
                    Path(old["path"]).unlink(missing_ok=True)
                    del self.uploads[old_id]
                self.uploads[identifier] = {"path": str(destination), "name": name}
                published = True
            return {"ok": True, "upload_id": identifier, "name": name, "size_bytes": size}
        finally:
            try:
                if not published:
                    partial.unlink(missing_ok=True)
                    destination.unlink(missing_ok=True)
            finally:
                with self._state_lock:
                    self._pending_uploads.remove(kind)
                    if self._closed.is_set():
                        self._remove_empty_upload_directory()

    def uploaded_audio(self, identifier: object) -> UploadRecord:
        """按会话上传编号查找已完成的音频副本。"""
        if not isinstance(identifier, str) or identifier not in self.uploads:
            raise ValidationError("请选择音频文件。", "audio_upload_id")
        return self.uploads[identifier]

    def _remove_empty_upload_directory(self) -> None:
        """移除上传结束后的空会话目录。"""
        if (not self._pending_uploads and self.upload_directory.exists()
                and not any(self.upload_directory.iterdir())):
            self.upload_directory.rmdir()

    def cleanup(self) -> None:
        """关闭会话和目录窗口，清理临时副本并保留已确认音频。"""
        # 与发布上传结果使用同一短锁，不能在“检查开放→发布”之间插入关闭标记。
        with self._state_lock:
            self._closed.set()
            if self._terminal is None:
                self._finish("cancelled")
        self._picker.close()
        with self._state_lock:
            keep: set[str] = set()
            if self.receipt and self.draft:
                config = self.draft["config"]
                keep.add(config["audio"]["path"])
            if self.upload_directory.resolve() != self.upload_directory:
                return
            for record in self.uploads.values():
                if record["path"] not in keep:
                    Path(record["path"]).unlink(missing_ok=True)
            self._remove_empty_upload_directory()

    def validate(self, payload: Mapping[str, object]) -> dict[str, object]:
        """读取已上传内容并应用规则，生成确认快照和面向网页的预览。"""
        with self._state_lock:
            self._require_editable()
            self._require_uploads_complete()
            self.draft = None  # 即使新校验失败，旧预览也不再可确认。
            allowed = {"auth_mode", "audio_upload_id", "diarization_enabled", "enhancement_mode",
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
            source = self.uploaded_audio(payload.get("audio_upload_id"))
            audio = validate_audio(self.upload_directory, source["path"], diarization)
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
                "audio": {"name": audio["name"], **{
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

    def check_hotwords(self, rows: object) -> dict[str, object]:
        """检查可编辑词表，返回行级问题供表格定位与标红。"""
        with self._state_lock:
            self._require_editable()
        try:
            result = validate_hotword_rows(rows)
            return {"ok": True, "count": result["count"], "issues": [], "warnings": result["warnings"]}
        except ValidationError as exc:
            if not exc.details:
                raise
            return {"ok": True, "count": 0, "issues": exc.details, "warnings": []}

    def _restored_form(self) -> dict[str, object]:
        """整理当前预览的输入快照及网页需要的音频显示信息。"""
        assert self.draft is not None
        form = self.draft["form"]
        audio = self.draft["config"]["audio"]
        return {"configuration": deepcopy(form),
                "audio": {"upload_id": form["audio_upload_id"], "name": audio["name"],
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
        """将已展示的预览交接为一个不可变任务，并持久保存会话回执。"""
        with self._state_lock:
            if self.receipt:
                return deepcopy(self.receipt)
            self._require_open()
            self._require_uploads_complete()
            if self._phase != "preview" or not self.draft:
                raise ValidationError("请先在网页完成填写并进入预览页，再回到 Codex 确认。", "confirmation")
            # 确认复用预览快照；执行前再比较完整摘要。
            audio = self.draft["config"]["audio"]
            try:
                path = resolve_input(self.upload_directory, audio["path"], AUDIO_SUFFIXES)
                check_file_unchanged(path, audio["fingerprint"])
            except FileError as exc:
                self.draft = None
                self._phase = "editing"
                raise ValidationError(str(exc), "audio_path") from exc
            self._require_open()
            job_id = uuid.uuid4().hex
            config: JobConfig = {
                **self.draft["config"], "schema_version": 1, "job_id": job_id,
                "json_directory": str(self.draft["json_base"] / job_id / "json"),
                "document_directory": str(self.draft["document_base"] / job_id / "documents"),
                "status": "CONFIGURED", "execution_authorized": True,
                "confirmed_at": datetime.fromtimestamp(self._clock(), timezone.utc).isoformat(),
            }
            receipt: ConfirmationReceipt = {
                "ok": True, "session_id": self.session_id, "job_id": job_id,
                "config_path": str(job_directory(self.runtime, job_id) / "config.json"),
                "auth_mode": config["auth_mode"], "json_directory": config["json_directory"],
                "document_directory": config["document_directory"], "execution_started": False,
            }
            # config.json由publish_config最后原子发布；回执读取以它作为交接完成标记。
            write_receipt(self.runtime, self.session_id, receipt)
            publish_config(self.runtime, config)
            self.receipt = receipt
            self._finish("handed_off")
            return deepcopy(self.receipt)
