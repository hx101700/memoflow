中文 | [English](https://github.com/hx101700/memoflow/blob/v0.1.2/release/NOTES.en.md)

# MemoFlow v0.1.2

MemoFlow v0.1.2 延续 v0.1.1 的独立运行环境，同时把“附上录音后开始转写”的入口接入同一套网页配置流程。你可以把录音发给 Codex，核对网页中带入的文件和设置，再交给 Codex 调用阿里云百炼完成转写。

### 这个版本的变化

- **对话附件进入配置页**：Codex 能取得本机附件路径时，会将录音带入转写页面；文件无法读取时，页面会在录音区域说明原因，仍可重新选择。
- **流程保持清晰**：网页仍是“填写 → 预览”两步。只有用户复制带 `session_id` 的确认消息后，才创建不可变任务并开始执行。
- **精度增强界面整理**：删除重复说明，保留热词和上下文输入、阿里云官方规则链接及原有表格校验。
- **登录说明同步**：固定版本的 BL 登录入口、Windows 桌面权限和浏览器打开方式已与当前实现及官方依据保持一致。
- **安装包同步更新**：完整包和轻量包均使用本版本的静态页面、Skill 指令、双语 README 和运行代码。

### 下载安装

| 安装包 | 如何选择 |
| --- | --- |
| **[asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.2/asr-transcription.zip)** | 推荐。包含 Python 和 Node.js 运行时，安装时无需再下载这两个运行时。 |
| **[asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.2/asr-transcription-lite.zip)** | 初始文件较小，首次安装时从官方来源下载运行时。 |

两个包都支持 Windows 10/11 x64。Python 依赖和百炼 CLI 的首次安装仍需联网；完整包不是完全离线安装包。

将选定的 ZIP 与下面这句话一起交给 Codex：

> 请将这个 ZIP 安装为 asr-transcription Skill，阅读其中的 SKILL.md，并按说明在当前任务文件夹准备运行环境。

使用前请准备好阿里云账号并开通百炼服务。安装后告诉 Codex“帮我转写录音”，按网页提示添加录音、调整设置、预览并复制确认消息。详细步骤见 [README](https://github.com/hx101700/memoflow/blob/v0.1.2/README.md)。

当前版本仍交付原始 JSON、Word、Excel 和 Markdown 转写稿；按用户偏好生成目标内容与反馈学习属于后续阶段。

### 从旧版本升级

先等待正在执行的任务结束，再用本 ZIP 替换已安装的 `asr-transcription` Skill，并在原工作目录重新运行 Skill 的 `scripts/bootstrap.ps1 -Workspace`。安装器会复用有效的 Python、Node、虚拟环境、百炼 CLI、凭据、任务和结果。

如果提示虚拟环境绑定了其他 Python，结束使用该环境的任务后，只删除 `WORKSPACE/.asr-transcription/.venv`，再运行 bootstrap。请保留 `.env`、`.state`、`.tools` 和输出目录，不要删除整个 `.asr-transcription`。

遇到问题欢迎提交 [Issue](https://github.com/hx101700/memoflow/issues)，附上环境、错误提示和复现步骤，并隐去 API Key、登录链接和私人录音内容。
