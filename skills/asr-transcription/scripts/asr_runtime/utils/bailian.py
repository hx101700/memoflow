"""构造和执行BL命令，解析登录状态与脱敏错误。"""

import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, NotRequired, TypedDict, cast
from urllib.parse import parse_qs, urlsplit

from .. import BAILIAN_VERSION
from ..models import ErrorReport, JobConfig
from .auth import bailian_environment
from .environment import Runtime, SetupError, check_login_execution_context, find_node, run_process

BEIJING_BASE_URL = "https://dashscope.aliyuncs.com"
WAIT_SECONDS = 3600
PROCESS_SECONDS = WAIT_SECONDS + 300


class _CodeExplanation(TypedDict):
    """描述已核对官方来源的错误含义。"""

    meaning: str
    source_url: NotRequired[str]


class _ErrorCatalog(TypedDict):
    """描述随Skill发布的错误说明字典。"""

    cli_exit_codes: dict[str, _CodeExplanation]
    api_codes: dict[str, _CodeExplanation]
    cli_source: str
    api_source: str


def installed_bl_version(runtime: Runtime) -> str | None:
    """读取工作区BL包的版本；未安装时返回None。"""
    path = runtime.path(".tools/bailian/node_modules/bailian-cli/package.json")
    if not path.is_file():
        return None
    try:
        version = json.loads(path.read_text(encoding="utf-8"))["version"]
        if not isinstance(version, str) or not version:
            raise ValueError("invalid version")
        return version
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SetupError("工作区BL包信息损坏，请检查安装目录。") from exc


def _node_command(runtime: Runtime, arguments: list[str]) -> list[str]:
    """组合Node入口、固定BL参数与登录开页适配。"""
    # --quiet是已核实的禁止命令结束后自动全局升级的路径；不猜造环境开关。
    command = [str(find_node())]
    if os.name == "nt" and arguments[:2] == ["auth", "login"] and "--console" in arguments:
        command.extend(["--require", str(runtime.resource("scripts/bailian/console-browser.cjs"))])
    return [*command, str(runtime.bl_entry), *arguments, "--quiet"]


def bl_command(runtime: Runtime, arguments: list[str]) -> list[str]:
    """核对工作区BL版本并构造Node启动参数。"""
    if installed_bl_version(runtime) != BAILIAN_VERSION or not runtime.bl_entry.is_file():
        raise SetupError(f"需要工作区BL {BAILIAN_VERSION}，请先运行bootstrap。")
    return _node_command(runtime, arguments)


def check_recognition_command(runtime: Runtime, arguments: list[str]) -> None:
    """按实际Node入口检查待交接识别命令的Windows长度。"""
    check_command_length(_node_command(runtime, arguments))


def verify_bl_installation(runtime: Runtime) -> None:
    """启动BL版本入口，确认包信息与可运行安装一致。"""
    # 包信息可能先于依赖写入；真正启动入口才能发现中断安装留下的缺依赖。
    result = run_process(runtime, bl_command(runtime, ["--version"]), isolated_config=True)
    if result.returncode or result.stdout.strip() != f"bl {BAILIAN_VERSION}":
        raise SetupError("BL入口无法按锁定版本启动，安装可能不完整；未自动重装。")


def recognition_arguments(config: JobConfig, audio_path: Path, json_path: Path) -> list[str]:
    """将已确认的识别选项映射为BL命令参数。"""
    arguments = [
        "speech", "recognize", "--config", "default", "--model", config["model"], "--url", str(audio_path),
        "--base-url", BEIJING_BASE_URL, "--out", str(json_path),
        "--timeout", str(WAIT_SECONDS), "--poll-interval", "5", "--output", "json",
    ]
    if config["diarization_enabled"]:
        arguments.append("--diarization")
    options = config["recognition_options"]
    if options["language_hints"]:
        arguments.extend(["--language", options["language_hints"][0]])
    if options["speaker_count"] is not None:
        arguments.extend(["--speaker-count", str(options["speaker_count"])])
    enhancement = config["enhancement"]
    if enhancement["hotwords"] is not None:
        arguments.extend([
            "--vocabulary", json.dumps(enhancement["hotwords"]["vocabulary"],
                                       ensure_ascii=False, separators=(",", ":")),
        ])
    if enhancement["context"] is not None:
        # 绑定选项和值，使以--开头的原文也按上下文解析。
        arguments.append("--context=" + enhancement["context"])
    return arguments


@dataclass(frozen=True)
class PreparedCommand:
    """保存准备好的BL命令参数与子进程环境。"""

    argv: tuple[str, ...] = field(repr=False)
    env: dict[str, str] = field(repr=False)


