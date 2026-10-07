"""用工作区Python、Node和pip/npm准备运行依赖。"""

import json
import locale
import shutil
import sys
import tempfile
import venv
from pathlib import Path
from typing import TextIO, cast

from .. import BAILIAN_VERSION
from ..utils.bailian import installed_bl_version, verify_bl_installation
from ..utils.environment import (
    Runtime,
    SetupError,
    check_node,
    check_python,
    installed_python_versions,
    locked_python_versions,
    npm_entry,
    run_process,
)
from ..utils.installation import (
    PIP_SHA256, PIP_VERSION, PIP_WHEEL_PATH, PythonIndex,
    rank_npm_registries, rank_python_indexes, run_installer,
)

_NPM_DOWNLOAD_ERRORS = {
    "ECONNRESET", "ECONNREFUSED", "ETIMEDOUT", "EIDLETIMEOUT", "EAI_AGAIN", "ENOTFOUND",
    "ENETUNREACH", "EHOSTUNREACH", "FETCH_ERROR", "EINTEGRITY", "E404", "E408", "E429",
}


def _install_bailian(runtime: Runtime, node: Path, npm: Path) -> None:
    """按测速顺序用npm安装锁定BL，仅下载类失败时切换另一个来源。"""
    print("正在比较npm官方源与npmmirror的文件下载速度。", file=sys.stderr, flush=True)
    registries = rank_npm_registries()
    log_path = runtime.path(".runtime/bootstrap.log")
    with log_path.open("w", encoding="utf-8") as log:
        for registry in registries:
            message = f"正在从{registry}安装百炼 CLI（BL）。"
            print(message, file=sys.stderr, flush=True)
            log.write(f"\n{message}\n")
            arguments = [str(node), str(npm), "ci", "--prefix", str(runtime.bl_directory),
                         "--registry", registry, "--ignore-scripts", "--no-audit", "--no-fund",
                         "--fetch-retries=2", "--prefer-offline", "--json", "--loglevel=http"]
            # npm将结构化结果写stdout，stderr继续提供实时进度；临时结果随上下文关闭。
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8", dir=runtime.path(".runtime/tmp")) as output:
                if run_installer(runtime, arguments, log, stdout_file=cast(TextIO, output)) == 0:
                    return
                output.seek(0)
                try:
                    code = json.load(output)["error"]["code"]
                except (ValueError, KeyError, TypeError):
                    code = None
            if not isinstance(code, str) or not (code in _NPM_DOWNLOAD_ERRORS or
                    len(code) == 4 and code.startswith("E5") and code[1:].isdigit()):
                raise SetupError(f"npm安装失败（{code if isinstance(code, str) else '未提供错误码'}）；本地日志：{log_path}")
            message = f"当前npm来源下载失败（{code}）。"
            print(message, file=sys.stderr, flush=True)
            log.write(message + "\n")
    raise SetupError(f"百炼 CLI（BL）安装失败，已尝试两个来源；本机日志：{log_path}")


def _download_python_packages(
    runtime: Runtime, indexes: list[PythonIndex], log: TextIO, *, installer: bool,
) -> None:
    """按测速顺序下载锁定包，每个来源最多启动一次pip下载。"""
    label = "pip安装工具" if installer else "Python依赖"
    for index in indexes:
        message = f"正在从{index.name}下载{label}。"
        print(message, file=sys.stderr, flush=True)
        log.write(f"\n{message}\n")
        arguments = [str(runtime.path(".venv/Scripts/python.exe")), "-I", "-X", "utf8", "-m", "pip",
                     "download", "--require-hashes", "--only-binary=:all:", "--no-cache-dir",
                     "--retries", "2", "--timeout", "120",
                     "--dest", str(runtime.path(".runtime/wheels"))]
        if installer:
            # 此时运行的是ensurepip提供的版本，只使用其已有公开参数。
            arguments += ["--no-index", "--no-deps", "--progress-bar", "on",
                          index.wheel_base_url + PIP_WHEEL_PATH + "#sha256=" + PIP_SHA256]
        else:
            arguments += ["--resume-retries", "5", "--progress-bar", "raw",
                          "--index-url", index.index_url,
                          "-r", str(runtime.resource("scripts/requirements.txt"))]
        if run_installer(runtime, arguments, log) == 0:
            return
    raise SetupError(f"{label}下载失败，已尝试两个来源；本地日志：{log.name}")


