"""管理已有转写的人工回听、版本化校对草稿及独立成品导出。"""

import json
import threading
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Literal, cast

from ..models import DeliveryReport, LocalizedText, ReviewDraft, ReviewSentence, Sentence
from ..utils.environment import Runtime, SetupError
from ..utils.files import FileError, check_file_unchanged, file_fingerprint, resolve_input, write_json_atomic
from ..utils.job_files import job_directory, read_config, read_execution, result_path
from ..utils.media import MediaError, prepare_playback
from ..utils.path_picker import PathPicker
from ..utils.results import load_transcript
from .delivery import export_documents
from .rules import AUDIO_SUFFIXES, ValidationError


class ReviewError(ValidationError):
    """携带校对页面可直接显示的双语错误，不暴露第三方异常正文。"""

    def __init__(self, zh: str, en: str, field: str = "review") -> None:
        """保存字段与双语说明，复用网页的校验错误协议。"""
        ValueError.__init__(self, zh)
        self.message: LocalizedText = {"zh": zh, "en": en}
        self.field = field
        self.details = []


class ReviewConflict(ReviewError):
    """表示校对版本已变化，需要重新读取后再保存。"""

    def __init__(self) -> None:
        """提示保留当前输入并重新取得已保存版本。"""
        super().__init__("校对版本已变化，请保留当前输入并刷新页面后再保存。",
                         "The review has changed. Keep your edits and reload the page before saving.")


def _review_directory(runtime: Runtime, job_id: str) -> Path:
    """定位任务自己的校对记录目录，拒绝重定向。"""
    path = job_directory(runtime, job_id) / "review"
    if path.resolve() != path:
        raise SetupError("校对记录目录不能重定向。")
    return path


def _read_delivery(path: Path, job_id: str) -> DeliveryReport | None:
    """读取校对导出记录，损坏时仅报告交付结果未知。"""
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_bytes())
        if (path.resolve() != path or not isinstance(value, dict) or value.get("job_id") != job_id
                or value.get("status") not in ("EXPORTING", "COMPLETE", "PARTIAL", "FAILED")
                or type(value.get("export_revision")) is not int or value["export_revision"] < 0
                or not isinstance(value.get("message"), str)):
            raise ValueError("invalid review status")
        if value["status"] == "COMPLETE":
            files = value.get("files")
            if (not isinstance(files, dict) or set(files) != {"xlsx", "docx", "md"}
                    or any(not isinstance(record, dict) or record.get("status") != "READY"
                           or not isinstance(record.get("path"), str) or not record["path"] for record in files.values())):
                raise ValueError("incomplete review delivery")
        return cast(DeliveryReport, value)
    except (OSError, ValueError, TypeError):
        return {"status": "OUTCOME_UNKNOWN", "message": "校对导出记录不可读，请检查已生成文件；未自动重导。"}


def read_review_status(runtime: Runtime, job_id: str) -> dict[str, object] | None:
    """读取草稿版本与校验导出记录，向任务查询返回状态摘要。"""
    directory = _review_directory(runtime, job_id)
    if not directory.exists():
        return None
    revision = 0
    draft = directory / "draft.json"
    try:
        if draft.exists():
            value = json.loads(draft.read_bytes())
            if draft.resolve() != draft or not isinstance(value, dict) or type(value.get("revision")) is not int or value["revision"] < 0:
                raise ValueError("invalid revision")
            revision = value["revision"]
    except (OSError, ValueError, TypeError):
        return {"status": "OUTCOME_UNKNOWN", "message": "校对草稿不可读，已保留原文件，请检查记录。"}
    delivery = _read_delivery(directory / "status.json", job_id)
    return {"revision": revision, "delivery": delivery,
            "export_revision": delivery.get("export_revision") if delivery else None}


