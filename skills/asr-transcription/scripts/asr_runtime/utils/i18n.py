"""按本机网页的请求语言呈现提示，命令行默认使用中文。"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar


_LANGUAGE: ContextVar[str] = ContextVar("ui_language", default="zh-CN")
_ENGLISH: dict[str, str] = {
    "请求来源不被允许。": "This request did not come from the local page.",
    "缺少有效的本地页面来源。": "Open this page from Codex to continue.",
    "会话无效，请从Codex重新打开本地页面链接。": "This session is no longer valid. Reopen the local page from Codex.",
    "未找到此页面或接口。": "This page or endpoint was not found.",
    "未找到此接口。": "This endpoint was not found.",
    "本地文件操作未完成，请检查路径与访问权限。": "The file operation could not be completed. Check the folder path and access permissions.",
    "请选择文件后传入本机。": "Select a file to add it to this local session.",
    "请求必须为JSON。": "The request must use JSON.",
    "请求体不能为空。": "The request body must not be empty.",
    "表格或文本内容过大，请减少后重新检查。": "The table or text is too large. Remove some content and check again.",
    "请求格式不正确。": "The request format is invalid.",
    "默认保存目录不能重定向到其他目录。": "The default output folder points to another location. Choose a folder directly.",
    "默认保存位置存在同名文件，请选择其他文件夹。": "A file already exists at the default output location. Choose another folder.",
    "请点击“选择文件夹”设置保存位置。": "Use Choose folder to set the output location.",
    "所选文件夹已不存在，请重新选择。": "The selected folder no longer exists. Choose it again or select another folder.",
    "此文件夹无法保存文件，请选择其他位置。": "Files cannot be saved to this folder. Choose another location.",
    "当前会话已关闭。": "This session has closed. Open a new transcription page from Codex.",
    "会话已失效，请回到 Codex 重新打开配置页。": "This session has expired. Return to Codex to open a new configuration page.",
    "当前编辑会话已结束，请回到 Codex 查看任务。": "This editing session has ended. Return to Codex to check the task.",
    "请先点击“返回修改”再编辑转写设置。": "Select Back to edit before changing the transcription settings.",
    "请先在网页完成填写并进入预览页，再回到 Codex 确认。": "Complete the form and open the preview before confirming the session in Codex.",
    "文件仍在添加，请稍候。": "The file is still being added. Wait for it to finish.",
    "未知的保存位置。": "The output location is invalid.",
    "无法读取 .env 文件。": "The .env file could not be read. Check that it exists and is accessible.",
    "不支持的文件用途。": "This file type is not supported for this upload.",
    "所选文件名或格式不符合要求。": "The file name or format is not supported. Choose a supported file.",
    "文件为空或超过本机接收上限。": "The file is empty or exceeds the local upload limit.",
    "此类文件正在添加，请稍候。": "A file of this type is already being added. Wait for it to finish.",
    "本地文件暂存目录不能重定向。": "The local upload folder points to another location. Reopen the page from Codex.",
    "传入的文件不完整，请重新选择。": "The file transfer was incomplete. Select the file again.",
    "请选择音频文件。": "Choose an audio file.",
    "请求含不支持的配置字段。": "The request contains unsupported settings.",
    "请选择有效的鉴权方式。": "Choose a supported authentication method.",
    "请选择有效的识别增强方式。": "Choose supported recognition accuracy options.",
    "转写设置已变更，请重新检查并预览。": "The transcription settings have changed. Review the updated preview before confirming.",
    "实际媒体格式不在固定模型支持范围内。": "The file's media format is not supported by this model.",
    "无法确定有效音频时长，不能完成上传前校验。": "The audio duration could not be read. Choose a valid audio file.",
    "音频时长超过模型允许的12小时。": "The recording exceeds the model's 12-hour limit.",
    "待上传音频超过临时OSS的1 GB上限。": "The audio file exceeds the 1 GB limit for temporary OSS storage.",
    "参考文本必须为文字，请重新输入。": "Context must be text. Enter it again.",
    "参考文本为空，请输入与录音相关的术语或参考文字，或关闭上下文增强。": "Context is empty. Enter terms or reference text related to the recording, or turn off context enhancement.",
    "参考文本共 {count} 个字符，最多支持 {maximum} 个，超出 {excess} 个。请精简后重新检查。": "The context contains {count} characters, exceeding the {maximum}-character limit by {excess}. Shorten it and check again.",
    "参考文本第 {position} 个字符无法传输（{codepoint}），请删除或重新输入。": "Character {position} in the context cannot be transmitted ({codepoint}). Remove or replace it.",
    "不接受公式，请填写固定文本和数值。": "Use plain text and numeric values instead of formulas.",
    "热词必须为非空文本。": "Enter a non-empty text value for the hotword.",
    "请移除热词首尾空白、换行或控制字符；程序不会自动修改。": "Remove leading or trailing spaces, line breaks, and control characters from the hotword. Your text is kept as entered.",
    "含非ASCII字符时，热词总长度最多15个字符。": "A hotword containing non-ASCII characters can have up to 15 characters in total.",
    "纯ASCII热词按空格切分后最多7段。": "An ASCII-only hotword can contain up to 7 space-separated parts.",
    "权重必须为1至5的整数或50。": "Set the weight to an integer from 1 to 5, or to 50.",
    "与第{other_row}行热词重复，请删除重复行，仅保留一行。": "This hotword also appears in row {other_row}. Remove duplicate rows and keep one entry.",
    "热词总数超过2000个，请减少。": "The list exceeds 2,000 hotwords. Remove some entries.",
    "超级热词（权重50）最多50个。": "You can use up to 50 super hotwords with a weight of 50.",
    "请修改热词表格中标红的单元格后重新检查。": "Correct the cells marked in red in the hotword table, then check again.",
    "请至少填写一个热词及其权重，或关闭热词增强。": "Enter at least one hotword and its weight, or turn off hotword enhancement.",
    "热词表格格式无效，请重新填写或导入。": "The hotword table format is invalid. Enter the rows again or import a workbook.",
    "热词表格最多支持10000行，请减少后重新检查。": "The hotword table supports up to 10,000 rows. Remove some rows and check again.",
    "单元格必须为文本或数值。": "The cell must contain text or a number.",
    "Excel单元格类型不受支持，请在此重新填写文本或权重整数。": "This Excel cell type is not supported. Enter the hotword text or an integer weight in this cell.",
    "已忽略{count}个完全空白行。": "Empty rows skipped: {count}.",
    "请选择一种语言，或使用自动识别。": "Choose one audio language or use automatic detection.",
    "设置发言人数前，请开启区分发言人。": "Turn on speaker diarization before setting the number of speakers.",
    "发言人数需为 {minimum}–{maximum} 的整数，或使用自动识别。": "Enter a whole number from {minimum} to {maximum}, or leave this blank for automatic detection.",
    "说话人选项必须为开启或关闭。": "Set speaker diarization to on or off.",
    "音频文件为空。": "The audio file is empty.",
    "此音频包含 {channels} 个声道。为区分发言人，转写前将生成单声道 FLAC 副本，保留原文件。副本通过大小和时长检查后才会上传。": "This recording has {channels} channels. A mono FLAC copy will be created for speaker diarization before transcription. The original file is kept, and the copy is uploaded only after its size and duration are checked.",
    "音频超过 2 小时。启用发言人区分可能导致识别失败或超时，建议使用 2 小时以内的音频。": "This recording is longer than 2 hours. Speaker diarization may fail or time out. Use a recording of 2 hours or less for this feature.",
    "此文件包含 {tracks} 个音轨，仅转写第一个音轨（索引0），其余音轨不会转写。": "This file has {tracks} audio tracks. Only the first track (index 0) will be transcribed.",
    "文件在校验期间发生变化，请重新校验。": "The file changed while it was being checked. Check it again.",
    "无法读取音频，请检查文件是否损坏及格式是否支持。": "The audio file could not be read. Check that it is not damaged and uses a supported format.",
    "无法读取热词Excel，请检查文件是否损坏或仍在写入。": "The hotword workbook could not be read. Finish saving the file and check that it is not damaged.",
    "热词文件超过 5 MB 文件上限。": "The hotword file exceeds the 5 MB limit.",
    "热词Excel结构过大：解压内容最多20 MiB、200个内部文件。": "The hotword workbook exceeds the local processing limit: 20 MiB of uncompressed content or 200 internal files. Use a smaller workbook based on the template.",
    "不支持加密的热词Excel，请保存为普通.xlsx文件。": "Encrypted workbooks are not supported. Save an unencrypted .xlsx file.",
    "多个工作表时请将待使用的工作表命名为“热词”。": "If the workbook has multiple sheets, name the sheet to use 热词.",
    "请使用普通工作表填写热词，不支持图表工作表。": "Enter hotwords in a regular worksheet. Chart sheets are not supported.",
    "热词工作表仅支持两列、最多10001行（含表头和空行）。": "The hotword sheet must have two columns and no more than 10,001 rows, including the header and empty rows.",
    "首行必须依次为text、weight，或中文列名热词、权重。": "The first row must contain text and weight in that order. The Chinese headers 热词 and 权重 are also accepted.",
    "请按模板修改表头。": "Use the column headers from the template.",
    "仅读取名为“热词”的工作表，其他工作表不参与此次转写。": "Only the sheet named 热词 is used for this transcription.",
    "已按中文别名读取表头：热词对应text，权重对应weight。": "The Chinese column headers were recognized: 热词 as text, and 权重 as weight.",
    "请输入 API Key。": "Enter your API key.",
    "API Key 中含有空格或换行，请检查后重新填写。": "The API key contains spaces or line breaks. Check the value and enter it again.",
    "尚未配置 API Key，请在网页中填写并保存。": "No API key is configured. Enter and save your key on the transcription page.",
    "无法保存 API Key，请检查工作目录的访问权限。": "The API key could not be saved. Check access permissions for the working folder.",
    "示例术语": "Example term",
    "目录选择请求无效。": "The folder selection request is invalid.",
    "请先关闭已打开的文件夹窗口。": "Finish or cancel the open folder dialog before opening another one.",
    "所选位置不是文件夹，请重新选择。": "The selected location is not a folder. Choose a folder.",
    "所选文件夹不存在或无法访问，请重新选择。": "The selected folder does not exist or cannot be accessed. Choose another folder.",
    "文件夹选择窗口目前仅支持 Windows。": "The folder picker is currently available on Windows only.",
    "无法启动文件夹窗口，请检查 Python 运行环境。": "The folder dialog could not start. Ask Codex to check the Python installation.",
    "文件夹窗口异常退出，请重新选择。": "The folder dialog closed unexpectedly. Choose the folder again.",
    "无法读取文件夹选择结果，请重新选择。": "The folder selection could not be read. Choose the folder again.",
    "当前 Python 缺少 tkinter/Tcl/Tk 组件。": "This Python installation is missing tkinter/Tcl/Tk.",
    "无法打开文件夹窗口，请从正常 Windows 桌面重新启动服务。": "The folder dialog could not open. Restart the local service from an interactive Windows desktop.",
    "录音转写 · 选择保存位置": "Audio transcription · Choose an output folder",
    "本机文件位置无效，请重新添加文件。": "The local file location is invalid. Add the file again.",
    "文件不是当前会话的本机副本，请重新添加。": "The file does not belong to this local session. Add it again.",
    "请选择普通文件，不能选择目录。": "Choose a file instead of a folder.",
    "文件扩展名不在允许的格式范围内。": "The file extension is not supported.",
    "无法读取指定文件，请检查路径和访问权限。": "The file could not be read. Check its location and access permissions.",
    "无法读取文件，请检查访问权限后重新校验。": "The file could not be read. Check its access permissions, then check it again.",
    "私有运行目录指向工作区外，请检查.asr-transcription。": "The private runtime folder points outside the working folder. Check .asr-transcription.",
    "私有运行目录与Skill安装目录重叠，请选择其他工作区。": "The runtime folder overlaps the Skill installation. Choose a different working folder.",
    "运行路径指向私有目录外：{relative}": "The runtime path points outside the private runtime folder: {relative}",
    "资源路径指向Skill目录外：{relative}": "The resource path points outside the Skill installation: {relative}",
    "Skill安装目录用于保存程序资源，请选择其他位置保存转写结果。": "Choose an output folder outside the Skill installation, which contains the program files.",
    "任务编号应为Codex交接回执中的32位小写十六进制编号。": "Use the 32-character lowercase hexadecimal task ID returned by Codex after handoff.",
    "任务目录不能重定向。": "The task folder must remain in its original location."
}


def translate(message: str) -> str:
    """按当前请求语言查找完整消息模板，保留未登记的原文。"""
    return _ENGLISH.get(message, message) if _LANGUAGE.get() == "en" else message


@contextmanager
def language_scope(accept_language: str) -> Iterator[None]:
    """设置当前请求的中英文语言，并在结束时恢复调用方语言。"""
    primary = accept_language.split(",", 1)[0].split(";", 1)[0].strip().lower()
    language = "en" if primary == "en" or primary.startswith("en-") else "zh-CN"
    token = _LANGUAGE.set(language)
    try:
        yield
    finally:
        _LANGUAGE.reset(token)
