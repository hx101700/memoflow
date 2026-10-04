"""管理任务配置、执行占用、状态记录和输出目录。"""

import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from ..models import DeliveryReport, ExecutionReport, JobConfig
from .environment import Runtime, SetupError
from .files import write_json_atomic


def job_directory(runtime: Runtime, job_id: str) -> Path:
    """核对回执编号与路径归属，返回任务目录。"""
    if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise SetupError("任务编号应为Codex交接回执中的32位小写十六进制编号。")
    path = runtime.path(f".state/jobs/{job_id}")
    if path != runtime.root.resolve() / ".state/jobs" / job_id:
        raise SetupError("任务目录不能重定向。")
    return path


def publish_config(runtime: Runtime, config: JobConfig) -> Path:
    """保存确认配置及其内容摘要，完成写入后发布配置文件。"""
    directory = job_directory(runtime, config["job_id"])
    directory.mkdir(parents=True, exist_ok=False)
    temporary = directory / "config.json.tmp"
    destination = directory / "config.json"
    content = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with temporary.open("xb") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())
    with (directory / "config.sha256").open("x", encoding="ascii") as checksum:
        checksum.write(hashlib.sha256(content).hexdigest() + "\n")
        checksum.flush()
        os.fsync(checksum.fileno())
    temporary.replace(destination)
    return destination


def read_config(runtime: Runtime, job_id: str) -> JobConfig:
    """读取已确认配置，并核对保存协议与内容摘要。"""
    path = job_directory(runtime, job_id) / "config.json"
    checksum = path.with_suffix(".sha256")
    if path.resolve() != path or checksum.resolve() != checksum:
        raise SetupError("任务配置不能使用符号链接。")
    if not checksum.is_file():
        raise SetupError("此任务缺少确认摘要，请回到Codex重新配置并确认新任务；未上传。")
    try:
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != checksum.read_text(encoding="ascii").strip():
            raise SetupError("已确认的配置发生变化，请回到Codex重新配置并确认新任务；未执行转写。")
        config = json.loads(content)
        # 模型记录用于标注原结果；是否允许新上传由转写入口按当前固定模型判断。
        valid = (config["schema_version"] == 1 and config["job_id"] == job_id
                 and isinstance(config["model"], str) and bool(config["model"].strip())
                 and config["region"] == "cn-beijing"
                 and config["status"] == "CONFIGURED"
                 and config["execution_authorized"] is True and bool(config["confirmed_at"]))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SetupError("无法读取已确认的配置，请回到Codex重新配置并确认新任务。") from exc
    if not valid:
        raise SetupError("任务配置的模型名称、地域或保存协议不符，未执行。")
    # 配置由publish_config生成；上面的协议和摘要检查确定读取的是确认快照。
    return cast(JobConfig, config)


def reserve_execution(runtime: Runtime, job_id: str) -> Path:
    """独占创建执行目录，登记本任务的一次执行占用。"""
    path = job_directory(runtime, job_id) / "execution"
    path.mkdir(exist_ok=False)
    return path


def read_execution(root: Path) -> ExecutionReport | None:
    """读取执行记录；已占用任务的记录缺失或损坏时返回结果未知。"""
    execution = root / "execution"
    if execution.resolve() != execution:
        raise SetupError("执行记录目录不能重定向。")
    if not execution.exists():
        return None
    try:
        report = json.loads((execution / "status.json").read_text(encoding="utf-8"))
        if (not isinstance(report, dict) or report.get("job_id") != root.name
                or report.get("status") not in ("PREPARING", "RUNNING", "STOPPED", "JSON_READY")):
            raise ValueError("invalid status")
        return cast(ExecutionReport, report)
    except (OSError, ValueError):
        return {"job_id": root.name, "status": "OUTCOME_UNKNOWN", "cloud_outcome": "unknown",
                "message": "任务已被占用但执行记录不可读，不能重新提交。请检查本地进程和记录。"}


def read_delivery(root: Path) -> DeliveryReport | None:
    """读取任务的导出状态，记录损坏时返回结果未知。"""
    directory = root / "delivery"
    if not directory.exists():
        return None
    try:
        if directory.resolve() != directory:
            raise ValueError("redirected report")
        report = json.loads((directory / "status.json").read_text(encoding="utf-8"))
        if (not isinstance(report, dict) or report.get("job_id") != root.name
                or report.get("status") not in ("EXPORTING", "COMPLETE", "PARTIAL", "FAILED")
                or not isinstance(report.get("message"), str)):
            raise ValueError("invalid report")
        if report["status"] == "COMPLETE":
            files = report.get("files", {})
            if (not isinstance(files, dict) or set(files) != {"xlsx", "docx", "md"}
                    or any(not isinstance(record, dict) or record.get("status") != "READY"
                           or not record.get("path") for record in files.values())):
                raise ValueError("incomplete delivery")
        return cast(DeliveryReport, report)
    except (OSError, ValueError, TypeError):
        return {"status": "OUTCOME_UNKNOWN", "message": "本地导出记录不可读，请检查已有文件；不会重新识别或自动导出。"}


def prepare_delivery(root: Path) -> Path:
    """准备任务的固定导出状态目录。"""
    state = root / "delivery"
    if state.resolve() != state:
        raise SetupError("导出记录目录不能重定向。")
    state.mkdir(parents=True, exist_ok=True)
    return state


def result_path(config: JobConfig) -> Path:
    """解析已确认的JSON保存路径，并核对任务目录归属。"""
    directory = Path(config["json_directory"])
    if (not directory.is_absolute() or directory.name != "json"
            or directory.parent.name != config["job_id"] or directory.resolve() != directory):
        raise SetupError("JSON保存位置发生变化或不是已确认的任务目录。")
    return directory / "transcription.json"


def prepare_result(runtime: Runtime, path: Path) -> None:
    """独占创建JSON结果文件的保存目录。"""
    runtime.check_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=False)


def prepare_documents(runtime: Runtime, config: JobConfig) -> Path:
    """核对并创建或复用已确认的文档保存目录。"""
    base = Path(config["document_directory"])
    if (not base.is_absolute() or base.name != "documents"
            or base.parent.name != config["job_id"] or base.resolve() != base):
        raise SetupError("文档保存位置发生变化或不是已确认的任务目录。")
    runtime.check_output_path(base)
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_record(directory: Path, report: Mapping[str, object]) -> None:
    """原子保存本目录的执行或导出状态记录。"""
    write_json_atomic(directory / "status.json", report)
