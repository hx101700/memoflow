# 当前状态

更新：2026-10-05。

## 工作区与发布边界

当前维护目录为 `D:\Project\memoflow`，开发分支为 `dev`。本轮没有修改旧目录 `D:\Project\asr-agent` 或用户已安装的 Skill。

正式版本 `v0.1.0` 对应 `master` 的 b4df5e7，正式标签与原 Skill 附件保留。本轮独立运行环境改进沿用项目版本号 0.1.0，按开发预览交付；不把 dev 的安装能力描述成原正式包已有功能。

实现提交 `8f7704d` 已推送远端 `dev`，对应[开发预览 dev-runtime](https://github.com/hx101700/memoflow/releases/tag/dev-runtime)。完整包和轻量包均已上传，远端附件大小与 SHA-256 和本机一致；正式标签及原 Skill 包保持原样。

## 本轮实现

- 首次安装由 Skill 的 `scripts/bootstrap.ps1` 准备工作目录独立 Python 3.12.10、Node.js 24.21.0（含 npm 11.19.0），再调用原有 Python bootstrap。无需预装这两个运行时，不修改系统 PATH、注册表或全局包。
- Python、Node、venv、BL 均位于工作目录 `.asr-transcription`；实际 BL 调用使用本地 Node 绝对路径。旧 venv 若仍绑定其他基础解释器，会停止并保留，按说明仅重建该 venv。
- 提供完整包 `asr-transcription.zip` 和轻量包 `asr-transcription-lite.zip`。两包代码、说明和静态页面相同；完整包另外包含两个经官方摘要校验的原始运行时 ZIP，安装时直接解压到工作目录。
- 轻量包从官方来源下载运行时，复用完整缓存和 curl 原生续传。业务依赖继续复用已有 pip/npm 选源安装，不新增识别重试。
- Skill、双语 README/AGENTS、使用说明、错误处理和 UML 01A/02 已同步。固定发行清单继续排除开发文档、测试、已安装环境、凭据及用户数据。

## 验证状态

- 新目录删除 Python/Node 的 PATH 搜索入口后，联网安装全部完成；doctor 无问题。Python 3.12.10、Node 24.21.0、BL 2.1.0 和 8 个 Python 依赖均来自工作目录。
- 新独立环境完整 Python 回归 440 项通过，无跳过；新增双包场景后，24 项 PowerShell/发行检查通过。严格 mypy 31 个源文件通过。
- 前端 55 项测试、Vue 类型检查及 Edge 网页回归通过；浏览器回归用时 49.781 秒。
- 安装日志 UTF-8 修正后的 20 项 bootstrap/pip 合约通过；中文空格路径的完整包安装成功，最终 ZIP 的环境复用、doctor、Tk、HTTP 启动/取消及 52 个资源文件只读检查通过。两包摘要见 [ACCEPTANCE](ACCEPTANCE.md)。

## 产品边界

第一阶段仍是单录音网页配置、BL 识别与原始 JSON、Word、Excel、Markdown 交付。固定 `qwen-audio-3.1-asr-flash-filetrans`、北京地域、BL 2.1.0。个性化纪要与反馈学习尚未实现。

编辑会话两小时，用户从预览复制含 session_id 的确认消息后交接唯一不可变任务；已有凭据直接执行，必要登录后继续同一任务，失败不自动重传。音频直接读取原路径，Excel 在内存解析，热词和上下文只在确认并预览时校验。

独立运行时减少版本和 PATH 冲突，不能保证任意 Windows、网络或组织策略下成功。本轮安装及本机回归不代表重新完成真实云端识别、人工原生窗口或 Office 逐页验收；限制见 [ISSUES](ISSUES.md)。