class ReviewSession:
    def __init__(self, runtime: Runtime, job_id: str) -> None:
        """核对原结果与摘要，恢复草稿并绑定可回听的原录音或单声道副本。"""
        self.runtime = runtime
        self.job_id = job_id
        self.config = read_config(runtime, job_id)
        execution = read_execution(job_directory(runtime, job_id))
        if execution is None or execution["status"] != "JSON_READY":
            raise ReviewError("任务尚无通过检查的转写JSON，不能打开人工回听。",
                              "This task has no verified transcript JSON to review.")
        self._source = load_transcript(result_path(self.config))
        expected = execution.get("result")
        if not isinstance(expected, dict) or self._source.sha256 != expected.get("sha256"):
            raise ReviewError("原始转写JSON与任务摘要不符，已保留文件，未打开校对。",
                              "The original transcript no longer matches the task checksum. Review was not opened.")
        self._directory = _review_directory(runtime, job_id)
        self._lock = threading.Lock()
        self._picker = PathPicker()
        self._closed = False
        self._exporting = False
        self._preparing_audio = False
        self._revision = 0
        self._changes: dict[int, ReviewSentence] = {}
        self._names: dict[int, str] = {}
        self._selected_path: str | None = None
        self._audio: Path | None = None
        self._audio_kind: Literal["original", "mono", "preview"] | None = None
        self._audio_stat: tuple[int, int, int] | None = None
        self._audio_error: LocalizedText | None = None
        self._load_draft()
        self._directory.mkdir(parents=True, exist_ok=True)
        self._delivery = _read_delivery(self._directory / "status.json", job_id)
        self._bind_initial_audio()

    def _require_open(self) -> None:
        """拒绝关闭后的校对写入或媒体操作。"""
        if self._closed:
            raise ReviewError("人工回听页面已关闭，请回到Codex重新打开。",
                              "This review is closed. Return to Codex to reopen it.")

    def _check_revision(self, payload: Mapping[str, object]) -> None:
        """核对客户端基于同一已保存版本提交更改。"""
        if type(payload.get("revision")) is not int or payload["revision"] != self._revision:
            raise ReviewConflict()

    @staticmethod
    def _text(value: object) -> str:
        """接受可保存为UTF-8的原文，不修剪或改写用户输入。"""
        if not isinstance(value, str):
            raise ReviewError("正文与说话人姓名必须为文字。", "Text and speaker names must be strings.")
        try:
            value.encode("utf-8")
        except UnicodeError as exc:
            raise ReviewError("输入含无法保存的字符，请删除后再保存。",
                              "The input contains an invalid character. Remove it before saving.") from exc
        return value

    def _validate_changes(self, rows: object) -> dict[int, ReviewSentence]:
        """检查句子改动只包含原有序号、正文与合法说话人编号。"""
        if not isinstance(rows, list):
            raise ReviewError("句子改动格式不正确。", "The sentence edits are invalid.")
        changes: dict[int, ReviewSentence] = {}
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"index", "text", "speaker_id"}
                    or type(row["index"]) is not int or not 1 <= row["index"] <= len(self._source.sentences)
                    or row["index"] in changes
                    or (row["speaker_id"] is not None and (type(row["speaker_id"]) is not int or row["speaker_id"] < 0))):
                raise ReviewError("只能修改已有句子的正文和说话人，不能更改时间或顺序。",
                                  "Only the text and speaker of existing sentences can be edited; timing and order stay fixed.")
            changes[row["index"]] = {"index": row["index"], "text": self._text(row["text"]),
                                      "speaker_id": row["speaker_id"]}
        return changes

    def _validate_speakers(self, rows: object) -> dict[int, str]:
        """检查说话人名称列表，并保留新增的非负整数编号。"""
        if not isinstance(rows, list):
            raise ReviewError("说话人列表格式不正确。", "The speaker list is invalid.")
        names: dict[int, str] = {}
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"id", "name"}
                    or type(row["id"]) is not int or row["id"] < 0 or row["id"] in names):
                raise ReviewError("说话人编号必须是互不重复的非负整数。",
                                  "Speaker IDs must be distinct non-negative integers.")
            names[row["id"]] = self._text(row["name"])
        return names

    def _load_draft(self) -> None:
        """恢复与原JSON匹配的草稿；损坏的记录保留并停止打开。"""
        path = self._directory / "draft.json"
        if not path.exists():
            return
        try:
            value = json.loads(path.read_bytes())
            if (path.resolve() != path or not isinstance(value, dict)
                    or value.get("source_sha256") != self._source.sha256
                    or type(value.get("revision")) is not int or value["revision"] < 0
                    or (value.get("audio_path") is not None and not isinstance(value["audio_path"], str))):
                raise ValueError("invalid draft")
            self._changes = self._validate_changes(value["sentences"])
            self._names = self._validate_speakers(value["speakers"])
            self._revision = value["revision"]
            self._selected_path = value.get("audio_path")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ReviewError("校对草稿损坏或与原JSON不符，已保留文件，请先检查。",
                              "The review draft is unreadable or belongs to a different transcript. The file was preserved.") from exc

    def _write_draft(self, changes: dict[int, ReviewSentence], names: dict[int, str],
                     audio: str | None) -> int:
        """先原子保存新版本，再更新内存；保存失败保留原版本和输入。"""
        revision = self._revision + 1
        draft: ReviewDraft = {"revision": revision, "source_sha256": self._source.sha256,
                              "sentences": list(changes.values()),
                              "speakers": [{"id": identifier, "name": name} for identifier, name in names.items()],
                              "audio_path": audio}
        try:
            write_json_atomic(self._directory / "draft.json", draft)
        except OSError as exc:
            raise ReviewError("校对未保存，请保留当前输入并检查目录权限或磁盘空间。",
                              "The review was not saved. Keep your edits and check folder permissions or disk space.") from exc
        self._revision, self._changes, self._names, self._selected_path = revision, changes, names, audio
        return revision

    def _sentences(self) -> tuple[Sentence, ...]:
        """从原句子合并正文、归属和姓名，保留原时间与顺序。"""
        result = []
        for original in self._source.sentences:
            change = self._changes.get(original.index)
            speaker = change["speaker_id"] if change else original.speaker_id
            result.append(replace(original, text=change["text"] if change else original.text,
                                  speaker_id=speaker, speaker_name=self._names.get(speaker) if speaker is not None else None))
        return tuple(result)

    def _bind_audio(self, path: Path, kind: Literal["original", "mono", "preview"]) -> None:
        """绑定已核对的普通音频文件及属性，供后续流式播放读取。"""
        if path.resolve() != path or not path.is_file():
            raise OSError("invalid audio path")
        with path.open("rb"):
            pass
        stat = path.stat()
        self._audio, self._audio_kind = path, kind
        self._audio_stat = (stat.st_size, stat.st_mtime_ns, stat.st_ino)
        self._audio_error = None

    def _verify_recording(self, path: Path) -> Path:
        """按原录音SHA核对重新选择的文件，允许原内容移动到新位置。"""
        selected = resolve_input(path, AUDIO_SUFFIXES)
        actual = file_fingerprint(selected)
        expected = self.config["audio"]["fingerprint"]
        if (actual["size_bytes"], actual["sha256"]) != (expected["size_bytes"], expected["sha256"]):
            raise ReviewError("所选文件与本任务的原录音不一致，请选择原文件。",
                              "The selected file does not match this task's recording. Select the original file.", "audio")
        return selected

    def _bind_initial_audio(self) -> None:
        """先尝试原录音或已重选原文件，无法读取时使用已有单声道副本。"""
        try:
            if self._selected_path:
                original = self._verify_recording(Path(self._selected_path))
            else:
                original = resolve_input(self.config["audio"]["path"], AUDIO_SUFFIXES)
                check_file_unchanged(original, self.config["audio"]["fingerprint"])
            self._bind_audio(original, "original")
            return
        except (OSError, FileError, ReviewError):
            pass
        try:
            self._bind_audio(job_directory(self.runtime, self.job_id) / "execution/mono.flac", "mono")
        except OSError:
            self._audio_error = {"zh": "原录音和单声道副本均无法读取，请重新选择原录音。",
                                 "en": "Neither the original recording nor its mono copy is available. Select the original recording again."}

    def _audio_description(self) -> dict[str, object]:
        """只返回播放可用性与文件名，不向页面暴露本机文件路径。"""
        available = self._audio is not None
        if available:
            try:
                self._check_audio()
            except ReviewError as exc:
                available = False
                self._audio_error = exc.message
        return {"available": available, "name": self._audio.name if self._audio else "",
                "kind": self._audio_kind if available else None, "error": deepcopy(self._audio_error)}

    def _check_audio(self) -> Path:
        """检查绑定文件仍在原位置且未改变，不接受页面传入任意路径。"""
        try:
            if self._audio is None or self._audio.resolve() != self._audio:
                raise OSError("missing audio")
            stat = self._audio.stat()
            if (stat.st_size, stat.st_mtime_ns, stat.st_ino) != self._audio_stat:
                raise OSError("changed audio")
            return self._audio
        except OSError as exc:
            raise ReviewError("回听录音不可用或已发生变化，请重新选择原录音。",
                              "The recording is unavailable or has changed. Select the original recording again.", "audio") from exc

    def description(self) -> dict[str, object]:
        """返回已保存校对内容、音频可用性和最近导出版本。"""
        with self._lock:
            sentences = self._sentences()
            speakers = {sentence.speaker_id for sentence in (*self._source.sentences, *sentences)
                        if sentence.speaker_id is not None} | self._names.keys()
            return {"job_id": self.job_id, "skill_version": self.runtime.skill_version, "model": self.config["model"],
                    "source_name": self.config["audio"]["name"], "revision": self._revision,
                    "sentences": [{"index": sentence.index, "begin_ms": sentence.begin_ms, "end_ms": sentence.end_ms,
                                   "text": sentence.text, "speaker_id": sentence.speaker_id,
                                   "original_text": original.text, "original_speaker_id": original.speaker_id}
                                  for original, sentence in zip(self._source.sentences, sentences)],
                    "speakers": [{"id": identifier, "name": self._names.get(identifier, "")} for identifier in sorted(speakers)],
                    "audio": self._audio_description(), "delivery": deepcopy(self._delivery),
                    "export_revision": self._delivery.get("export_revision") if self._delivery else None, "closed": self._closed}

    def save(self, payload: Mapping[str, object]) -> dict[str, object]:
        """合并本批句子和姓名改动，保存成功后返回新版本。"""
        with self._lock:
            self._require_open()
            self._check_revision(payload)
            if set(payload) - {"revision", "sentences", "speakers"}:
                raise ReviewError("请求含不支持的校对字段。", "The request contains unsupported review fields.")
            changes = dict(self._changes)
            for index, change in self._validate_changes(payload.get("sentences", [])).items():
                original = self._source.sentences[index - 1]
                if (change["text"], change["speaker_id"]) == (original.text, original.speaker_id):
                    changes.pop(index, None)
                else:
                    changes[index] = change
            names = {**self._names, **self._validate_speakers(payload.get("speakers", []))}
            if changes == self._changes and names == self._names:
                return {"ok": True, "revision": self._revision}
            return {"ok": True, "revision": self._write_draft(changes, names, self._selected_path)}

    def export(self, payload: Mapping[str, object]) -> dict[str, object]:
        """选择导出目录后冻结已保存版本，生成三种独立校对稿。"""
        with self._lock:
            self._require_open()
            self._check_revision(payload)
            if set(payload) != {"revision", "picker_id"}:
                raise ReviewError("请先保存校对内容，再导出当前版本。", "Save your edits before exporting the current revision.")
            if self._exporting:
                raise ReviewError("校对稿正在导出，请等待本次完成。", "Review documents are being exported. Wait for this export to finish.")
            initial = Path(self.config["document_directory"])
            if self._delivery:
                for record in self._delivery.get("files", {}).values():
                    if record.get("status") == "READY" and record.get("path"):
                        previous = Path(record["path"]).parent
                        if previous.is_dir():
                            initial = previous
                            break
        selected = self._picker.select(initial if initial.is_dir() else self.runtime.workspace,
                                        payload["picker_id"], mode="directory")
        if selected is None:
            return {"ok": True, "cancelled": True}
        with self._lock:
            self._require_open()
            self._check_revision(payload)
            if self._exporting:
                raise ReviewError("校对稿正在导出，请等待本次完成。", "Review documents are being exported. Wait for this export to finish.")
            revision = self._revision
            transcript = replace(self._source, sentences=self._sentences())
            self._exporting = True
            self._delivery = {"status": "EXPORTING", "export_revision": revision, "message": "正在本机生成校对稿。"}
        try:
            delivery = export_documents(self.runtime, self.config, transcript, review_revision=revision,
                                        review_directory=selected)
        except (OSError, SetupError, KeyboardInterrupt) as exc:
            delivery = {"status": "OUTCOME_UNKNOWN", "export_revision": revision, "error_type": type(exc).__name__,
                        "message": "校对导出或记录保存中断，草稿及已有文件保留，请检查本机文件；未重新转写。"}
        except BaseException:
            with self._lock:
                self._exporting = False
            raise
        with self._lock:
            self._exporting = False
            self._delivery = delivery
            return {"ok": True, "cancelled": False, "delivery": deepcopy(delivery),
                    "export_revision": revision, "revision": self._revision}

    def audio_path(self) -> Path:
        """返回已经绑定并核对属性的音频文件，供HTTP范围读取。"""
        with self._lock:
            self._require_open()
            return self._check_audio()

    def select_audio(self, picker_id: object) -> dict[str, object]:
        """重新选择并验证原录音，只将新位置保存到校对草稿。"""
        with self._lock:
            self._require_open()
            initial = self._audio.parent if self._audio else self.runtime.workspace
        selected = self._picker.select(initial if initial.is_dir() else self.runtime.workspace, picker_id,
                                        mode="audio", audio_suffixes=tuple(sorted(AUDIO_SUFFIXES)))
        if selected is None:
            return {"ok": True, "cancelled": True}
        try:
            selected = self._verify_recording(selected)
        except (OSError, FileError) as exc:
            raise ReviewError("无法读取所选录音，请检查文件及访问权限。",
                              "The selected recording could not be read. Check the file and its permissions.", "audio") from exc
        with self._lock:
            self._require_open()
            self._write_draft(self._changes, self._names, str(selected))
            self._bind_audio(selected, "original")
            return {"ok": True, "cancelled": False, "revision": self._revision, "audio": self._audio_description()}

    def prepare_audio(self) -> dict[str, object]:
        """在浏览器不支持原格式时准备一次完整MP3，期间允许保存校对。"""
        with self._lock:
            self._require_open()
            source = self._check_audio()
            if self._audio_kind == "preview":
                return {"ok": True, "audio": self._audio_description()}
            if self._preparing_audio:
                raise ReviewError("播放音频正在准备，请稍候。", "Playback audio is being prepared. Please wait.", "audio")
            self._preparing_audio = True
        destination = self._directory / "playback.mp3"
        try:
            if destination.resolve() != destination:
                raise OSError("redirected playback")
            if not destination.is_file():
                prepare_playback(source, destination)
            with self._lock:
                self._require_open()
                if self._audio == source:
                    self._bind_audio(destination, "preview")
                return {"ok": True, "audio": self._audio_description()}
        except (OSError, MediaError) as exc:
            raise ReviewError("无法准备浏览器播放音频，原录音和校对草稿已保留。",
                              "Playback audio could not be prepared. The recording and review draft were preserved.", "audio") from exc
        finally:
            with self._lock:
                self._preparing_audio = False

    def close(self) -> None:
        """关闭校对会话和选择窗口，保留已保存草稿、播放副本及成品。"""
        with self._lock:
            self._closed = True
        self._picker.close()
