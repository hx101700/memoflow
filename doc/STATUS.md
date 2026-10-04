# 当前状态

更新：2026-10-04。

## 产品与入口

MemoFlow 第一阶段由 asr-transcription Skill 完成单录音网页配置、BL 识别及 JSON、Word、Excel、Markdown 交付。个性化纪要与反馈学习尚未实现。

固定模型 qwen-audio-3.1-asr-flash-filetrans，北京地域，BL 2.1.0。入口为 skills/asr-transcription/scripts/asr.py；Python 保持入口 → application → utils，前端采用 Vue、TypeScript 与 Element Plus。开发分支 dev，版本 0.1.0，master 保持 6c83711。

## 当前行为

- 网页分填写、独立预览两步。音频通过系统文件窗口选择并直接读取原路径，Excel 在内存解析，两者均不产生输入副本。Excel 导入只读取并填表；热词和上下文内容仅在点击“确认并预览”后由后端校验。错误就地提示，原值保留。编辑、导入成功、失焦和语言切换不触发内容检查。
- 只有用户在对话中提供预览页会话编号，才交接唯一不可变任务；裸“继续”不能代选会话。必要登录完成后继续同一任务，等待交付，不再询问业务授权。
- 编辑会话有效两小时。正常结束先关闭会话和目录窗口，等待 HTTP 请求线程，再清理磁盘暂存。
- 下次在同一工作目录启动 serve 时，回收已到期且原进程确定结束的会话。PID 临时文件、Python 库暂存目录按已结束进程回收。正式凭据、已交接输入、mono.flac、JSON、成品及执行占用保留。
- Key 继续由 dotenv 更新，工作副本位于会话目录。无法确认归属或进程状态的文件保留并提示；不扫描系统 Temp，也不自动重传识别。
- ZIP 按固定清单交付运行代码、前端产物、参考资料和仓库最新双语 README，不包含开发 doc、UML、测试、环境或用户数据。

## 相关代码与资料

会话及回收：application/session.py、application/recovery.py、web.py、utils/session_files.py。写入归属：utils/files.py、documents.py、auth.py、environment.py、job_files.py。前端由 useTranscription.ts 编排，热词由 HotwordEditor.vue 展示。

使用指令为 SKILL.md 和 references；架构、文件生命周期、UML 与验证分别见 DEVELOPMENT、UML、ACCEPTANCE。

## 本轮验证与交付

404 项 Python 测试通过（88.437 秒），无跳过；43 项前端测试、严格 mypy 31 个源文件、Vue 类型检查及 Vite 构建通过。Edge 完整页面验收通过（12.324 秒），验证内容只在预览按钮触发检查，以及原路径音频选择、Key 保存、交接、服务关闭与重复回执。

真实测试子进程被强制结束后，再次开页回收 Key 工作副本和 Python 暂存，所选原录音保留。测试使用实际服务进程句柄，避免仅结束 Windows venv 启动器。活进程、未知状态、未到期、已交接数据及正式凭据均有保留检查。

本轮未执行真实云端识别、真实登录、原生目录窗口人工操作、Office 逐页检查或全新联网安装。已安装 Skill 和真实工作目录保持原样。发行包及远端同步待最终核对，继续沿用 v0.1.0 预览。

发行包已核对：48 文件、338972 字节，SHA-256 `e24f48f040e551f7599b4e9b2759ce94d2e9dd408f17717e506e54848dfc2292`。CRC、固定清单及源码逐文件字节一致；远端同步待完成。
