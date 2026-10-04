中文 | [English](https://github.com/hx101700/memoflow/blob/v0.1.0/release/NOTES.en.md)

MemoFlow 希望把录音整理成符合你习惯和格式要求的会议纪要。v0.1.0 开发预览先完成第一步：在 Codex 中转写录音，拿到带时间戳的 Word、Excel 和 Markdown，供你检查与校对。

### 功能特性

- **网页填写与预览**：添加录音，设置语言、发言人区分和保存位置。预览前后可以返回调整，确认后再交给 Codex。
- **热词与上下文**：直接填写热词，或导入 Excel 后就地修改。问题会标在对应单元格；热词和上下文可以同时使用。
- **百炼识别**：通过官方 BL CLI 调用 Qwen-Audio-3.1-ASR-Flash-Filetrans，支持控制台授权和北京地域 API Key。
- **三种文档**：一次生成 Word、Excel、Markdown 并保留原始 JSON。已有成功任务可以在本机重新导出。
- **中英界面与主题**：按习惯选择中文、English、浅色或深色外观。

### 从配置到交付

在网页点击“确认并预览”，核对无误后用“复制给 Codex”把确认消息发回对话。Codex 会接收这份设置；需要登录时引导你完成一次授权，随后等待转写和文件生成完成。交接后的设置固定，结果在 Codex 中查看。

编辑页面从打开起有效两小时，交接或到期会显示结束提示。已经交给 Codex 的任务不受页面期限影响。

### 开始使用

先注册阿里云账号，按平台指引完成实名认证和百炼服务准备。下载 [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.0/asr-transcription.zip)，连同下面这句话发给 Codex：

> 请解压 ZIP，阅读其中的 SKILL.md，帮我安装并配置 asr-transcription。

安装后说“帮我转写录音”，按打开的页面操作即可。安装包也包含最新的中英文 README。

当前支持 Windows 10/11 x64，需要 Python 3.12 x64、Node.js 18.17+ 与 npm。识别使用百炼北京地域，可能产生调用费用。个性化会议纪要与反馈学习属于后续阶段。

详细用法见 [README](https://github.com/hx101700/memoflow/blob/v0.1.0/README.md)，问题和建议欢迎提交 [Issue](https://github.com/hx101700/memoflow/issues)。
