# MemoFlow

中文 | [English](README.en.md)

MemoFlow 的目标是把录音整理成符合你习惯和指定格式的会议纪要，并从你提供的范例、格式要求与确认的修改反馈中持续学习。

当前可用的是第一阶段的 `asr-transcription` Skill：在 Codex 中转写单个录音，生成可供校对的 Word、Excel 和 Markdown。它通过官方 [BL CLI](https://github.com/modelstudioai/cli) 调用[阿里云百炼](https://help.aliyun.com/zh/model-studio/what-is-model-studio)，并提供本机网页帮助你配置转写。

## 功能特性

- **录音转写**：处理单个音频，保留时间戳，支持区分发言人。
- **精度增强**：直接填写热词或从 Excel 导入后修改，添加上下文参考文本，两种方式可以同时使用。
- **可视化配置**：在浏览器中添加录音、调整设置并选择保存位置，支持中英文界面及浅色、深色主题。
- **文档生成**：同时生成 Word、Excel 和 Markdown，保留原始 JSON，支持本地重新导出。

## Skill 安装

从 [Releases](https://github.com/hx101700/memoflow/releases) 下载第一阶段的开发预览包 `asr-transcription.zip`。

使用前，请先[注册阿里云账号](https://help.aliyun.com/zh/account/step-1-register-an-alibaba-cloud-account)，按[官方指引](https://help.aliyun.com/zh/model-studio/first-api-call-to-qwen)完成实名认证、开通百炼服务等准备。

将发行包 `asr-transcription.zip` 和下面这句话发给 Codex：

```text
请将这个 ZIP 安装为 asr-transcription Skill，阅读其中的 SKILL.md，并按说明在当前任务文件夹准备运行环境。
```

Skill 安装位置存放工具与说明；工作目录存放运行环境、凭据、任务和结果，默认使用当前任务文件夹，也可以告诉 Codex 使用其他位置。当前支持 Windows 10/11 x64，需要 Python 3.12 x64 和 Node.js 18.17+（含 npm），首次准备环境需要联网。详细说明见[使用指南](https://github.com/hx101700/memoflow/blob/dev/skills/asr-transcription/references/usage.md)。

## 快速开始

安装完成后，直接告诉 Codex：

```text
帮我使用工具转写录音。
```

Codex 会使用这个 Skill 打开本机转写网页。按页面提示添加录音，调整音频语言、说话人区分等设置，并选择保存位置。页面右上角可切换中文/English，以及跟随系统、浅色或深色外观。百炼认证可选择：

- **控制台登录（推荐）**：在阿里云官方网页完成授权，由 BL 管理登录凭据。
- **API Key**：在转写页面选择“使用指定 API Key”，填入或修改自己的北京地域百炼 Key，您的API Key 将会保存到当前工作目录中。

<!-- SCREENSHOT: overview
在此放实际转写页面截图，展示添加录音、转写设置和保存位置。
建议文件：doc/images/01-transcription-overview.png
配文：添加录音，按需调整转写设置。隐藏密钥和私人路径。
-->

需要提高专业词汇的识别准确率时，可以导入热词表，或填写上下文参考文本。热词指定重点识别的词语，上下文提供包含相关词语的参考文本；两种方式可以同时使用。

<!-- SCREENSHOT: enhancement
在此放热词与上下文同时启用的实际截图。
建议文件：doc/images/02-accuracy-enhancement.png
配文：为识别提供热词和上下文参考。使用公开术语和可公开的示例内容。
-->

点击“确认并预览”核对本次设置，需要调整时可返回修改。确认无误后，点击“复制给 Codex”，将复制的确认消息发回对话。Codex 会接收这份设置并开始处理；需要控制台授权时，在系统默认浏览器完成操作后回复“已完成”即可。它会等待识别和文档生成完成，给出文件及保存位置，供你检查和校对。转写会将录音及启用的增强内容发送到百炼北京地域，可能产生调用费用。

音频通过系统文件窗口选择，直接读取原文件；热词 Excel 在内存中解析。转写完成前请保留录音及原路径，只有需要合并声道时才生成处理后的音频文件。

**第二阶段（规划中）** 将根据校对稿、文档范例和格式要求生成会议纪要，并利用你确认的修改反馈改善后续结果。偏好如何保存、反馈如何采纳将在该阶段确定，当前 Skill 交付到转写校对稿。

## 参与贡献

欢迎提交 [Issue](https://github.com/hx101700/memoflow/issues)、功能建议和 PR。代码结构、开发约定与验证方法见[开发文档](https://github.com/hx101700/memoflow/blob/dev/doc/README.md)。如果能帮助到您，欢迎 **star 和 fork** 本项目，谢谢！

## 相关链接

| 资源 | 链接 |
| --- | --- |
| 阿里云百炼 | [控制台](https://bailian.console.aliyun.com/) · [官方文档](https://help.aliyun.com/zh/model-studio/) |
| 百炼 CLI | [官方主页](https://bailian.console.aliyun.com/cli) · [GitHub](https://github.com/modelstudioai/cli) |
| 识别精度增强 | [热词与上下文说明](https://help.aliyun.com/zh/model-studio/improve-asr-accuracy) |
| MemoFlow | [使用指南](https://github.com/hx101700/memoflow/blob/dev/skills/asr-transcription/references/usage.md) · [版本下载](https://github.com/hx101700/memoflow/releases) |

本项目采用 [Apache-2.0](LICENSE) 许可证。
