"""管理Skill资源、工作区运行路径和子进程环境。"""

import json
import ctypes
from collections.abc import Iterator
from contextlib import contextmanager
from ctypes import wintypes
import os
import re
import subprocess
import sys
import sysconfig
import tempfile
from dataclasses import dataclass
from pathlib import Path
from .i18n import translate


class SetupError(Exception):
    """表示可向用户解释的环境配置错误。"""

    def __init__(self, message: str, **params: object) -> None:
        """保留错误模板供网页翻译，并提供当前语言的异常说明。"""
        super().__init__(translate(message, **params))
        self.template = message
        self.params = params


def process_is_running(pid: int) -> bool | None:
    """查询Windows进程是否存活，权限不足或状态未知时返回None。"""
    if os.name != "nt" or type(pid) is not int or not 0 < pid <= 0xFFFFFFFF:
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    synchronize = 0x00100000
    handle = kernel.OpenProcess(synchronize, False, pid)
    if not handle:
        return False if ctypes.get_last_error() == 87 else None  # ERROR_INVALID_PARAMETER
    try:
        state = kernel.WaitForSingleObject(handle, 0)
        if state == 0x00000102:  # WAIT_TIMEOUT：进程仍在运行。
            return True
        if state == 0:  # WAIT_OBJECT_0：进程已结束。
            return False
        return None
    finally:
        kernel.CloseHandle(handle)


def check_login_execution_context() -> None:
    """拒绝在Windows受限令牌中启动浏览器登录。"""
    if os.name != "nt":
        return
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    security.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    security.OpenProcessToken.restype = wintypes.BOOL
    security.IsTokenRestricted.argtypes = [wintypes.HANDLE]
    security.IsTokenRestricted.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    token = wintypes.HANDLE()
    token_query = 0x0008
    if not security.OpenProcessToken(kernel.GetCurrentProcess(), token_query, ctypes.byref(token)):
        raise SetupError("无法读取Windows进程权限，未启动登录。")
    try:
        ctypes.set_last_error(0)
        restricted = security.IsTokenRestricted(token)
        if not restricted and ctypes.get_last_error():
            raise SetupError("无法读取Windows进程权限，未启动登录。")
        if restricted:
            raise SetupError("浏览器登录需要正常Windows桌面执行权限；请通过执行工具的权限机制重新运行login（Codex使用require_escalated）。本次未启动BL或浏览器。")
    finally:
        kernel.CloseHandle(token)