def _install_python_dependencies(runtime: Runtime) -> None:
    """选择下载来源、准备支持续传的pip并从本机wheel安装依赖。"""
    python = str(runtime.path(".venv/Scripts/python.exe"))
    # -I忽略PYTHONUTF8，显式选项保证安装输出与UTF-8日志解码一致。
    pip = [python, "-I", "-X", "utf8", "-m", "pip"]
    log_path = runtime.path(".runtime/python-install.log")
    with log_path.open("w", encoding="utf-8") as log:
        if not runtime.path(".venv/Lib/site-packages/pip").is_dir():
            # ensurepip的内部pip进程仅继承-I，按Windows本地编码统一读取两层输出。
            if run_installer(runtime, [python, "-I", "-m", "ensurepip", "--default-pip"], log,
                             encoding=locale.getencoding()):
                raise SetupError(f"无法准备pip；本地日志：{log_path}")
        version = run_process(runtime, [python, "-I", "-c",
                              "from importlib.metadata import version; print(version('pip'))"])
        if version.returncode:
            raise SetupError("无法读取工作区pip版本，请检查虚拟环境。")
        print("正在比较PyPI与阿里云镜像的文件下载速度。", file=sys.stderr, flush=True)
        indexes = rank_python_indexes()
        if version.stdout.strip() != PIP_VERSION:
            _download_python_packages(runtime, indexes, log, installer=True)
            wheel = runtime.path(".runtime/wheels/" + PIP_WHEEL_PATH.rsplit("/", 1)[1])
            if run_installer(runtime, pip + ["install", "--no-index", "--no-deps", "--require-hashes",
                             "--no-cache-dir", wheel.as_uri() + "#sha256=" + PIP_SHA256], log):
                raise SetupError(f"pip本机安装失败；本地日志：{log_path}")
        _download_python_packages(runtime, indexes, log, installer=False)
        if run_installer(runtime, pip + ["install", "--no-index", "--require-hashes",
                         "--only-binary=:all:", "--no-cache-dir",
                         "--find-links", str(runtime.path(".runtime/wheels")),
                         "-r", str(runtime.resource("scripts/requirements.txt"))], log):
            raise SetupError(f"Python依赖本机安装失败；本地日志：{log_path}")


def bootstrap(runtime: Runtime) -> dict[str, str]:
    """检查工作区运行时，按 Skill 依赖锁准备环境与 API Key 模板。"""
    check_python()
    node, _ = check_node(runtime)

    source = runtime.resource("scripts/bailian")
    lock_path = source / "package-lock.json"
    if not lock_path.is_file():
        raise SetupError("缺少BL依赖锁文件，停止安装。")
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        locked_version = lock["packages"]["node_modules/bailian-cli"]["version"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SetupError("BL依赖锁文件损坏，停止安装。") from exc
    if locked_version != BAILIAN_VERSION:
        raise SetupError("BL锁文件版本与当前命令契约不一致。")
    expected = locked_python_versions(runtime)

    # 先检查已有BL，避免明知其冲突仍修改Python环境。
    installed = installed_bl_version(runtime)
    destination = runtime.bl_directory
    if installed is not None:
        if installed != BAILIAN_VERSION or not runtime.bl_entry.is_file():
            raise SetupError("已有BL安装不匹配或不完整，未覆盖，请先检查。")
        verify_bl_installation(runtime)
    elif destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise SetupError("BL目标目录非空，未覆盖或自动重试，请先检查上次安装状态。")
    if installed is None:
        npm = npm_entry(node)

    runtime.prepare()
    environment = runtime.path(".venv")
    if environment.exists() and not (environment / "pyvenv.cfg").is_file():
        raise SetupError(".venv已存在且不是可识别的虚拟环境，未覆盖。")
    if not environment.exists():
        venv.EnvBuilder(with_pip=False).create(environment)
    python = runtime.path(".venv/Scripts/python.exe")
    if not python.is_file():
        raise SetupError("已有虚拟环境不完整，未覆盖或自动重建。")
    # 隔离模式使检查与安装使用标准库及venv依赖，避免导入工作区同名模块。
    checked = run_process(runtime, [str(python), "-I", "-c",
        "import sys, sysconfig; from pathlib import Path; "
        "raise SystemExit(sys.version_info[:2] != (3, 12) or sys.implementation.name != 'cpython' "
        "or sysconfig.get_platform() != 'win-amd64' or Path(sys.base_prefix).resolve() != Path(sys.argv[1]).resolve())",
        str(runtime.base_python.parent)])
    if checked.returncode:
        raise SetupError("工作区虚拟环境无法启动或未绑定本地Windows x64 CPython 3.12。"
                         "已保留该环境；请清理工作区.asr-transcription/.venv后重新运行Skill的scripts/bootstrap.ps1。")
    if installed_python_versions(runtime, expected) != expected:
        _install_python_dependencies(runtime)
        if installed_python_versions(runtime, expected) != expected:
            raise SetupError("pip结束但Python依赖校验失败，未自动重试。")

    if installed is None:
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(source / name, destination / name)

        _install_bailian(runtime, node, npm)
        verify_bl_installation(runtime)

    key_file = runtime.path(".env")
    if not key_file.exists():
        shutil.copyfile(runtime.resource("assets/env.example"), key_file)
    return {"status": "already_installed" if installed is not None else "installed",
            "version": BAILIAN_VERSION, "directory": str(destination), "key_file": str(key_file),
            "python": str(python), "base_python": str(runtime.base_python), "node": str(node)}
