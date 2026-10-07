# MemoFlow

中文 | [English](README.en.md)

> 把支持语种的会议录音交给 Codex，先听清、识准、整理成可校对的转写稿，再逐步生成符合你习惯的会议纪要。

[![Latest release](https://img.shields.io/github/v/release/hx101700/memoflow?display_name=tag&sort=semver)](https://github.com/hx101700/memoflow/releases/latest) [![License](https://img.shields.io/github/license/hx101700/memoflow)](LICENSE) [![Windows](https://img.shields.io/badge/Windows-10%2F11%20x64-0078D4)](https://github.com/hx101700/memoflow/releases/latest)

MemoFlow 的最终目标，是把一次次会议中的语音、上下文、校对和格式偏好，逐步整理成符合用户习惯的会议纪要。它会从用户提供的范例和确认过的修改中学习，形成稳定的个人化输出方式。

当前交付第一阶段：一个面向 Codex 的 `asr-transcription` Skill。它使用阿里云百炼的 [Qwen-Audio-3.1-ASR-Flash-Filetrans](https://help.aliyun.com/zh/model-studio/qwen-audio-3-1-asr-flash-filetrans)，支持模型覆盖的多语种与方言；当前产品重点以中文会议、人名和专业术语为主要使用场景。通过本机网页让你核对录音、识别设置、热词、上下文和保存位置，再由 Codex 完成一次非实时转写。

## 为什么需要 MemoFlow

会议录音本身不能直接变成可用的信息。用户通常还需要处理几件事：

- 长录音难以从头回听，重要内容、章节和待办事项不容易定位；
- 人名、产品名和行业术语容易被识别错；
- 多人讨论需要知道“谁说了什么”；
- 一次转写往往还要继续校对、整理，并保存成团队习惯的格式；
- 录音、认证、配置、转写和文件整理分散在多个工具里，操作过程容易失去上下文。

[通义听悟](https://help.aliyun.com/zh/tingwu/what-is-tingwu)将音视频记录、转写、说话人分离、内容提炼和重点定位组织成“阅读音视频”的工作方式。MemoFlow 借鉴这个产品方向，当前先把最基础也最关键的环节做好：让 Codex 帮用户把录音配置清楚、把内容识别准确，并交付可以检查和继续加工的转写稿。

## 为什么是 Codex + Qwen-Audio 3.1

两者承担不同的工作。

- **Qwen-Audio-3.1-ASR-Flash-Filetrans**负责非实时文件识别。阿里云将它定位为多语种及方言的长音频文件转写模型，支持说话人分离、热词和上下文增强；模型文档列出的单次音频上限为 12 小时、2 GB，启用说话人分离时建议控制在 2 小时以内。[模型说明](https://help.aliyun.com/zh/model-studio/asr-model)
- **Codex**负责本地工作流：准备 Skill 环境、打开配置页面、承接对话附件、引导认证、等待百炼返回，并把结果整理到用户选择的位置。
- **MemoFlow**把两者连接起来：完整转写内容保存在文件中，聊天只承载操作、确认和结果位置，后续可以在文件基础上继续校对和生成会议纪要。

识别专业词汇时，MemoFlow 使用百炼支持的即时热词和上下文增强。热词适合临时的人名、产品名和术语；上下文适合提供会议背景或领域语料，两者可以同时放进同一次请求。[阿里云精度增强说明](https://help.aliyun.com/zh/model-studio/improve-asr-accuracy)

## 第一次使用

第一次使用的时间取决于网络、环境准备和录音时长，项目不承诺固定的“30 秒完成”。实际步骤是：

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

MemoFlow 会保存百炼返回的原始 JSON，并根据同一份转写结果制作三种不同格式的校对文档，方便你按自己的工作方式继续阅读、筛选、修改和归档。

<!-- SCREENSHOT: hero
放一张真实网页截图或 20–40 秒 GIF，展示“添加录音 → 预览 → 复制给 Codex”。
文件建议：doc/images/memoflow-demo.gif
请隐藏 API Key、用户名、本地路径和真实会议内容。
-->

<!-- SCREENSHOT: outputs
放脱敏的 Word、Excel、Markdown 成品截图，展示同一份转写的不同整理方式。
文件建议：doc/images/02-transcription-outputs.png
-->

## 当前能力与边界

- 处理单个录音，不提供实时转写。
- 支持模型覆盖的多语种与方言、对话附件、本机文件选择、热词、上下文和说话人区分。
- 当前验收平台为 Windows 10/11 x64；macOS/Linux 尚未作为验收平台。
- 当前交付转写校对稿；自动会议纪要、用户风格学习和反馈闭环属于第二阶段。
- 识别会把录音及启用的增强内容发送到阿里云百炼北京地域，可能产生调用费用。

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
| 通义听悟 | [产品说明](https://help.aliyun.com/zh/tingwu/what-is-tingwu) |
| 识别精度增强 | [热词与上下文说明](https://help.aliyun.com/zh/model-studio/improve-asr-accuracy) |
| MemoFlow | [Release](https://github.com/hx101700/memoflow/releases/latest) · [开发文档](doc/README.md) |

本项目采用 [Apache-2.0](LICENSE) 许可证。
