# MemoFlow

中文 | [English](README.en.md)

> 把中文录音发给 Codex，生成带时间戳、可区分发言人的 Word、Excel 和 Markdown 转写稿。

[![Latest release](https://img.shields.io/github/v/release/hx101700/memoflow?display_name=tag&sort=semver)](https://github.com/hx101700/memoflow/releases/latest) [![License](https://img.shields.io/github/license/hx101700/memoflow)](LICENSE) [![Windows](https://img.shields.io/badge/Windows-10%2F11%20x64-0078D4)](https://github.com/hx101700/memoflow/releases/latest)

MemoFlow 是一个面向 Codex 的录音转写 Skill。它使用阿里云百炼的 [Qwen-Audio-3.1-ASR-Flash-Filetrans](https://help.aliyun.com/zh/model-studio/qwen-audio-3-1-asr-flash-filetrans)，通过本机网页让你核对录音、识别设置、热词、上下文和保存位置，再由 Codex 完成转写和文件交付。

当前交付第一阶段：**可靠的转写校对稿**。根据校对稿、范例和反馈生成个性化会议纪要是后续阶段。

<!-- SCREENSHOT: hero
建议放一张真实网页截图或 20–40 秒 GIF，展示“添加录音 → 预览 → 复制给 Codex”。
文件建议：doc/images/memoflow-demo.gif
请隐藏 API Key、用户名、本地路径和真实会议内容。
-->

## 30 秒开始

1. 下载 [v0.1.2 安装包](https://github.com/hx101700/memoflow/releases/tag/v0.1.2)。
2. 把 ZIP 和下面这句话一起发给 Codex：

   ```text
   请将这个 ZIP 安装为 asr-transcription Skill，阅读其中的 SKILL.md，并按说明在当前任务文件夹准备运行环境。
   ```

3. 安装完成后告诉 Codex：

   ```text
   帮我转写这段录音。
   ```

4. 在网页中核对录音和设置，点击“确认并预览”，再点击“复制给 Codex”，把确认消息发回原对话。

完整包适合大多数用户，包含 Python 和 Node.js 运行时；轻量包体积更小，首次安装时从官方来源下载运行时。两种包都支持 Windows 10/11 x64，Python 依赖和百炼 CLI 仍需联网安装。

使用前请准备[阿里云账号](https://help.aliyun.com/zh/account/step-1-register-an-alibaba-cloud-account)，并按[百炼官方指引](https://help.aliyun.com/zh/model-studio/first-api-call-to-qwen)完成服务准备。

## 你会得到什么

| 文件 | 内容 |
| --- | --- |
| `transcription.json` | 百炼返回的原始转写结果 |
| `transcription.docx` | 便于阅读和校对的 Word 文档 |
| `transcription.xlsx` | 可筛选、逐段查看的 Excel 文档 |
| `transcription.md` | 便于笔记和归档的 Markdown 文档 |

三种文档保留时间戳；开启说话人区分时包含说话人编号。输出目录由网页选择，默认位于当前工作目录的 `transcriptions` 下。

## 功能特性

- **Codex Skill 工作流**：录音附件、本机文件选择和已有录音路径进入同一套网页配置流程。
- **中文识别增强**：使用 Qwen-Audio 3.1，支持热词和上下文同时发送。
- **说话人区分**：默认开启；多声道录音需要合并时保留原文件，并生成处理副本。
- **可视化预览**：填写和预览分为两步，确认后才创建任务并交给 Codex 执行。
- **两种百炼认证**：控制台登录或工作目录中的北京地域 API Key。
- **本地文件交付**：原始 JSON、Word、Excel、Markdown 一次生成，支持成功任务本地重导。

## 适合谁

- 使用 Codex、希望把录音交给 AI 处理的 Windows 用户。
- 需要中文人名、产品名和专业术语增强的用户。
- 需要保留原文、时间戳和说话人信息，且希望人工校对的团队。

## 当前边界

- 当前只处理单个录音，不提供实时转写。
- 当前支持 Windows 10/11 x64；macOS/Linux 尚未作为验收平台。
- 当前交付转写校对稿，自动会议纪要和反馈学习仍在规划中。
- 识别会把录音和启用的增强内容发送到阿里云百炼北京地域，可能产生调用费用。

## 预览页面

<!-- SCREENSHOT: transcription-page
展示添加录音、转写设置、热词/上下文和保存位置。
文件建议：doc/images/01-transcription-overview.png
-->

<!-- SCREENSHOT: outputs
展示 Word、Excel、Markdown 成品的脱敏截图。
文件建议：doc/images/02-transcription-outputs.png
-->

## 帮助与参与

- [使用指南](skills/asr-transcription/references/usage.md)：安装、认证、网页操作和升级。
- [错误说明](skills/asr-transcription/references/errors.md)：登录、安装、会话和转写问题。
- [提交问题](https://github.com/hx101700/memoflow/issues)：请附操作系统、安装包、复现步骤和脱敏错误。
- [功能讨论](https://github.com/hx101700/memoflow/discussions)：分享使用场景、输出格式和第二阶段需求。
- [支持说明](SUPPORT.md)：选择 Issue、Discussion 或文档入口。
- [贡献指南](CONTRIBUTING.md)：提交代码、文档和示例前请先阅读。

请不要在 Issue、Discussion 或截图中提交 API Key、登录链接、录音原文或私人路径。

## 相关链接

| 资源 | 链接 |
| --- | --- |
| 阿里云百炼 | [控制台](https://bailian.console.aliyun.com/) · [官方文档](https://help.aliyun.com/zh/model-studio/) |
| 百炼 CLI | [官方主页](https://bailian.console.aliyun.com/cli) · [GitHub](https://github.com/modelstudioai/cli) |
| 识别精度增强 | [热词与上下文说明](https://help.aliyun.com/zh/model-studio/improve-asr-accuracy) |
| MemoFlow | [Release](https://github.com/hx101700/memoflow/releases/latest) · [开发文档](doc/README.md) |

本项目采用 [Apache-2.0](LICENSE) 许可证。
