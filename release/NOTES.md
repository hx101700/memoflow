中文 | [English](https://github.com/hx101700/memoflow/blob/v0.1.5/release/NOTES.en.md)

# MemoFlow v0.1.5

这次更新完善了代理网络下的运行配置和网页确认消息，并接入官方百炼 CLI 2.8.4。升级完成后，Codex 会告诉你这一版改了什么，再继续手头的任务。

### 更新内容

- **接入百炼 CLI 2.8.4**：适配新版浏览器登录和错误输出，继续使用 Qwen-Audio-3.1-ASR-Flash-Filetrans 转写录音。
- **保留已有网络设置**：运行时沿用用户配置的代理和证书，修复这些设置在启动百炼 CLI 时被过滤的问题。
- **确认消息更完整**：从预览页复制的消息包含云端接收方、北京地域、模型和会话编号，便于 Codex 承接本次转写授权。
- **更新后了解变化**：成功更新并准备好环境后，Codex 参考该版本的 Release 简述变化，随后继续原任务。

### 下载

| 安装包 | 说明 |
| --- | --- |
| **完整包（首次安装推荐手动下载该发行包） · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.5/asr-transcription.zip)** | 附带 Python、Node.js 和配套 npm，用于首次安装时准备基础运行环境。 |
| **轻量包（更新时使用，由 Codex 自动下载） · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.5/asr-transcription-lite.zip)** | 复用已安装的 Python、Node.js 和 npm，适合后续更新。 |

### 安装与更新

首次安装，或从 [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0)、[v0.1.1](https://github.com/hx101700/memoflow/releases/tag/v0.1.1) 升级，请将新版 ZIP 交给 Codex，按 [README「安装」一节](https://github.com/hx101700/memoflow/blob/v0.1.5/README.md#安装)完成安装或更新。

已安装 [v0.1.2](https://github.com/hx101700/memoflow/releases/tag/v0.1.2) 以及高于此版本的用户，可告诉 Codex“检查并更新语音转写 Skill”，通过自动更新升级到 v0.1.5（即当前版本），后续的正式版本也可通过该方式获取。

也支持旧版手动更新：将新版本的 ZIP 和[「安装」一节](https://github.com/hx101700/memoflow/blob/v0.1.5/README.md#安装)中的完整请求一起发给 Codex，即可完成更新。

升级沿用原工作目录，保留已有运行时、凭据、任务和转写结果。Codex 会将百炼 CLI 依赖准备为本版要求的 2.8.4。

在国内网络环境下使用时，建议为更新操作配置可稳定访问 GitHub 的网络连接，以便顺利检查和下载更新。

遇到问题，欢迎通过 [Issues](https://github.com/hx101700/memoflow/issues) 反馈。
