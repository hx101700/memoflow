"""按固定清单构建可独立安装的录音转写 Skill。"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import TypedDict
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


SKILL_DIRECTORY = Path("skills/asr-transcription")
REPOSITORY_FILES = ("README.md", "README.en.md")
REQUIRED_FILES = (
    "SKILL.md", "agents/openai.yaml", "LICENSE", "assets/env.example",
    "references/usage.md", "references/errors.md", "references/model.md",
    "scripts/asr.py", "scripts/bootstrap.ps1", "scripts/runtimes.json", "scripts/requirements.txt",
    "scripts/bailian/package.json", "scripts/bailian/package-lock.json",
    "scripts/bailian/console-browser.cjs",
    "scripts/asr_runtime/__init__.py", "scripts/asr_runtime/__main__.py",
    "scripts/asr_runtime/models.py", "scripts/asr_runtime/web.py",
    "scripts/asr_runtime/error_catalog.json",
    "scripts/asr_runtime/application/__init__.py",
    "scripts/asr_runtime/application/bootstrap.py",
    "scripts/asr_runtime/application/diagnostics.py",
    "scripts/asr_runtime/application/session.py",
    "scripts/asr_runtime/application/recovery.py",
    "scripts/asr_runtime/application/transcription.py",
    "scripts/asr_runtime/application/delivery.py",
    "scripts/asr_runtime/application/inputs.py",
    "scripts/asr_runtime/application/rules.py",
    "scripts/asr_runtime/utils/__init__.py",
    "scripts/asr_runtime/utils/environment.py",
    "scripts/asr_runtime/utils/installation.py",
    "scripts/asr_runtime/utils/auth.py",
    "scripts/asr_runtime/utils/bailian.py",
    "scripts/asr_runtime/utils/media.py",
    "scripts/asr_runtime/utils/results.py",
    "scripts/asr_runtime/utils/documents.py",
    "scripts/asr_runtime/utils/path_picker.py",
    "scripts/asr_runtime/utils/_path_dialog.py",
    "scripts/asr_runtime/utils/files.py",
    "scripts/asr_runtime/utils/job_files.py",
    "scripts/asr_runtime/utils/session_files.py",
    "scripts/asr_runtime/utils/hotwords.py",
    "scripts/asr_runtime/utils/i18n.py",
    "scripts/asr_runtime/static/index.html",
    "scripts/asr_runtime/static/app.css",
    "scripts/asr_runtime/static/app.js",
    "scripts/asr_runtime/static/favicon.svg",
    "scripts/asr_runtime/static/THIRD_PARTY_LICENSES.txt",
)


class BuildReport(TypedDict):
    """描述发行文件及其固定清单。"""

    status: str
    path: str
    file_count: int
    files: list[str]


def release_files(root: Path) -> dict[str, Path]:
    """核对运行资源和仓库使用说明，返回固定归档路径映射。"""
    files = {name: root / SKILL_DIRECTORY / name for name in REQUIRED_FILES}
    files.update({name: root / name for name in REPOSITORY_FILES})
    for name, path in files.items():
        if path.resolve(strict=True) != path or not path.is_file():
            raise ValueError(f"发行文件不是普通文件：{name}")
    return dict(sorted(files.items()))


def runtime_files(root: Path, directory: Path) -> dict[str, Path]:
    """核对官方运行时归档的固定摘要，返回完整包附加资源。"""
    manifest = json.loads((root / SKILL_DIRECTORY / "scripts/runtimes.json").read_text(encoding="utf-8"))
    files: dict[str, Path] = {}
    for definition in manifest.values():
        name = definition["url"].rsplit("/", 1)[1]
        archive = directory / name
        with archive.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != definition["sha256"]:
            raise ValueError(f"运行时归档摘要不符：{name}")
        files["assets/runtimes/" + name] = archive
    return files


def build_zip(root: Path, destination: Path | None = None, *, runtime_directory: Path | None = None) -> BuildReport:
    """按同一源码生成轻量包或附带两个官方运行时归档的完整包。"""
    root = root.resolve(strict=True)
    files = release_files(root)
    if runtime_directory is not None:
        files.update(runtime_files(root, runtime_directory))
    files = dict(sorted(files.items()))
    filename = "asr-transcription.zip" if runtime_directory is not None else "asr-transcription-lite.zip"
    destination = (destination or root / "dist" / filename).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "x", compression=ZIP_DEFLATED) as archive:
        for name, path in files.items():
            archive.write(path, name, compress_type=ZIP_STORED if name.endswith(".zip") else ZIP_DEFLATED)
    return {"status": "created", "path": str(destination),
            "file_count": len(files), "files": list(files)}


def main() -> int:
    """解析输出位置，构建用户 Skill 包并打印 JSON 回执。"""
    parser = argparse.ArgumentParser(description="构建可独立安装的 asr-transcription Skill。")
    parser.add_argument("--output", type=Path, help="输出 ZIP 路径；已有文件会保留")
    parser.add_argument("--runtime-directory", type=Path, help="附带此目录中与runtimes.json摘要匹配的两个官方ZIP")
    options = parser.parse_args()
    try:
        report = build_zip(Path(__file__).resolve().parents[1], options.output,
                           runtime_directory=options.runtime_directory)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "failed", "message": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
