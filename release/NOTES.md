中文 | [English](https://github.com/hx101700/memoflow/blob/v0.1.3/release/NOTES.en.md)

# MemoFlow v0.1.3

本次更新完善了版本检查异常后的继续使用流程，在页面中加入当前版本号，并升级至官方百炼 CLI 2.5.1，让使用状态和登录问题更容易确认。

### 更新内容

- **更新检查异常时继续转写**：遇到 GitHub HTTP 403 等可恢复问题时，继续使用已安装的 Skill，承接本次请求并启动录音配置页。
- **页面直接查看版本**：在左上角 MemoFlow 旁展示当前 Skill 版本，方便确认安装结果和反馈问题；版本标签随深浅主题适配，与品牌文字对齐。
- **采用官方百炼 CLI 2.5.1**：使用官方的快速登录回调修复，完善登录超时及失败说明，便于定位授权问题。
- **安装问题提示更清晰**：区分临时的更新检查失败与需要修复的安装状态，给出对应的继续使用或修复指引。

### 下载

| 安装包 | 说明 |
| --- | --- |
| **完整包（首次安装推荐手动下载该发行包） · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.3/asr-transcription.zip)** | 附带 Python、Node.js 和配套 npm，用于首次安装时准备基础运行环境。 |
| **轻量包（更新时使用，由 Codex 自动下载） · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.3/asr-transcription-lite.zip)** | 复用已安装的 Python、Node.js 和 npm，适合后续更新。 |

Python 依赖和百炼 CLI 的安装仍需联网。

### 安装与更新

首次安装，或从 [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0)、[v0.1.1](https://github.com/hx101700/memoflow/releases/tag/v0.1.1) 升级，请将新版 ZIP 交给 Codex，按 [README「安装」一节](https://github.com/hx101700/memoflow/blob/v0.1.3/README.md#安装)完成安装或更新。

已安装 [v0.1.2](https://github.com/hx101700/memoflow/releases/tag/v0.1.2) 的用户，可告诉 Codex“检查并更新语音转写 Skill”，通过自动更新升级到 v0.1.3（即当前版本）。安装本版后，后续高于 v0.1.3 的正式版本也可通过该方式获取。

也支持旧版手动更新：将新版本的 ZIP 和[「安装」一节](https://github.com/hx101700/memoflow/blob/v0.1.3/README.md#安装)中的完整请求一起发给 Codex，即可完成更新。

升级沿用原工作目录，保留已有运行时、凭据、任务和转写结果。Codex 会按新版要求准备百炼 CLI 依赖。

遇到问题，欢迎通过 [Issues](https://github.com/hx101700/memoflow/issues) 反馈。
