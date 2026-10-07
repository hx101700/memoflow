# 当前状态

更新：2026-10-08。

## 当前工作

本轮为双语 README 加入用户提供的 Codex 操作截图与当前配置、预览、交接三张网页效果图。网页效果图使用演示数据，按当前静态前端完整渲染后截图，不代表云端识别验收；服务已通过 cancel 正常结束。图片保存在 `assets/screenshots/`，README 使用完整 GitHub 图片地址，两包继续不附带介绍图。

原图副本与用户提供的 PNG 字节一致；三张网页图无横向溢出、没有显示 API Key 输入。双语四图引用一致、14 项打包测试及本地文档链接检查通过。业务代码与正式标签、附件未改动。

当前目录为 `D:\Project\memoflow`，分支为 `dev`。按当前发布策略，本轮代码作为唯一正式版本 [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0) 维护。

本轮按用户最新 README 统一“个性化纪要生成”，核对 Skill、运行源码、前端、参考资料和 UML 的用词。双语 README 图使用圆角节点与平滑连线，保留九个节点和九条关系；代码只调整文案及职责说明，业务行为、协议和依赖保持原样。

Release 使用“更新内容”，完整包标为“推荐”，删除重复的两包说明。本轮不移动正式 v0.1.0 标签或替换原附件；当前候选包在 `dist/terminology-review/`，用于复核修改。

本轮验证：181 项针对性 Python、56 项前端、3 项 Edge 回归通过；严格 mypy 31 个源文件、Vue 类型与构建、官方 Skill 格式、文档链接及双包一致性检查通过。GitHub 视觉工具因无法确认浏览器 URL 停止，图表按用户截图改进，并完成本地深浅主题渲染；未声称已完成 GitHub 实际视觉验证。详见 [ACCEPTANCE](ACCEPTANCE.md)。

## 已完成

- 新增 `serve --audio <绝对路径>`。对话附件与原生文件选择共用 `Session._register_audio()`，登记原文件；媒体检测与完整 SHA 在确认并预览时执行。
- `/api/session` 返回 `audio` 和双语 `audio_error`。页面恢复当前选择编号；初始路径无效仍可编辑，重新选择后清错；刷新和语言切换保留录音状态。
- Skill 描述、展示信息与正文覆盖附件、录音路径和转写请求，统一先网页配置与预览，再由用户交接任务。首次安装按宿主信息核对 Windows 10/11 x64。
- README 双语增加 Qwen 3.1、网页核对、Codex 协作与文件化处理的项目价值；学习能力明确为后续目标。统一导入、确认消息、API Key 和双语官方链接，删除页面旧预览版标签与重复提示。
- UML 01A、01B、03 源稿及 PNG 已同步；其余协议与图稿保持适用。

## 上次完整回归

- 推送前 Python 完整回归 **453 项通过，0 跳过，175.461 秒**；严格 mypy **31 个源文件通过**。
- 本次清理后前端 **56 项测试**、Vue 类型和 Vite 构建通过；**3 项 Edge 回归通过，44.032 秒**，覆盖有效／失效附件、替换、刷新、语言切换、预览与交接。当前静态产物与源码一致。
- 官方 Skill 格式校验和展示元数据解析通过。独立行为检查实际读取 Skill 并以附件启动服务，发起一次宿主开页请求，正确停在用户填写阶段；取消后服务退出 0。
- 两包固定清单、CRC、源码逐字比较与本机环境复用检查通过；完整包 52 文件、轻量包 50 文件，全部资源保持只读。摘要与范围见 [ACCEPTANCE](ACCEPTANCE.md)。

## 交付位置

- `dist/terminology-review/asr-transcription.zip`：本轮完整候选包。
- `dist/terminology-review/asr-transcription-lite.zip`：本轮轻量候选包。
- 本轮原始验证记录在 `.runtime/attachments-*.json`、`.runtime/attachments-final-python.log`；仅用于本机复核，不进入 Git 或安装包。

## 产品范围

第一阶段交付单录音的原始 JSON、Word、Excel、Markdown。固定模型 `qwen-audio-3.1-asr-flash-filetrans`、北京地域和 BL 2.1.0。用户在网页填写、预览并复制含 session_id 的确认消息，随后交接唯一任务；必要登录后执行，失败不自动重传。

用户工作目录保存环境、凭据与任务，Skill 资源只读。当前功能与限制见 [HELP](HELP.md)、[ISSUES](ISSUES.md)，实现与调用关系见 [DEVELOPMENT](DEVELOPMENT.md)、[UML](UML.md)。后续个性化纪要生成与反馈学习尚未实现。