def prepare_command(runtime: Runtime, arguments: list[str], auth_mode: str) -> PreparedCommand:
    """准备BL参数和凭据环境，并检查Windows命令长度。"""
    argv = bl_command(runtime, arguments)
    check_command_length(argv)
    return PreparedCommand(tuple(argv), bailian_environment(runtime, auth_mode))


class BailianFailure(Exception):
    def __init__(self, report: ErrorReport, *, started: bool) -> None:
        """保存脱敏错误报告与BL进程启动状态。"""
        super().__init__(report["explanation"])
        self.report = report
        self.started = started


def check_command_length(argv: list[str]) -> None:
    """检查完整命令的Windows长度是否在系统上限内。"""
    # CreateProcessW的32767限制包含终止NUL；按Python实际Windows引号规则计算。
    length = len(subprocess.list2cmdline(argv).encode("utf-16-le")) // 2 + 1
    if length > 32767:
        raise SetupError(
            "识别命令共{length}个UTF-16单元，超过Windows的32767上限。"
            "请减少热词或缩短路径后重新配置；未截断热词、未启动BL。", length=length,
        )


def redact_message(value: str, private_values: list[str]) -> str:
    """隐藏私有参数、URL和常见凭据，再限制可展示错误的长度。"""
    for private in sorted(set(private_values), key=len, reverse=True):
        if private:
            value = value.replace(private, "[已隐藏]")
    value = re.sub(r"(?:https?|oss)://[^\s\"<>]+", "[URL已隐藏]", value)
    value = re.sub(r"\b(?:sk-[A-Za-z0-9._-]+|LTAI[A-Za-z0-9]+)\b", "[凭据已隐藏]", value)
    value = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [已隐藏]", value)
    return " ".join(value.split())[:800]


def explain_cli_error(returncode: int, stderr: str, private_values: list[str]) -> ErrorReport:
    """解析BL结构化错误，并附上脱敏信息与官方错误说明。"""
    catalog = cast(_ErrorCatalog, json.loads((Path(__file__).parent.parent / "error_catalog.json").read_text(encoding="utf-8")))
    try:
        error = json.loads(stderr)["error"]
        if not isinstance(error, dict):
            error = {}
    except (ValueError, KeyError, TypeError):
        error = {}
    api_code = error.get("api_code")
    if not isinstance(api_code, str):
        api_code = None
    request_id = error.get("request_id")
    if not isinstance(request_id, str):
        request_id = None
    http_status = error.get("http_status")
    if type(http_status) is not int:
        http_status = None
    cli = catalog["cli_exit_codes"].get(str(returncode))
    api = catalog["api_codes"].get(api_code or "")
    explanation = cli["meaning"] if cli else "BL返回未收录的进程退出码。"
    source = catalog["cli_source"] if cli else None
    if api:
        explanation = api["meaning"]
        source = api.get("source_url", catalog["api_source"])
    elif api_code:
        explanation += " 当前官方字典未收录此API错误码，不能据此推断具体原因。"
    message = error.get("message")
    return {
        "source": "cli", "cli_exit_code": returncode, "http_status": http_status,
        "code": redact_message(api_code, private_values) if api_code else None,
        "request_id": redact_message(request_id, private_values) if request_id else None,
        "message": redact_message(message, private_values) if isinstance(message, str) else "CLI未提供可解析的结构化错误信息。",
        "explanation": explanation, "source_url": source,
    }


def _open_login_url(url: str) -> None:
    """校验BL输出的官方登录URL，并交给系统浏览器打开。"""
    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, strict_parsing=True, keep_blank_values=True)
        notice = query.get("notice", [])
        callback = re.fullmatch(r"127\.0\.0\.1:(\d{1,5})\?state=[0-9a-f]{32}", notice[0]) if len(notice) == 1 else None
        valid = (parsed.scheme == "https" and parsed.netloc == "bailian.console.aliyun.com"
                 and parsed.path == "/console-login" and not parsed.fragment
                 and not any(character.isspace() for character in url)
                 and set(query) <= {"notice", "needapikey"}
                 and ("needapikey" not in query or query["needapikey"] == ["true"])
                 and callback is not None and 1 <= int(callback[1]) <= 65535)
    except ValueError:
        valid = False
    if not valid:
        raise SetupError("BL返回的登录链接不符合已核实的官方格式，本次登录已停止。")
    try:
        # 登录适配已将BL的开页动作交到此处，ShellExecute完整接收URL。
        os.startfile(url)
    except OSError as exc:
        raise SetupError("无法打开BL提供的完整登录页面，本次登录已停止，未重试。") from exc


