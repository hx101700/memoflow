中文 | [English](https://github.com/hx101700/memoflow/blob/v0.1.0/release/NOTES.en.md)

# MemoFlow v0.1.0

MemoFlow v0.1.0 是首个公开版本，先完成“录音转写与校对稿交付”这一阶段。它把 Codex 的任务组织能力、阿里云百炼的语音识别能力和本机网页配置连接起来，用户可以在确认设置后获得可继续处理的转写结果。

### 这版包含

- **交互式转写页面**：选择录音，调整识别设置，在提交前查看预览。
- **对话附件入口**：从 Codex 附上的录音开始，沿用同一套配置和确认流程。
- **识别增强**：支持说话人区分、热词和上下文增强，并调用 Qwen-Audio-3.1-ASR-Flash-Filetrans 完成非实时文件转写。
- **任务交接**：确认消息包含 `session_id`，设置交给 Codex 后再执行，避免在对话中重复传递完整转写内容。
- **双语资料与两种安装包**：提供中英文 README，以及包含运行时的完整包和体积更小的轻量包。

### 下载

| 安装包 | 适合情况 |
| --- | --- |
| **完整包 · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.0/asr-transcription.zip)** | 包含 Python 和 Node.js 运行时，适合希望减少首次运行下载内容的用户。 |
| **轻量包 · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.0/asr-transcription-lite.zip)** | 初始下载体积更小，首次安装时从官方来源准备运行时。 |

两个包包含相同的 Skill 和运行代码，区别只在于是否附带 Python 与 Node.js 运行时归档。

详细介绍与使用入口见 [README](https://github.com/hx101700/memoflow/blob/v0.1.0/README.md)。问题反馈请提交到 [Issues](https://github.com/hx101700/memoflow/issues)。
