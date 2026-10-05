# 当前状态

更新：2026-10-05。

## 版本与工作区

当前维护目录为 `D:\Project\memoflow`。本次发布版本为 **0.1.1**，包含工作目录独立 Python/Node 和完整／轻量两种安装包；`dev` 用于后续开发，`master` 保存正式发布里程碑。发布入口：[v0.1.1 Release](https://github.com/hx101700/memoflow/releases/tag/v0.1.1)。

项目版本与根依赖锁已同步为 0.1.1。旧正式版本 v0.1.0、开发预览 dev-runtime 的标签和附件保留；用户已安装 Skill、旧项目目录和私人数据未被修改。

## 当前实现

- 首次安装由 Skill 的 `scripts/bootstrap.ps1` 准备工作目录独立 Python 3.12.10、Node.js 24.21.0（含 npm 11.19.0），再调用既有 Python bootstrap。无需预装运行时，不修改系统 PATH、注册表或全局包。
- 完整包 `asr-transcription.zip` 附带两个官方运行时归档，轻量包 `asr-transcription-lite.zip` 按需下载；两包使用相同代码和说明。业务依赖与 BL 仍需联网安装。
- 现有 venv 会核对基础 Python 绑定；旧绑定或搬迁问题明确报错并保留，按说明只重建 venv，不删除凭据和任务。
- pip 输出显式使用 UTF-8；ensurepip 的内部进程采用系统编码，按其实际编码解码后统一保存日志。HTML 使用 Git 的 LF 换行规则，避免 Windows 构建产生混合换行。
- Skill、双语 README/AGENTS、使用说明、发行说明与 UML 已核对。正式说明不再指引用户下载开发预览；历史发布资料通过 Git 标签追溯。

## 最终验证

- **446 项 Python 测试通过，0 跳过，140.569 秒**，包括真实本机 BL/npm/pip 合约及实际 ensurepip 中文路径检查。
- 严格 mypy **31 个源文件通过**；前端 **55 项测试**、Vue 类型、登录适配和页面构建通过；Edge 完整回归 **40.255 秒**通过。
- 候选完整包在无系统 Python/Node PATH 的全新中文目录完成联网安装。修正 ensurepip 后，最终两包分别通过环境复用、doctor、Tk、HTTP 启动/取消与资源只读检查。
- 两包 CRC、固定清单、源码逐字比较及 **19 份 Markdown 的 120 个本地链接**通过。完整包 52 文件，轻量包 50 文件；大小与摘要见 [ACCEPTANCE](ACCEPTANCE.md)。

## 产品边界

第一阶段仍交付单录音的原始 JSON、Word、Excel、Markdown。固定 `qwen-audio-3.1-asr-flash-filetrans`、北京地域和 BL 2.1.0。个性化纪要与反馈学习尚未实现。

编辑会话两小时，用户从预览复制含 session_id 的确认消息后交接唯一任务；必要登录后继续同一任务，失败不自动重传。音频引用原路径，Excel 在内存解析，热词与上下文在确认并预览时校验。

本机验收不替代多台全新 Windows、新 Codex 对话、人工原生窗口、真实授权/识别及 Office 逐页验收。运行环境仍受网络、权限与组织策略影响，具体边界见 [ISSUES](ISSUES.md)。
