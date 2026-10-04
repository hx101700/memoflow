"""编排已确认任务的BL识别和本地文档导出。"""

import os
from datetime import datetime, timezone
from pathlib import Path

from .. import MODEL
from ..models import AudioInfo, AudioRecord, DeliveryReport, ExecutionReport, JobConfig, Transcript
from ..utils.bailian import BailianFailure, PreparedCommand, prepare_command, recognition_arguments, run_recognition
from ..utils.environment import Runtime, SetupError
from ..utils.files import FileError, file_fingerprint
from ..utils.job_files import (
    job_directory, read_config, read_execution, read_delivery, reserve_execution,
    result_path, prepare_result, save_record,
)
from ..utils.results import load_transcript
from ..utils.media import MediaError, convert_to_mono
from .delivery import export_documents
from .rules import ValidationError, check_audio_limits


def _save_status(directory: Path, report: ExecutionReport) -> bool:
    """保存执行记录，返回写入结果并将失败原因附入回执。"""
    report["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        save_record(directory, report)
    except (OSError, KeyboardInterrupt) as exc:
        report["record_error"] = {
            "source": "local", "code": "LOCAL_RECORD_SAVE_FAILED", "phase": "save_status",
            "attempted_status": report["status"], "error_type": type(exc).__name__,
            "explanation": "执行记录未保存，磁盘状态可能滞后；请保留本次回执，检查目录权限、空间或中断原因。",
        }
        return False
    return True


def job_status(runtime: Runtime, job_id: str) -> ExecutionReport:
    """查询任务的本地状态与最近一次交付结果。"""
    root = job_directory(runtime, job_id)
    report = read_execution(root)
    if report is None:
        read_config(runtime, job_id)
        return {"job_id": job_id, "status": "CONFIGURED", "execution_authorized": True,
                "message": "转写任务已确认，等待开始执行。"}
    if report["status"] == "OUTCOME_UNKNOWN":
        return report
    if report["status"] in ("PREPARING", "RUNNING"):
        report["message"] = "这是最近保存的执行状态，不代表进程仍存活。请检查原执行进程，勿重新提交。"
    delivery = read_delivery(root)
    if delivery is not None:
        if delivery["status"] == "EXPORTING":
            delivery["message"] = "这是最近保存的导出状态，不代表进程仍在运行。请检查原进程和已完成文件；不会自动重试。"
        _attach_delivery(report, delivery)
    return report


def _attach_delivery(report: ExecutionReport, delivery: DeliveryReport) -> ExecutionReport:
    """合并导出回执并更新文档就绪状态。"""
    report.update({"delivery": delivery, "documents_ready": delivery["status"] == "COMPLETE",
                   "message": delivery["message"]})
    return report


def _deliver(runtime: Runtime, config: JobConfig, transcript: Transcript, report: ExecutionReport) -> ExecutionReport:
    """生成任务文档，将交付结果合并到执行回执。"""
    try:
        delivery = export_documents(runtime, config, transcript)
    except (OSError, SetupError, KeyboardInterrupt) as exc:
        # 即使状态文件也无法写入，仍把已保存的JSON交给调用者，不能误报识别失败。
        delivery = {"status": "OUTCOME_UNKNOWN", "error_type": type(exc).__name__,
                    "message": "本地导出中断或记录无法保存。JSON及已生成文件已保留，请检查目录权限、空间和文件；未重新识别。"}
    return _attach_delivery(report, delivery)


def export_job(runtime: Runtime, job_id: str) -> ExecutionReport:
    """核对已保存的转写结果并更新任务文档。"""
    config = read_config(runtime, job_id)
    report = read_execution(job_directory(runtime, job_id))
    if report is None or report["status"] != "JSON_READY":
        raise SetupError("任务尚无通过检查的JSON，不能导出；不会自动重新识别。")
    try:
        expected = report["result"]["sha256"]
    except (KeyError, TypeError) as exc:
        raise SetupError("任务记录缺少结果JSON摘要，无法核对导出来源；未导出，也未重新识别。") from exc
    transcript = load_transcript(result_path(config))
    if transcript.sha256 != expected:
        raise SetupError("转写JSON在验收后发生变化，未导出；请先检查原结果。")
    return _deliver(runtime, config, transcript, report)


def _check_input(record: AudioRecord) -> Path:
    """核对用户原始音频的路径、大小和内容摘要，返回读取路径。"""
    path = Path(record["path"])
    if not path.is_absolute() or path.resolve() != path:
        raise SetupError("已确认的音频位置发生变化，请重新选择并确认新任务。")
    current = file_fingerprint(path)
    expected = record["fingerprint"]
    if (current["size_bytes"], current["sha256"]) != (expected["size_bytes"], expected["sha256"]):
        raise SetupError("交接后的输入文件已改变，请重新配置并确认新任务；未上传。")
    return path


def prepare_input(runtime: Runtime, config: JobConfig, execution: Path) -> tuple[PreparedCommand, list[str], Path]:
    """核对音频、准备识别命令与结果目录，并按需转换声道。"""
    audio_record = config["audio"]
    source = _check_input(audio_record)
    prepared = execution / "mono.flac" if audio_record["requires_mono"] else source
    destination = result_path(config)
    arguments = recognition_arguments(config, prepared, destination)
    enhancement = config["enhancement"]
    private = [str(source), audio_record.get("name", source.name)]
    hotwords = enhancement["hotwords"]
    if hotwords is not None:
        private.extend(hotwords["vocabulary"])
    context = enhancement["context"]
    if context is not None:
        private.append(context)
    command = prepare_command(runtime, arguments, config["auth_mode"])
    # 先拒绝不可启动的参数；通过后才做可能耗时的本地声道合并。
    if audio_record["requires_mono"]:
        converted = convert_to_mono(source, prepared, AudioInfo(**audio_record["metadata"]))
        check_audio_limits(converted, True)
    prepare_result(runtime, destination)
    return command, private, destination


def transcribe(runtime: Runtime, job_id: str) -> ExecutionReport:
    """按确认快照执行一次BL识别及本地导出，返回已知结果与失败阶段。"""
    config = read_config(runtime, job_id)
    if config["model"] != MODEL:
        raise SetupError(
            f"已确认任务的模型与当前固定模型{MODEL}不一致，请重新配置并确认新任务。"
            "未更改原配置、未占用执行，也未上传；已有结果仍可本地查看或重导。"
        )
    try:
        # 目录是一次执行的持久占用标记，成功、失败、崩溃后都不删除或自动重试。
        execution = reserve_execution(runtime, job_id)
    except FileExistsError:
        return job_status(runtime, job_id)
    report: ExecutionReport = {"job_id": job_id, "status": "PREPARING", "execution_authorized": True,
              "authorization_source": "session_handoff", "cloud_outcome": "not_started",
              "started_at": datetime.now(timezone.utc).isoformat(),
              "executor_pid": os.getpid(), "documents_ready": False}
    if not _save_status(execution, report):
        report.update({"status": "STOPPED", "message": "执行记录未保存，BL尚未启动，音频未上传；未自动重试。"})
        return report
    phase = "prepare_input"
    try:
        runtime.prepare()
        command, private, destination = prepare_input(runtime, config, execution)
        report["json_path"] = str(destination)
        # 先记录保守的RUNNING，防止进程启动后崩溃却留下“尚未上传”的记录。
        report.update({"status": "RUNNING", "cloud_outcome": "unknown", "message": "BL正在执行上传、识别、等待及结果保存。"})
        if not _save_status(execution, report):
            report.update({"status": "STOPPED", "cloud_outcome": "not_started",
                           "message": "执行记录未保存，BL尚未启动，音频未上传；未自动重试。"})
            return report
        phase = "run_bl"
        run_recognition(runtime, command, private)
        phase = "read_result"
        transcript = load_transcript(destination)
        result = transcript.summary()
        report.update({"status": "JSON_READY", "cloud_outcome": "result_received", "result": result,
                       "message": "BL已结束，转写JSON已保存并通过结构检查；等待本地导出。"})
    except BailianFailure as exc:
        outcome = "unknown" if report["status"] == "RUNNING" and exc.started else "not_started"
        message = ("BL执行已停止，云端结果未知；未自动重试，也未取消云端任务。" if outcome == "unknown"
                   else "BL识别尚未启动，音频未上传；未自动重试。")
        report.update({"status": "STOPPED", "cloud_outcome": outcome,
                       "error": {**exc.report, "phase": phase}, "message": message})
    except (Exception, KeyboardInterrupt) as exc:
        # 自有异常只含可公开说明；第三方或程序异常可能带正文，只报告类型和阶段。
        if isinstance(exc, (SetupError, ValidationError, MediaError, FileError)):
            message = str(exc)
        elif isinstance(exc, KeyboardInterrupt):
            message = "本机操作已中断；未自动重试。请依据cloud_outcome判断已知执行范围。"
        elif isinstance(exc, OSError):
            message = "本地文件操作失败，请检查文件是否存在、目录权限、磁盘空间及文件占用。"
        else:
            message = f"转写程序发生异常，类型：{type(exc).__name__}；未自动重试，请联系开发者检查。"
        report.update({"status": "STOPPED", "message": message,
                       "error": {"source": "local", "code": "LOCAL_EXECUTION_STOPPED", "phase": phase,
                                 "error_type": type(exc).__name__, "explanation": message}})
    if not _save_status(execution, report):
        if report["status"] == "JSON_READY":
            report["message"] = "转写JSON已保存并通过检查，但执行记录未保存；本次未生成文档，请保留本回执及JSON，勿重新识别。"
        else:
            report["message"] += " 执行记录也未保存，请保留本次回执。"
        return report
    if report["status"] == "JSON_READY":
        # 云端成功先独立落盘。导出失败不得改写为识别失败或触发第二次BL执行。
        return _deliver(runtime, config, transcript, report)
    return report