@dataclass(frozen=True)
class Runtime:
    workspace: Path
    skill_root: Path

    def __post_init__(self) -> None:
        """规范化工作区与Skill目录，并确认运行数据位于Skill外。"""
        try:
            workspace = self.workspace.resolve(strict=True)
            skill_root = self.skill_root.resolve(strict=True)
        except OSError as exc:
            raise SetupError("工作区或Skill目录不存在，或无法访问。") from exc
        if not workspace.is_dir() or not skill_root.is_dir():
            raise SetupError("工作区与Skill位置必须是已有文件夹。")
        if workspace.is_relative_to(skill_root):
            raise SetupError("请选择Skill安装目录之外的工作区保存运行数据与转写结果。")
        object.__setattr__(self, "workspace", workspace)
        object.__setattr__(self, "skill_root", skill_root)
        # 立即解析一次运行根，先拒绝会写入Skill的目录布局。
        self.root

    @property
    def root(self) -> Path:
        """返回工作区内的私有运行目录。"""
        root = (self.workspace / ".asr-transcription").resolve()
        if not root.is_relative_to(self.workspace):
            raise SetupError("私有运行目录指向工作区外，请检查.asr-transcription。")
        if root.is_relative_to(self.skill_root) or self.skill_root.is_relative_to(root):
            raise SetupError("私有运行目录与Skill安装目录重叠，请选择其他工作区。")
        return root

    def path(self, relative: str) -> Path:
        """解析私有运行路径并检查其位于运行目录内。"""
        root = self.root
        path = (root / relative).resolve()
        # Windows junction / 符号链接不能把凭据和临时文件引向运行目录外。
        if not path.is_relative_to(root):
            raise SetupError("运行路径指向私有目录外：{relative}", relative=relative)
        return path

    def resource(self, relative: str) -> Path:
        """解析Skill资源路径并检查其位于安装目录内。"""
        path = (self.skill_root / relative).resolve()
        if not path.is_relative_to(self.skill_root):
            raise SetupError("资源路径指向Skill目录外：{relative}", relative=relative)
        return path

    def check_output_path(self, path: Path) -> None:
        """检查输出目标位于Skill资源目录之外。"""
        if path.resolve().is_relative_to(self.skill_root):
            raise SetupError("Skill安装目录用于保存程序资源，请选择其他位置保存转写结果。")

    @property
    def output_root(self) -> Path:
        """返回工作区内的默认转写保存目录。"""
        return self.workspace / "transcriptions"

    @property
    def base_python(self) -> Path:
        """返回工作区独立Python解释器的入口。"""
        return self.path(".tools/python/python.exe")

    @property
    def node_entry(self) -> Path:
        """返回工作区独立Node.js的入口。"""
        return self.path(".tools/node/node.exe")

    @property
    def bl_directory(self) -> Path:
        """返回当前工作区独立安装BL的位置。"""
        return self.path(".tools/bailian")

    @property
    def bl_entry(self) -> Path:
        """返回当前工作区BL的Node入口路径。"""
        return self.path(".tools/bailian/node_modules/bailian-cli/dist/bailian.mjs")

    def prepare(self) -> None:
        """创建私有运行目录和独立的npm空配置。"""
        for relative in (".runtime/tmp", ".runtime/npm-cache", ".state/bailian"):
            self.path(relative).mkdir(parents=True, exist_ok=True)
        for name in ("npm-user.npmrc", "npm-global.npmrc"):
            path = self.path(f".runtime/{name}")
            # 自有空配置阻止 npm 读取用户已有的 registry/token 设置。
            if path.exists() and path.read_text(encoding="utf-8").strip():
                raise SetupError(f"隔离配置应为空，请检查：{path}")
            path.touch(exist_ok=True)


@contextmanager
def python_temporary_directory(runtime: Runtime) -> Iterator[None]:
    """将当前Python进程的库临时文件集中到工作区并在退出时清理。"""
    base = runtime.path(".runtime/tmp")
    base.mkdir(parents=True, exist_ok=True)
    previous = tempfile.tempdir
    with tempfile.TemporaryDirectory(
        prefix=f"python-{os.getpid()}-", dir=base, ignore_cleanup_errors=True,
    ) as directory:
        tempfile.tempdir = directory
        try:
            yield
        finally:
            tempfile.tempdir = previous


def child_environment(runtime: Runtime, *, isolated_config: bool = False) -> dict[str, str]:
    """构造子进程环境，并选择工作区凭据或独立检查配置。"""
    allowed = {"PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "PROCESSOR_ARCHITECTURE"}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    inherited_path = os.environ.get("PATH", "")
    temp = str(runtime.path(".runtime/tmp"))
    env.update({
        "PATH": os.pathsep.join(filter(None, (str(runtime.node_entry.parent), inherited_path))),
        "TEMP": temp,
        "TMP": temp,
        "TMPDIR": temp,
        "BAILIAN_CONFIG_DIR": str(runtime.path(".state/bailian-check" if isolated_config else ".state/bailian")),
        "DO_NOT_TRACK": "1",
        "NO_COLOR": "1",
        "NPM_CONFIG_USERCONFIG": str(runtime.path(".runtime/npm-user.npmrc")),
        "NPM_CONFIG_GLOBALCONFIG": str(runtime.path(".runtime/npm-global.npmrc")),
        "NPM_CONFIG_CACHE": str(runtime.path(".runtime/npm-cache")),
        "NPM_CONFIG_PREFIX": str(runtime.bl_directory),
        "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org/",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_FUND": "false",
        # 已审阅BL的postinstall只预下载推荐器Wiki，ASR不需要该技能资产。
        "NPM_CONFIG_IGNORE_SCRIPTS": "true",
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONNOUSERSITE": "1",
    })
    return env


def find_node(runtime: Runtime) -> Path:
    """定位工作区Node，缺失时提示运行首次安装入口。"""
    node = runtime.node_entry
    if not node.is_file():
        raise SetupError("工作区Node.js尚未安装，请运行Skill的scripts/bootstrap.ps1。")
    return node


def check_python() -> None:
    """确认当前Python符合依赖锁的Windows x64 CPython 3.12要求。"""
    # requirements锁定的是此平台的二进制wheel，不把更高版本误报为支持。
    if (sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 12)
            or sysconfig.get_platform() != "win-amd64"):
        raise SetupError("当前依赖锁需要Windows x64的CPython 3.12。")


