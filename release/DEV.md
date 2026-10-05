中文 | [English](https://github.com/hx101700/memoflow/blob/dev-runtime/release/DEV.en.md)

这次开发预览让 MemoFlow 的首次安装更省事：Python 和 Node.js 会准备在当前工作目录中，不用先安装它们，也不会更改电脑上已有的版本。录音转写、网页设置和文档生成功能保持一致。

### 选择安装包

| 安装包 | 适合谁 |
| --- | --- |
| **[asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/dev-runtime/asr-transcription.zip)** | 推荐。已附带官方 Windows x64 Python 和 Node.js 压缩包，减少安装过程中再次下载运行时的等待。 |
| **[asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/dev-runtime/asr-transcription-lite.zip)** | 希望先下载较小安装包的用户。安装时从官方来源获取相同运行时。 |

两个包使用相同的 Skill 代码和说明。完整包也需要联网安装 Python 依赖与百炼 CLI；它不是完整离线安装包。安装器会核对官方运行时的摘要，后续使用工作目录内的程序路径，避免系统版本与 PATH 冲突。

### 开始使用

选一个 ZIP，与这句话一起交给 Codex：

> 请将这个 ZIP 安装为 asr-transcription Skill，阅读其中的 SKILL.md，并按说明在当前任务文件夹准备运行环境。

准备好阿里云账号及百炼服务后，告诉 Codex“帮我转写录音”，按打开的页面操作即可。支持 Windows 10/11 x64；使用步骤见[说明](https://github.com/hx101700/memoflow/blob/dev-runtime/README.md)。

这是 `dev` 的开发预览。正式版 v0.1.0 和已安装的 Skill 保持原样；正在运行任务时，请先等待任务结束再更换 Skill。旧工作目录如果仍绑定系统 Python，按安装器提示重建其中的虚拟环境，保留凭据、任务和结果。

欢迎通过 [Issues](https://github.com/hx101700/memoflow/issues)反馈安装环境、错误提示及复现步骤，请隐去密钥和私人录音内容。
