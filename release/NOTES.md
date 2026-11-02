中文 | [English](https://github.com/hx101700/memoflow/blob/v0.1.4/release/NOTES.en.md)

# MemoFlow v0.1.4

本次更新升级至官方百炼 CLI 2.7.2，采用官方上传与网络兼容性修复，并补充上传失败和执行中断的错误说明，方便在转写遇到问题时定位原因。

### 更新内容

- **升级百炼 CLI 至 2.7.2**：采用新版官方依赖，继续使用 Qwen-Audio-3.1-ASR-Flash-Filetrans 完成录音转写。
- **上传失败原因更清楚**：获取上传授权失败时，保留服务返回的 HTTP 状态、错误码和请求编号，帮助 Codex 给出更具体的排查说明。
- **补充执行中断说明**：识别百炼 CLI 的中断退出状态，便于区分本机执行情况与云端任务结果。

### 下载

| 安装包 | 说明 |
| --- | --- |
| **完整包（首次安装推荐手动下载该发行包） · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.4/asr-transcription.zip)** | 附带 Python、Node.js 和配套 npm，用于首次安装时准备基础运行环境。 |
| **轻量包（更新时使用，由 Codex 自动下载） · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.4/asr-transcription-lite.zip)** | 复用已安装的 Python、Node.js 和 npm，适合后续更新。 |

### 安装与更新

首次安装，或从 [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0)、[v0.1.1](https://github.com/hx101700/memoflow/releases/tag/v0.1.1) 升级，请将新版 ZIP 交给 Codex，按 [README「安装」一节](https://github.com/hx101700/memoflow/blob/v0.1.4/README.md#安装)完成安装或更新。

已安装 [v0.1.2](https://github.com/hx101700/memoflow/releases/tag/v0.1.2) 以及高于此版本的用户，可告诉 Codex“检查并更新语音转写 Skill”，通过自动更新升级到 v0.1.4（即当前版本），后续的正式版本也可通过该方式获取。

也支持旧版手动更新：将新版本的 ZIP 和[「安装」一节](https://github.com/hx101700/memoflow/blob/v0.1.4/README.md#安装)中的完整请求一起发给 Codex，即可完成更新。

升级沿用原工作目录，保留已有运行时、凭据、任务和转写结果。Codex 会将百炼 CLI 依赖准备为本版要求的 2.7.2。

在国内网络环境下使用时，建议为更新操作配置可稳定访问 GitHub 的网络连接，以便顺利检查和下载更新。

遇到问题，欢迎通过 [Issues](https://github.com/hx101700/memoflow/issues) 反馈。
