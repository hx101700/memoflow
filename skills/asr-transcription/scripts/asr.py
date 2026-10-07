"""启动录音转写 Skill 的本机工具。"""

import sys

# Skill 目录作为只读资源使用，编译缓存留在执行进程内。
sys.dont_write_bytecode = True

if __name__ == "__main__":
    from asr_runtime.__main__ import main

    raise SystemExit(main())