def npm_entry(node: Path) -> Path:
    """定位与Node配套的npm入口脚本。"""
    path = node.parent / "node_modules/npm/bin/npm-cli.js"
    if not path.is_file():
        raise SetupError("工作区Node.js缺少配套npm，请运行Skill的scripts/bootstrap.ps1检查安装。")
    return path


def stop_process_tree(process: subprocess.Popen[str]) -> None:
    """结束本次命令及其Windows子进程，并等待退出。"""
    if process.poll() is not None:
        return
    if os.name == "nt":
        # Windows venv有启动器和实际Python两层，中断时需共同结束。
        stopped = subprocess.run(
            [str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"),
             "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            shell=False, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if stopped.returncode:
            raise SetupError(f"无法结束本机进程树（PID {process.pid}，退出码 {stopped.returncode}），请检查仍在运行的命令。")
    else:
        process.kill()
    process.wait()


def run_process(
    runtime: Runtime, argv: list[str], timeout: float = 60, *, isolated_config: bool = False,
) -> subprocess.CompletedProcess[str]:
    """在工作区执行本机命令，返回捕获的进程输出。"""
    try:
        process = subprocess.Popen(
            argv,
            cwd=runtime.workspace,
            env=child_environment(runtime, isolated_config=isolated_config),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as exc:
        raise SetupError(f"无法启动子进程：{type(exc).__name__}") from exc
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired as exc:
        raise SetupError("子进程等待超时，已停止，未自动重试。") from exc
    except OSError as exc:
        raise SetupError(f"子进程输出读取失败：{type(exc).__name__}") from exc
    finally:
        try:
            stop_process_tree(process)
        finally:
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


def check_node(runtime: Runtime) -> tuple[Path, str]:
    """运行Node版本检查，返回满足BL要求的入口与版本。"""
    node = find_node(runtime)
    result = run_process(runtime, [str(node), "--version"])
    version = result.stdout.strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    if result.returncode or not match or tuple(map(int, match.groups())) < (18, 17, 0):
        raise SetupError("Node.js版本不满足BL要求：需要18.17.0或更高版本。")
    return node, version


def locked_python_versions(runtime: Runtime) -> dict[str, str]:
    """读取依赖锁中的精确版本，并核对版本与SHA256格式。"""
    try:
        lines = runtime.resource("scripts/requirements.txt").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SetupError("无法读取Python依赖锁文件requirements.txt。") from exc
    versions = {}
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)(?:\s+--hash=sha256:[0-9a-f]{64})+", line)
        if not match or match[1] in versions:
            raise SetupError(f"requirements.txt第{number}行不是唯一的锁定依赖，请检查。")
        versions[match[1]] = match[2]
    if not versions:
        raise SetupError("requirements.txt没有锁定依赖，停止检查/安装。")
    return versions


def installed_python_versions(runtime: Runtime, packages: dict[str, str]) -> dict[str, str] | None:
    """加载工作区venv依赖并返回版本，加载失败时返回None。"""
    python = runtime.path(".venv/Scripts/python.exe")
    if not python.is_file():
        return None
    result = run_process(runtime, [str(python), "-I", "-c",
        "import av, dotenv, openpyxl, et_xmlfile, defusedxml, docx, lxml.etree, typing_extensions; "
        "import importlib.metadata as m, json, sys; "
        "print(json.dumps({name:m.version(name) for name in sys.argv[1:]}))", *packages])
    if result.returncode:
        return None
    try:
        versions = json.loads(result.stdout)
        if not isinstance(versions, dict) or set(versions) != set(packages):
            raise ValueError("invalid package report")
        if not all(isinstance(version, str) for version in versions.values()):
            raise ValueError("invalid package version")
    except ValueError as exc:
        raise SetupError("Python依赖检查返回异常，未自动安装或重试。") from exc
    return versions
