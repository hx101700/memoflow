中文 | [English](https://github.com/hx101700/memoflow/blob/v0.1.2/release/NOTES.en.md)

# MemoFlow v0.1.2

这次更新让后续升级更省事：Codex 可以检查并获取新的 Skill 版本，复用已有运行环境，减少重复下载和手动安装。同时接入官方百炼 CLI 2.4.0，完善上传、登录与环境检查的处理。

### 更新内容

- **后续升级更方便**：加入 Skill 自动更新，每天最多自动检查一次正式版本。发现新版后下载轻量包完成更新，并向用户说明结果；也可主动要求 Codex 检查更新。
- **减少更新下载量**：沿用工作目录中的 Python、Node.js 和 npm，按新版要求准备依赖，保留凭据、任务及转写结果。
- **采用官方上传与登录修复**：升级至官方百炼 CLI 2.4.0，直接使用其上传等待时间和 Windows 授权链接处理，移除此前的本地修订与登录适配。
- **环境问题更容易定位**：修正虚拟环境绑定检查，区分依赖缺失与解释器运行异常，减少安装和诊断中的重复检查。
- **减少旧下载占用**：环境升级成功后清理工作目录中的旧版 Python 依赖和 npm 下载缓存，保留当前版本可复用的内容。

### 下载

| 安装包 | 说明 |
| --- | --- |
| **完整包（首次安装，手动下载，推荐） · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.2/asr-transcription.zip)** | 附带 Python、Node.js 和配套 npm，用于首次安装时准备基础运行环境。 |
| **轻量包（更新时使用，由 Codex 自动下载） · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.2/asr-transcription-lite.zip)** | 复用已安装的 Python、Node.js 和 npm，适合后续更新。 |

Python 依赖和百炼 CLI 的安装仍需联网。

### 安装与更新

首次安装，或从 [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0)、[v0.1.1](https://github.com/hx101700/memoflow/releases/tag/v0.1.1) 首次升级到 v0.1.2（即当前版本），请将新版 ZIP 交给 Codex，按 [README](https://github.com/hx101700/memoflow/blob/v0.1.2/README.md#安装) 完成安装或更新。

安装 v0.1.2（即当前版本）后，后续高于 v0.1.2 的正式版本，可以选择让 Codex 通过自动更新获取，也可继续将新 ZIP 交给 Codex 更新。

已有旧版百炼 CLI 时，Codex 会按新版 Skill 指引重新准备该依赖，保留原工作目录中的运行时、凭据、任务和结果。

遇到问题，欢迎通过 [Issues](https://github.com/hx101700/memoflow/issues) 反馈。
