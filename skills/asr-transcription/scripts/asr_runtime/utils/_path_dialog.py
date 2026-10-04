"""显示独立进程中的文件或目录窗口，通过管道返回选择结果。"""

import json
import sys
from typing import Literal, cast


def show_path_dialog(initial: str, title: str, *, mode: Literal["audio", "directory"],
                     audio_suffixes: tuple[str, ...] = (), audio_label: str = "音频文件") -> str | None:
    """显示原生选择窗口并返回路径，取消返回None并销毁父窗口。"""
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("当前 Python 缺少 tkinter/Tcl/Tk 组件。") from exc
    window = None
    try:
        window = tkinter.Tk()
        window.withdraw()
        window.attributes("-topmost", True)
        window.update_idletasks()
        if mode == "audio":
            filetypes = [(audio_label, tuple(f"*{suffix}" for suffix in audio_suffixes))] if audio_suffixes else []
            return filedialog.askopenfilename(
                parent=window, initialdir=initial, title=title, filetypes=filetypes,
            ) or None
        return filedialog.askdirectory(
            parent=window, initialdir=initial, title=title, mustexist=True,
        ) or None
    except tkinter.TclError as exc:
        raise RuntimeError("无法打开选择窗口，请从正常 Windows 桌面重新启动服务。") from exc
    finally:
        if window is not None:
            try:
                window.destroy()
            except tkinter.TclError:
                pass


if __name__ == "__main__":
    try:
        result = {"path": show_path_dialog(
            sys.argv[1], sys.argv[2], mode=cast(Literal["audio", "directory"], sys.argv[3]),
            audio_suffixes=tuple(json.loads(sys.argv[4])), audio_label=sys.argv[5],
        )}
    except RuntimeError as exc:
        result = {"error": str(exc)}
    # 仅写入父进程的私有管道，不进入应用日志。
    print(json.dumps(result, ensure_ascii=False), flush=True)
