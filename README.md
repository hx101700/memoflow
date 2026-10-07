# MemoFlow

中文 | [English](README.en.md)

> MemoFlow 让 Codex 把语音输入整理成符合用户习惯和指定格式的内容。

[![Latest release](https://img.shields.io/github/v/release/hx101700/memoflow?display_name=tag&sort=semver)](https://github.com/hx101700/memoflow/releases/latest) [![License](https://img.shields.io/github/license/hx101700/memoflow)](LICENSE) [![Windows](https://img.shields.io/badge/Windows-10%2F11%20x64-0078D4)](https://github.com/hx101700/memoflow/releases/latest)

MemoFlow 是一套面向 Codex 的交互式语音转写与个性化内容生成 Skill，适用于会议转写、内容生产、通话分析、访谈和培训等场景。用户只需在网页中选择录音、填写需要开启的识别能力并确认，Codex 就会调用阿里云百炼提供的 [Qwen-Audio-3.1-ASR-Flash-Filetrans](https://help.aliyun.com/zh/model-studio/qwen-audio-3-1-asr-flash-filetrans)，将录音整理成可校对的转写稿和指定格式的文档。

当前已经完成录音配置、非实时转写、热词与上下文增强、说话人区分和文档交付。后续 MemoFlow 会根据用户的校对反馈、重点要求和格式范例持续学习，逐步生成符合用户习惯、排版规整、可以直接继续使用的内容。

## 为什么需要 MemoFlow

会议录音本身不能直接变成可用的信息。用户通常还需要处理几件事：

- 长录音难以从头回听，重要内容、章节和待办事项不容易定位；
- 人名、产品名和行业术语容易被识别错；
- 多人讨论需要知道“谁说了什么”；
- 一次转写往往还要继续校对、整理，并保存成团队习惯的格式；
- 录音、认证、配置、转写和文件整理分散在多个工具里，操作过程容易失去上下文。

MemoFlow 面向这些需要把语音转成可用信息的场景：它先把录音整理成可回溯、可校对的文字，保留时间、说话人和重要术语，再让用户继续整理成自己需要的文档或内容。当前阶段先把录音配置、识别和校对交付做好。

## 为什么是 Codex + Qwen-Audio 3.1

两者承担不同的工作。

Codex 很擅长理解上下文、组织多步任务、读取文件和按用户要求继续处理，但语音识别本身不是它的核心能力。很多通用工作流会从 [Whisper](https://github.com/openai/whisper) 开始；Whisper 是优秀的通用多语种模型，但官方也明确说明它在不同语言上的表现差异很大。对于中文会议中的方言、人名、产品术语、说话人和上下文，单靠通用识别结果往往还需要大量人工校对。

MemoFlow 把识别交给 Qwen-Audio 3.1，把任务组织和结果交付交给 Codex。在本项目的目标范围内，这个组合把“听不清、术语错、多人内容难整理、识别结果难继续加工”集中处理：Qwen 提供适合非实时文件转写的识别能力，Codex 把认证、网页核对、文件保存和后续处理串成一次可追踪的工作。

- **Qwen-Audio-3.1-ASR-Flash-Filetrans**负责非实时文件识别。阿里云将它定位为多语种及方言的长音频文件转写模型，支持说话人分离、热词和上下文增强；模型文档列出的单次音频上限为 12 小时、2 GB，启用说话人分离时建议控制在 2 小时以内。[模型说明](https://help.aliyun.com/zh/model-studio/asr-model)
- **Codex**负责本地工作流：准备 Skill 环境、打开配置页面、承接对话附件、引导认证、等待百炼返回，并把结果整理到用户选择的位置。
- **MemoFlow**把两者连接起来：完整转写内容保存在文件中，聊天只承载操作、确认和结果位置，后续可以在文件基础上继续校对并生成指定格式的内容。

识别专业词汇时，MemoFlow 使用百炼支持的即时热词和上下文增强。热词适合临时的人名、产品名和术语；上下文适合提供会议背景或领域语料，两者可以同时放进同一次请求。[阿里云精度增强说明](https://help.aliyun.com/zh/model-studio/improve-asr-accuracy)


## 第一次使用

1. 下载 [v0.1.2 安装包](https://github.com/hx101700/memoflow/releases/tag/v0.1.2)。
2. 把 ZIP 和下面这句话一起发给 Codex：

   ```text
   请将这个 ZIP 安装为 asr-transcription Skill，阅读其中的 SKILL.md，并按说明在当前任务文件夹准备运行环境。
   ```

3. 安装完成后告诉 Codex：

   ```text
   帮我转写这段录音。
   ```

4. 在网页中核对带入的录音，按需调整语言、说话人区分、热词、上下文和保存位置。
5. 点击“确认并预览”，确认后点击“复制给 Codex”，把确认消息发回原对话。
6. Codex 根据同一个任务完成认证、转写和文档交付。

完整包包含 Python 和 Node.js 运行时，适合大多数用户；轻量包体积更小，首次安装时从官方来源下载运行时。两种包都支持 Windows 10/11 x64，Python 依赖和百炼 CLI 仍需联网安装。

使用前请准备[阿里云账号](https://help.aliyun.com/zh/account/step-1-register-an-alibaba-cloud-account)，并按[百炼官方指引](https://help.aliyun.com/zh/model-studio/first-api-call-to-qwen)完成服务准备。

## 转写完成后

MemoFlow 会保存百炼返回的原始结果，并根据同一份转写内容制作三种不同格式的校对文档，方便你继续阅读、筛选、修改和归档。

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
