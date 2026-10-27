"""读取工作区 API Key 并准备 BL 凭据环境。"""

import shutil
from pathlib import Path

from .environment import Runtime, SetupError, child_environment


def _validate_api_key(value: object) -> str:
    """校验用户填写的 API Key，返回去除首尾空白的凭据。"""
    if not isinstance(value, str) or not value.strip():
        raise SetupError("请输入 API Key。")
    key = value.strip()
    if any(character.isspace() for character in key):
        raise SetupError("API Key 中含有空格或换行，请检查后重新填写。")
    return key


def read_api_key(runtime: Runtime, *, required: bool = True) -> str:
    """读取并校验私有 .env 中的 API Key；required=False 时缺失或空值返回空字符串。"""
    from dotenv import dotenv_values

    path = runtime.path(".env")
    if not path.is_file():
        if required:
            raise SetupError("尚未配置 API Key，请在网页中填写并保存。")
        return ""
    # 不加载到全局os.environ，不展开${变量}，不从其他目录自动寻找.env。
    value = dotenv_values(path, encoding="utf-8-sig", interpolate=False).get("DASHSCOPE_API_KEY")
    if value is None or not value.strip():
        if required:
            raise SetupError("尚未配置 API Key，请在网页中填写并保存。")
        return ""
    return _validate_api_key(value)


def write_api_key(runtime: Runtime, value: object, *, staging_directory: Path) -> None:
    """在编辑会话目录更新 API Key 后替换正式 .env，保留其他配置与注释。"""
    from dotenv import set_key

    key = _validate_api_key(value)
    path = runtime.path(".env")
    path.parent.mkdir(parents=True, exist_ok=True)
    staging_directory.mkdir(parents=True, exist_ok=True)
    staged = staging_directory / ".env"
    try:
        if path.exists():
            shutil.copyfile(path, staged)
        else:
            staged.write_bytes(b"")
        # dotenv将临时文件放在目标旁；会话目录使强制退出后的凭据副本也可归属清理。
        set_key(staged, "DASHSCOPE_API_KEY", key, encoding="utf-8")
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


def api_key_status(runtime: Runtime) -> dict[str, str | bool]:
    """返回本机API Key的配置状态与提示。"""
    try:
        read_api_key(runtime)
    except (SetupError, OSError, UnicodeError) as exc:
        message = str(exc) if isinstance(exc, SetupError) else "无法读取 .env 文件，请检查文件权限，并使用 UTF-8 编码保存。"
        return {"mode": "api_key", "configured": False, "verified_online": False, "message": message}
    return {"mode": "api_key", "configured": True, "verified_online": False,
            "message": "已检测到 API Key，尚未验证可用性。"}


def bailian_environment(runtime: Runtime, auth_mode: str) -> dict[str, str]:
    """构造BL环境，按鉴权方式配置工作区API Key。"""
    env = child_environment(runtime)
    if auth_mode == "api_key":
        env["DASHSCOPE_API_KEY"] = read_api_key(runtime)
    elif auth_mode != "console":
        raise SetupError("未知鉴权方式。")
    return env
