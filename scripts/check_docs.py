"""检查仓库Markdown中的本地文件与章节链接。"""

import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def heading_ids(text: str) -> set[str]:
    """按本仓库的ATX标题生成GitHub章节编号。"""
    headings = re.findall(r"^#+\s+(.+)$", text, re.M)
    return {re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-") for heading in headings}


def main() -> int:
    """检查产品、开发和Skill资料，打印失效链接并返回检查结果。"""
    documents = sorted({path for pattern in ("*.md", "doc/**/*.md", "release/*.md", "skills/**/*.md")
                        for path in ROOT.glob(pattern)})
    failures: list[dict[str, str]] = []
    checked = 0
    for path in documents:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if re.match(r"[a-zA-Z][\w+.-]*:", target):
                continue
            filename, _, fragment = unquote(target).partition("#")
            resolved = (path.parent / filename).resolve() if filename else path
            checked += 1
            reason = None
            if not resolved.exists():
                reason = "missing file"
            elif fragment and resolved.suffix == ".md":
                if fragment not in heading_ids(resolved.read_text(encoding="utf-8")):
                    reason = "missing heading"
            if reason:
                failures.append({"source": path.relative_to(ROOT).as_posix(), "target": target, "reason": reason})
    print(json.dumps({"documents": len(documents), "local_links": checked, "failures": failures}, ensure_ascii=False))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
