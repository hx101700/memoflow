"""生成转写原稿或所选目录中的人工校对稿，返回当次导出结果。"""

from pathlib import Path

from ..utils.documents import DocumentError, publish_document, write_docx, write_markdown, write_xlsx
from ..utils.environment import Runtime, SetupError
from ..utils.job_files import prepare_documents
from ..models import DeliveryReport, JobConfig, Transcript


def export_documents(runtime: Runtime, config: JobConfig, transcript: Transcript, *,
                     review_directory: Path | None = None) -> DeliveryReport:
    """生成并替换转写任务的 Excel、Word 和 Markdown 校对稿，汇总交付结果。"""
    report: DeliveryReport = {"job_id": config["job_id"], "status": "FAILED",
              "files": {}, "message": "本次校对稿尚未生成。"}
    try:
        if review_directory is None:
            destination = prepare_documents(runtime, config)
        else:
            if review_directory.resolve() != review_directory or not review_directory.is_dir():
                raise SetupError("所选校对稿目录不可用，请重新选择保存位置。")
            destination = review_directory
            runtime.check_output_path(destination)
    except (OSError, SetupError, KeyError, TypeError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            message = "本次导出已中断，原始数据保留；未生成文件，也未自动重试。"
        elif isinstance(exc, SetupError):
            message = str(exc) + "JSON已保留。"
        else:
            message = "无法创建文档目录，请检查已确认的保存位置、权限和磁盘空间；JSON已保留。"
        report.update({"status": "FAILED", "message": message,
                       "error_type": type(exc).__name__})
        return report

    name = "transcription"
    if review_directory is not None:
        # 为Windows文件名中的任务编号、扩展名及发布暂存后缀预留空间。
        source_stem = Path(config["audio"]["name"]).stem[:80]
        name = f"{source_stem}-reviewed-{config['job_id']}"
    # 格式之间没有成功依赖；某一项失败后仍可完成其余格式，但不重试失败项。
    for extension, writer in (("xlsx", write_xlsx), ("docx", write_docx), ("md", write_markdown)):
        final = destination / f"{name}.{extension}"
        try:
            size = publish_document(writer, transcript, final, source_name=config["audio"]["name"],
                                    job_id=config["job_id"], model=config["model"])
            report["files"][extension] = {"status": "READY", "path": str(final),
                                          "bytes": size}
        except (Exception, KeyboardInterrupt) as exc:
            # 第三方序列化器可能在异常中携带正文。仅公开自有错误说明及异常类型。
            if isinstance(exc, KeyboardInterrupt):
                message = "本次导出已中断，已生成文件和原始数据保留；未自动重试。"
            elif isinstance(exc, DocumentError):
                message = str(exc)
            elif isinstance(exc, OSError):
                message = "文件保存失败，请检查目录权限、磁盘空间及文件占用；未自动重试。"
            else:
                message = f"导出程序发生异常，类型：{type(exc).__name__}；未自动重试，请联系开发者检查。"
            report["files"][extension] = {"status": "FAILED", "message": message,
                                          "error_type": type(exc).__name__}
            if isinstance(exc, KeyboardInterrupt):
                break
    ready = sum(item["status"] == "READY" for item in report["files"].values())
    report.update({"status": "COMPLETE" if ready == 3 else "PARTIAL" if ready else "FAILED",
                   "message": "Excel、Word和Markdown校对稿已保存，Excel和Word已回读核验。" if ready == 3 else "部分或全部校对稿未完成；JSON及已完成文件已保留，未自动重试。"})
    return report
