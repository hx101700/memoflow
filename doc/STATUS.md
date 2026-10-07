# 当前状态

更新：2026-10-07。

## 当前工作

当前目录为 `D:\Project\memoflow`，分支为 `dev`。本轮准备发布 [v0.1.2](https://github.com/hx101700/memoflow/releases/tag/v0.1.2)，正式版本将在发布到 master 后生效；上一正式版本 v0.1.1 对应 master 的 c639b51。

本次本地审查删除了无业务消费者的编辑响应恢复分支、旧精度增强副标题和旧双语提示，并同步静态前端、测试与当前登录说明；审查提交已推送 dev，现进入 0.1.2 发布流程。

推送前深审已完成。现行源码、Skill、文档及 10 份 UML 的调用边界已核对，修正了图 03 的 HTTP/SSE 分派和并行关系、图 07 的原文件变化分支；本次提交同步到 dev，正式版仍按原标签管理。

## 已完成

- 新增 `serve --audio <绝对路径>`。对话附件与原生文件选择共用 `Session._register_audio()`，登记原文件；媒体检测与完整 SHA 在确认并预览时执行。
- `/api/session` 返回 `audio` 和双语 `audio_error`。页面恢复当前选择编号；初始路径无效仍可编辑，重新选择后清错；刷新和语言切换保留录音状态。
- Skill 描述、展示信息与正文覆盖附件、录音路径和转写请求，统一先网页配置与预览，再由用户交接任务。首次安装按宿主信息核对 Windows 10/11 x64。
- README 双语增加 Qwen 3.1、网页核对、Codex 协作与文件化处理的项目价值；学习能力明确为后续目标。统一导入、确认消息、API Key 和双语官方链接，删除页面旧预览版标签与重复提示。
- UML 01A、01B、03 源稿及 PNG 已同步；其余协议与图稿保持适用。

## 验证

- 推送前 Python 完整回归 **453 项通过，0 跳过，175.461 秒**；严格 mypy **31 个源文件通过**。
- 本次清理后前端 **56 项测试**、Vue 类型和 Vite 构建通过；**3 项 Edge 回归通过，44.032 秒**，覆盖有效／失效附件、替换、刷新、语言切换、预览与交接。当前静态产物与源码一致。
- 官方 Skill 格式校验和展示元数据解析通过。独立行为检查实际读取 Skill 并以附件启动服务，发起一次宿主开页请求，正确停在用户填写阶段；取消后服务退出 0。
- 两包固定清单、CRC、源码逐字比较与本机环境复用检查通过；完整包 52 文件、轻量包 50 文件，全部资源保持只读。摘要与范围见 [ACCEPTANCE](ACCEPTANCE.md)。

## 交付位置

- `dist/review-20261007/asr-transcription.zip`：附 Python 和 Node 的完整候选包。
- `dist/review-20261007/asr-transcription-lite.zip`：相同代码与说明的轻量候选包。
- 本轮原始验证记录在 `.runtime/attachments-*.json`、`.runtime/attachments-final-python.log`；仅用于本机复核，不进入 Git 或安装包。

## 产品范围

第一阶段交付单录音的原始 JSON、Word、Excel、Markdown。固定模型 `qwen-audio-3.1-asr-flash-filetrans`、北京地域和 BL 2.1.0。用户在网页填写、预览并复制含 session_id 的确认消息，随后交接唯一任务；必要登录后执行，失败不自动重传。

用户工作目录保存环境、凭据与任务，Skill 资源只读。当前功能与限制见 [HELP](HELP.md)、[ISSUES](ISSUES.md)，实现与调用关系见 [DEVELOPMENT](DEVELOPMENT.md)、[UML](UML.md)。后续个性化纪要与反馈学习尚未实现。
