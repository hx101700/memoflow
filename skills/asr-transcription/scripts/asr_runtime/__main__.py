"""本地配置、明确授权的BL转写，以及仅查看本地执行记录的入口。"""

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from pathlib import Path

from .application.bootstrap import bootstrap
from .application.diagnostics import doctor
from .utils.auth import api_key_status
from .utils.environment import Runtime, SetupError, python_temporary_directory
from .utils.bailian import BailianFailure, console_status, login_console


def main(argv: list[str] | None = None) -> int:
    """在指定工作区分派Skill命令，输出JSON回执与进程退出码。"""
    # Windows重定向输出时也保持UTF-8，使Codex和JSON解析器正确读取中文。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="asr-transcription录音转写工具；转写须明确授权上传。")
    parser.add_argument("--workspace", type=Path, required=True, help="保存运行环境与结果的现有工作文件夹")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "bootstrap", "api-key-status", "console-status", "login"):
        commands.add_parser(name)
    serve_parser = commands.add_parser("serve", help="打开本地配置网页")
    serve_parser.add_argument("--port", type=int, default=0, help="本地网页端口，默认自动选择")
    serve_parser.add_argument("--no-browser", action="store_true", help="不自动打开系统浏览器")
    for name in ("confirm", "cancel"):
        command = commands.add_parser(name)
        command.add_argument("--session", required=True, help="用户从预览页复制到对话中的编辑会话编号")
    for name in ("transcribe", "export", "job-status"):
        command = commands.add_parser(name)
        command.add_argument("--job", required=True, help="会话交接回执中的任务编号")
    args = parser.parse_args(argv)
    report: Mapping[str, object]
    try:
        runtime = Runtime(args.workspace, Path(__file__).resolve().parents[2])
        with python_temporary_directory(runtime) if args.command in ("serve", "transcribe", "export") else nullcontext():
            if args.command == "serve":
                from .web import serve
                serve(runtime, port=args.port, open_browser=not args.no_browser)
                return 0
            if args.command in ("confirm", "cancel"):
                from .web import control_session
                report = control_session(runtime, args.session, args.command)
            elif args.command == "transcribe":
                from .application.transcription import transcribe
                report = transcribe(runtime, args.job)
            elif args.command == "export":
                from .application.transcription import export_job
                report = export_job(runtime, args.job)
            elif args.command == "job-status":
                from .application.transcription import job_status
                report = job_status(runtime, args.job)
            else:
                actions: dict[str, Callable[[Runtime], Mapping[str, object]]] = {
                    "doctor": doctor, "bootstrap": bootstrap, "api-key-status": api_key_status,
                    "console-status": console_status, "login": login_console,
                }
                report = actions[args.command](runtime)
    except BailianFailure as exc:
        print(json.dumps({"status": "STOPPED", "error": exc.report}, ensure_ascii=False))
        return 1
    except (SetupError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "failed", "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if (report.get("issues") or report.get("configured") is False
                 or report.get("status") in ("STOPPED", "OUTCOME_UNKNOWN")
                 or (report.get("status") == "JSON_READY" and not report.get("documents_ready"))) else 0


if __name__ == "__main__":
    raise SystemExit(main())
