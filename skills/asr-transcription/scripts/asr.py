"""启动录音转写 Skill 的本机工具。"""

import sys
import json
from pathlib import Path

# Skill 目录作为只读资源使用，编译缓存留在执行进程内。
sys.dont_write_bytecode = True

if __name__ == "__main__":
    from update import UpdateError, skill_in_use

    try:
        with skill_in_use(Path(__file__).resolve().parents[1]):
            from asr_runtime.__main__ import main

            raise SystemExit(main())
    except (UpdateError, OSError) as error:
        print(json.dumps({"status": "failed", "message": str(error)}, ensure_ascii=False))
        raise SystemExit(1)
