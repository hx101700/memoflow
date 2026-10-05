中文 | [English](https://github.com/hx101700/memoflow/blob/v0.1.1/release/NOTES.en.md)

MemoFlow v0.1.1 简化了首次安装：不必提前配置 Python 和 Node.js，Codex 会按 Skill 指引在当前工作目录准备独立环境。电脑上已有的 Python、Node 和其他项目环境保持原样。

### 这个版本的变化

- **独立运行环境**：Python、Node、百炼 CLI 和依赖分别安装在工作目录内，减少版本不兼容和 PATH 冲突。
- **两种安装包**：完整包附带经过官方摘要校验的 Python、Node 压缩包；轻量包在安装时下载相同运行时。两者使用同一份 Skill 代码和说明。
- **安装恢复与诊断**：轻量包保留未完成下载供续传；已有环境会先检查基础 Python 绑定，发现旧环境或路径变化时给出处理说明并保留数据。
- **中文路径**：修复 pip 安装日志中的中文乱码，中文及带空格的工作目录可正常显示。

录音转写的使用方式保持一致：在网页添加录音、调整热词与上下文，预览后将确认消息发给 Codex，由它调用百炼并生成 Word、Excel、Markdown 和原始 JSON。

### 下载安装

| 安装包 | 如何选择 |
| --- | --- |
| **[asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.1/asr-transcription.zip)** | 推荐。已包含 Python 和 Node.js，安装时无需再下载这两个运行时。 |
| **[asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.1/asr-transcription-lite.zip)** | 初始文件较小，首次安装时从官方来源下载运行时。 |

两个包都支持 Windows 10/11 x64，仍需联网安装 Python 依赖和百炼 CLI。完整包不是完全离线安装包。

将选定的 ZIP 与这句话一起交给 Codex：

> 请将这个 ZIP 安装为 asr-transcription Skill，阅读其中的 SKILL.md，并按说明在当前任务文件夹准备运行环境。

使用前请准备好阿里云账号并开通百炼服务。安装后说“帮我转写录音”，按打开的页面操作即可。详细步骤见 [README](https://github.com/hx101700/memoflow/blob/v0.1.1/README.md)。

### 从旧版本升级

先等待正在执行的任务结束，再更换 Skill。若原工作目录的虚拟环境仍绑定系统 Python，按安装器提示只重建其中的 `.asr-transcription/.venv`，保留凭据、任务和转写结果。不要删除整个工作目录。

遇到问题欢迎提交 [Issue](https://github.com/hx101700/memoflow/issues)，附上环境、错误提示和复现步骤，并隐去密钥及私人录音内容。
