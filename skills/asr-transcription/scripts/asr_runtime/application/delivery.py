"""向转写任务的固定目录导出三种格式的校对稿并记录交付结果。"""

from ..utils.documents import DocumentError, publish_document, write_docx, write_markdown, write_xlsx
from ..utils.environment import Runtime, SetupError
from ..utils.job_files import job_directory, prepare_documents, prepare_delivery, save_record
from ..models import DeliveryReport, JobConfig, Transcript


def export_documents(runtime: Runtime, config: JobConfig, transcript: Transcript) -> DeliveryReport:
    """生成并替换转写任务的 Excel、Word 和 Markdown 校对稿，汇总交付结果。"""
    state = prepare_delivery(job_directory(runtime, config["job_id"]))
    report: DeliveryReport = {"job_id": config["job_id"], "status": "EXPORTING",
              "files": {}, "message": "正在本机生成校对稿。"}
    save_record(state, report)
    try:
        destination = prepare_documents(runtime, config)
    except (OSError, SetupError, KeyError, TypeError) as exc:
        message = (str(exc) + "JSON已保留。" if isinstance(exc, SetupError)
                   else "无法创建文档目录，请检查已确认的保存位置、权限和磁盘空间；JSON已保留。")
        report.update({"status": "FAILED", "message": message,
                       "error_type": type(exc).__name__})
        save_record(state, report)
        return report

    # 格式之间没有成功依赖；某一项失败后仍可完成其余格式，但不重试失败项。
    for extension, writer in (("xlsx", write_xlsx), ("docx", write_docx), ("md", write_markdown)):
        final = destination / f"transcription.{extension}"
        try:
            size = publish_document(writer, transcript, final, source_name=config["audio"]["name"],
                                    job_id=config["job_id"], model=config["model"])
            report["files"][extension] = {"status": "READY", "path": str(final),
                                          "bytes": size}
        except Exception as exc:
            # 第三方序列化器可能在异常中携带正文。仅公开自有错误说明及异常类型。
            if isinstance(exc, DocumentError):
                message = str(exc)
            elif isinstance(exc, OSError):
                message = "文件保存失败，请检查目录权限、磁盘空间及文件占用；未自动重试。"
            else:
                message = f"导出程序发生异常，类型：{type(exc).__name__}；未自动重试，请联系开发者检查。"
            report["files"][extension] = {"status": "FAILED", "message": message,
                                          "error_type": type(exc).__name__}
        save_record(state, report)
    ready = sum(item["status"] == "READY" for item in report["files"].values())
    report.update({"status": "COMPLETE" if ready == 3 else "PARTIAL" if ready else "FAILED",
                   "message": "Excel、Word和Markdown校对稿已保存，Excel和Word已回读核验。" if ready == 3 else "部分或全部校对稿未完成；JSON及已完成文件已保留，未自动重试。"})
    save_record(state, report)
    return report