def _communicate_login(process: subprocess.Popen[str], timeout: float | None) -> tuple[None, str]:
    """等待BL登录回调，同时读取完整链接和错误输出。"""
    # _run_bl在console_login路径固定创建两个文本管道。
    output = cast(IO[str], process.stdout)
    error_output = cast(IO[str], process.stderr)

    def read_links() -> None:
        """读取BL登录链接并向系统浏览器发出一次打开请求。"""
        opened = False
        try:
            with output:
                while line := output.readline():
                    line = line.strip()
                    if not opened and line.startswith(("https://", "http://")):
                        if process.poll() is not None:
                            raise SetupError("BL登录进程已结束，本次链接已不可继续使用；未重新发起登录。")
                        opened = True
                        _open_login_url(line)
        except (SetupError, OSError):
            if process.poll() is None:
                process.kill()
            raise

    try:
        with ThreadPoolExecutor(max_workers=2) as readers:
            links = readers.submit(read_links)
            errors = readers.submit(error_output.read)
            try:
                process.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise
            # 进程结束后管道得到EOF；线程回收完成后才返回，不遗留监听线程。
            links.result()
            return None, errors.result()
    finally:
        error_output.close()


def _run_bl(runtime: Runtime, command: PreparedCommand,
            private_values: list[str], *, timeout: float | None, capture_stdout: bool = False,
            console_login: bool = False) -> str:
    """执行BL命令并管理进程回收与错误报告。"""
    private_values = [*private_values, command.env.get("DASHSCOPE_API_KEY", "")]
    try:
        process = subprocess.Popen(
            command.argv, cwd=runtime.workspace, env=command.env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture_stdout or console_login else subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as exc:
        raise BailianFailure({"source": "local", "code": "LOCAL_PROCESS_START_FAILED",
                              "explanation": "无法启动BL进程，尚未执行云端操作。"}, started=False) from exc
    stdout: str | None
    stderr: str
    try:
        if console_login:
            stdout, stderr = _communicate_login(process, timeout)
        else:
            stdout, stderr = process.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError) as exc:
        if not console_login:
            process.kill()
            process.communicate()
        # 这里只说明进程中断；是否已提交识别，由调用用例解释。
        raise BailianFailure({"source": "local", "code": "LOCAL_WAIT_INTERRUPTED",
                              "explanation": "BL进程等待已中断，未自动重试。"},
                             started=True) from exc
    if process.returncode:
        raise BailianFailure(explain_cli_error(process.returncode, stderr, private_values), started=True)
    return stdout or ""


def run_recognition(runtime: Runtime, command: PreparedCommand,
                    private_values: list[str]) -> None:
    """调用BL完成识别流程及JSON保存。"""
    _run_bl(runtime, command, private_values, timeout=PROCESS_SECONDS)


def console_status(runtime: Runtime) -> dict[str, str | bool]:
    """查询并解释BL本地模型与控制台凭据状态。"""
    runtime.prepare()
    command = prepare_command(runtime, ["auth", "status", "--config", "default", "--output", "json"], "console")
    output = _run_bl(runtime, command, [], timeout=60, capture_stdout=True)
    try:
        status = json.loads(output)
        if not isinstance(status, dict):
            raise ValueError("invalid status")
    except ValueError as exc:
        raise SetupError("BL未返回可解析的本地登录状态。") from exc
    # authenticated也可能只代表控制台token/AK，识别必须存在模型API Key。
    configured = isinstance(status.get("api_key"), dict)
    console_configured = isinstance(status.get("console"), dict)
    if configured:
        message = "已配置当前工作区的模型凭据。"
    elif console_configured:
        message = "控制台凭据已保存，但未配置模型 API Key，暂时无法执行语音识别。请检查官方授权结果。"
    else:
        message = "当前工作区尚无模型凭据，请先运行login完成百炼控制台登录。"
    return {"mode": "console", "configured": configured, "console_configured": console_configured,
            "verified_online": False, "message": message}


def login_console(runtime: Runtime) -> dict[str, str | bool]:
    """发起官方控制台登录，并用BL本地状态确认凭据是否保存。"""
    check_login_execution_context()
    runtime.prepare()
    command = prepare_command(runtime, ["auth", "login", "--console", "--console-site", "domestic",
                                        "--config", "default", "--output", "json"], "console")
    print(json.dumps({"status": "WAITING_FOR_LOGIN", "message": "请在系统默认浏览器完成百炼授权，完成后回到Codex发送“已完成”。"}, ensure_ascii=False), flush=True)
    _run_bl(runtime, command, [], timeout=None, console_login=True)
    # BL登录空等超时也可能退出0，必须再核对公开的本地状态命令。
    return console_status(runtime)
