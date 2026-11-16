中文 | [English](https://github.com/hx101700/memoflow/blob/v0.1.6/release/NOTES.en.md)

# MemoFlow v0.1.6

这次加入了转写后的**回听校对**。你可以一边听录音，一边修改文字和说话人，校对完成后直接导出文档。

### 更新内容

- **同步百炼 CLI 2.10.1**：更新官方 CLI 及依赖，继续使用 Qwen-Audio-3.1-ASR-Flash-Filetrans 转写录音。
- **新增回听校对**：转写后可逐句回听、修改文字和说话人，修改自动保存；支持重置单句、跳转到下一处修改，并选择目录导出 Word、Excel、Markdown 校验稿。
- **调整 Skill 表述**：开始处理、等待结果和交付时，Codex 使用更自然、简短的说明，让当前状态和下一步更清楚。
- **增加更新重试**：安装本版后，后续更新的版本检查与轻量包下载共用最多两次额外网络重试机会，减少因短暂网络波动而手动重新发起的操作。
- **补充计费与额度提示**：免费额度耗尽、账户欠费或预算限制导致识别失败时，说明对应原因并提供处理入口。
- 修复 bug 并优化使用体验。

### 下载

| 安装包 | 说明 |
| --- | --- |
| **完整包（首次安装推荐手动下载该发行包） · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.6/asr-transcription.zip)** | 附带 Python、Node.js 和配套 npm，用于首次安装时准备基础运行环境。 |
| **轻量包（更新时使用，由 Codex 自动下载） · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.6/asr-transcription-lite.zip)** | 复用已安装的 Python、Node.js 和 npm，适合后续更新。 |

### 安装与更新

首次安装，或从 [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0)、[v0.1.1](https://github.com/hx101700/memoflow/releases/tag/v0.1.1) 升级，请将新版 ZIP 交给 Codex，按 [README「安装」一节](https://github.com/hx101700/memoflow/blob/v0.1.6/README.md#安装)完成安装或更新。

已安装 [v0.1.2](https://github.com/hx101700/memoflow/releases/tag/v0.1.2) 以及高于此版本的用户，可告诉 Codex“检查并更新语音转写 Skill”，通过自动更新升级到 v0.1.6（即当前版本），后续的正式版本也可通过该方式获取。

也支持旧版手动更新：将新版本的 ZIP 和[「安装」一节](https://github.com/hx101700/memoflow/blob/v0.1.6/README.md#安装)中的完整请求一起发给 Codex，即可完成更新。

升级沿用原工作目录，保留已有运行时、凭据、任务和转写结果。Codex 会将百炼 CLI 依赖准备为本版要求的 2.10.1。

在国内网络环境下使用时，建议为更新操作配置可稳定访问 GitHub 的网络连接，以便顺利检查和下载更新。

遇到问题，欢迎通过 [Issues](https://github.com/hx101700/memoflow/issues) 反馈。如果 MemoFlow 对你有帮助，欢迎给项目点个 [Star](https://github.com/hx101700/memoflow)。
