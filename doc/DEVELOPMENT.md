# 开发说明

本文说明 MemoFlow 第一阶段的职责、接口和数据生命周期。用户操作见 [usage.md](../skills/asr-transcription/references/usage.md)，对象与调用关系见 [UML](UML.md)，实际验证见 [ACCEPTANCE](ACCEPTANCE.md)。

## 业务与职责

MemoFlow 的目标是从语音生成符合用户习惯、重点要求和指定格式的会议纪要，并采用用户确认的范例与修改反馈改善后续结果。当前 `asr-transcription` Skill 实现第一阶段：把单个录音转为原始 JSON、Word、Excel 和 Markdown，交给用户校对。第二阶段的纪要生成、偏好存储及反馈学习尚未实现。

固定模型为 `qwen-audio-3.1-asr-flash-filetrans`，北京地域，BL 2.1.0 临时 OSS 上传。

| 参与者 | 职责 |
| --- | --- |
| Codex 与 Skill | 选择工作目录、打开页面、根据用户明确指定的会话交接、处理认证、执行工具并交付结果 |
| Vue 页面 | 文件选择、表格编辑、配置与预览、复制确认消息、显示结束状态 |
| Python | 管理本机会话、保存确认快照、媒体准备、调用 BL、解析结果和生成文档 |
| BL | 鉴权、临时上传、识别提交、轮询、下载与原始 JSON 落盘 |

一个完整转写任务对应一个 Skill。共享 CLI 能力集中在 `utils/bailian.py`；有独立的新 BL 用户任务时再评估拆分，当前不引入通用工具注册、云客户端、数据库或消息队列。

## 资源边界与结构

```text
frontend/                         # Vue / TypeScript 开发源码
skills/asr-transcription/          # Skill 安装资源，运行时只读
├── SKILL.md
├── agents/openai.yaml
├── scripts/
│   ├── asr.py
│   ├── requirements.txt
│   ├── bailian/
│   └── asr_runtime/
├── references/
├── assets/env.example
└── LICENSE

工作目录/
├── .asr-transcription/
│   ├── .env
│   ├── .venv/
│   ├── .tools/bailian/
│   ├── .runtime/
│   └── .state/
│       ├── bailian/
│       ├── sessions/<session_id>/
│       ├── web-uploads/<session_id>/
│       └── jobs/<job_id>/
└── transcriptions/               # 默认保存根
```

`Runtime(workspace, skill_root)` 区分用户工作目录与 Skill 资源。`resource()` 读安装资源，`path()` 定位私有运行文件，`output_root` 给出默认输出根，`check_output_path()` 保护 Skill 资源。私有运行目录与 Skill 目录互不包含。CLI 使用脚本绝对路径并显式传入同一 `--workspace`；凭据、环境、录音和任务不写回 Skill。

`SKILL.md` 的 name、description 和正文为技能入口。`agents/openai.yaml` 是可选展示元数据，scripts、references、assets 分别存放可执行工具、按需资料及模板。根 README 面向使用者，AGENTS 面向源码维护者；安装包的 README 直接取自仓库根。

## 模块职责

Python 路径相对于 `skills/asr-transcription/scripts/asr_runtime/`，前端路径相对于仓库根。

| 模块 | 职责 |
| --- | --- |
| `__main__.py` / `web.py` | CLI 与 HTTP 分派、受保护的本机控制、事件连接和服务生命周期 |
| `application/bootstrap.py` / `diagnostics.py` | 安装工作目录依赖、诊断本机条件 |
| `application/session.py` | 编辑会话、上传、预览版本、交接和副本清理 |
| `application/inputs.py` / `rules.py` | 读取输入事实、统一应用模型规则；rules 无 I/O |
| `application/transcription.py` | 一次执行、状态查询和重新导出 |
| `application/delivery.py` | 三种 writer 的顺序调用与交付汇总 |
| `utils/environment.py` / `auth.py` | Runtime、隔离进程环境和运行凭据 |
| `utils/installation.py` | 固定来源测速、pip 下载与本机安装、日志与子进程回收 |
| `utils/bailian.py` | 公开 CLI 参数映射、BL 进程、登录链接转交和脱敏错误 |
| `utils/files.py` / `job_files.py` / `session_files.py` | 文件摘要与原子替换、任务协议、会话连接与交接回执 |
| `utils/hotwords.py` / `media.py` | Excel 导入/模板、媒体探测和单声道副本 |
| `utils/results.py` / `documents.py` | 结果解析、文档生成与目标替换 |
| `utils/directory_picker.py` / `_directory_dialog.py` | 原生目录窗口、取消与子进程回收 |
| `models.py` / `utils/i18n.py` | 共享类型、请求范围的本机消息语言 |
| `frontend/App.vue` / `components/` | 两步页面与 Element Plus 输入、表格、预览、结束提示 |
| `frontend/useTranscription.ts` / `model.ts` | 页面用例编排、纯状态和输入版本 |
| `frontend/api.ts` / `types.ts` | 本机 HTTP/事件传输与协议类型 |
| `frontend/preferences.ts` / `i18n.ts` | 语言、外观偏好与文案 |

Session、DirectoryPicker 持有实际生命周期；无状态操作使用模块函数。TypedDict 和 TypeScript 接口描述数据协议，不建立重复的运行时对象层。Python 保持入口 → application → utils；utils 不反向导入用例。

## 编辑会话与执行任务

| 对象 | 何时创建 | 状态与结束 | 持久数据 |
| --- | --- | --- | --- |
| `session_id` | 启动网页服务时 | 编辑、预览；交接、取消或打开满两小时后结束 | 活动连接信息；成功交接回执 |
| `job_id` | 有效预览被代码交接时 | 配置固定；一次执行，结果与记录保留 | 配置/摘要、执行记录、文档交付记录 |

页面只负责“填写 → 预览”，往返不生成任务编号。前端完成预览展示后登记当前版本；后端可确认“当前预览已就绪”，不把成功校验直接等同页面状态。返回修改先通知后端，成功后才恢复可编辑表单。

预览有“复制给 Codex”按钮，复制明确开始请求及 `session_id`。Skill 必须从当前用户确认消息读取编号；仅“继续”不能选择会话，不从启动回执、历史或目录代替用户选择。会话编号是定位信息，保护请求的令牌是另一数据。

`confirm --session ID` 定位私有连接信息并调用受保护的本机 HTTP。Session 锁内检查截止时间、预览状态和版本，核对音频 size/mtime，生成任务编号，先保存候选回执，再写配置及摘要，最后原子发布 config.json 作为完成标记。读取回执时，只有对应配置已发布才视为交接成功；成功后配置不可修改，重复确认读取同一份回执。CLI 先读持久回执，因此响应丢失、网页服务已经结束时仍可恢复原编号。

会话有效期为从创建起固定两小时，使用一次计时器及操作时截止时间检查。到期与交接共用状态保护，只有一个终态。没有活动上报、心跳、逐次草稿保存或云端进度轮询。页面通过单向事件连接收到交接、到期或取消结果，呈现结束提示，由用户关闭标签页。

交接保留任务需要的音频和记录；取消、到期清理未提交副本，保留用户原文件和已保存的 Key。结束时移除临时连接令牌并关闭服务。已经创建的任务、登录等待和转写不受两小时编辑期限影响。关闭标签页并不能可靠地证明服务结束。

正常服务关闭先执行 Session 清理、取消目录选择，再由标准库服务器等待请求线程收尾。仍在接收的上传利用关闭标记或既有 socket 读写超时结束，并由自身 finally 清理临时文件；这不构成强制杀进程后的清理保证。

## 输入检查

| 时机 | 行为 | 消费者 |
| --- | --- | --- |
| 上传 | 名称、用途、大小、实际接收字节 | 会话音频引用或热词导入结果 |
| 预览 | 选项与增强规则、音频探测和 SHA、输出根目录 | 内存预览快照与版本 |
| 交接 | 预览就绪、截止时间、音频 size/mtime | 不可变授权配置 |
| 执行 | 配置协议/摘要、音频完整摘要、当前凭据 | 本次 BL 命令 |
| 重导 | 已保存成功记录与原始 JSON 摘要 | 固定任务目录的三种文件 |

热词从 Excel 去除表头、忽略完全空白行，保留无效单元格及原值供修正。网页行序号按当前数组从 1 连续编号，删除后重排，与用于组件复用的稳定键分开；错误定位使用当前数据位置。分页不改变编号含义。

导入、改动后整个热词区域失焦、最终整单检查都调用同一后端路径：`validate_hotword_rows()` → `build_vocabulary()`。自动检查不锁住编辑；输入版本使过期响应失效。相同文本的所有重复行报错，由用户保留一行，权重问题单独定位。没有“检查词表”按钮或检查通过标签。

上下文按 400 个 Unicode 字符及可传输字符检查，错误指出具体长度或字符位置并保留原文；本机不推断其是否与录音语义相关。热词与上下文可同时使用。Excel 只是导入来源，执行消费确认快照的 vocabulary。

输出根由默认位置或本次原生目录窗口批准；选择试写、预览和实际生成分别在各自写入边界复用 `check_output_path()`。窗口起点不可用时从工作目录打开，取消保留原路径。多声道且启用发言人区分时，按预览提示创建单声道 FLAC，保留原文件与采样率，检查新副本事实和上传大小，失败停止。

## 认证与执行

API Key 与任务快照分离。`KeyDisplay.vue` 的局部状态持有密码输入；专用受保护请求加载/保存私有 `.env`，配置只记录认证方式。预览前按需保存，执行时读取当前值。Key 不进入任务配置、日志、聊天或浏览器持久存储。

控制台模式复用当前工作目录的 BL 模型凭据；未知时查询一次本机状态，缺失才登录。两种模式的在线有效性都由实际 BL 调用判断。用户交接时已确认上传范围与可能的费用；登录完成回复“已完成”后，Codex 读取原 BL 结果并执行同一任务，不再次询问业务授权。

登录从首次调用就采用正常 Windows 桌面执行权限。`check_login_execution_context()` 拒绝已观察到会导致浏览器失败的受限令牌。固定 BL 2.1.0 的 cmd/start 会拆开 URL 中的 `&`，因此只在 console 登录预加载 `console-browser.cjs`，转交完整 URL，由 Python 系统 URL 处理器打开一次。BL 包未修改，回调和凭据由 BL 管理；BL 升级时须重新核对是否可移除此适配。

`recognition_arguments()` 统一映射 BL 选项。热词序列化为一个 JSON 参数，上下文使用一个 `--context=<原文>` 参数，子进程采用参数数组与 `shell=False`。Windows 参数长度检查和运行凭据读取各执行一次；来源见 [model.md](../skills/asr-transcription/references/model.md)。

`transcribe --job ID` 读取交接授权，核对协议与当前模型，再独占创建 execution 目录。一次任务只有一次尝试，准备失败也保留占用；重复调用读取既有状态，不自动重试。它约束本地尝试次数，不是云端恰好一次保证。启动后 Codex 持续等待同一进程，直到文档交付或明确失败。

| 字段 | 含义 |
| --- | --- |
| `CONFIGURED` | 交接配置已保存，尚未执行 |
| `PREPARING` | 已取得执行占用，最近处于本机准备 |
| `RUNNING` | 已写入启动前保守记录，不证明云端受理或进程存活 |
| `STOPPED` | 此次执行停止，以 phase 与 cloud_outcome 解释 |
| `JSON_READY` | 原始 JSON 通过结构检查 |
| `documents_ready=true` | delivery 为 COMPLETE，三格式均完成 |
| `OUTCOME_UNKNOWN` | 本机记录不足以确定结果 |
| `record_error` | 记录写入失败，磁盘可能滞后于当次回执 |

成功 JSON 记录写入失败时保留 JSON 并在导出前返回。当前没有补签摘要或恢复成功记录入口。`job-status` 只读本地记录，不查询云端或进程存活。具体状态与修复见 [errors.md](../skills/asr-transcription/references/errors.md)。

## 文档交付与路径

results 唯一解析原始 JSON，三个 writer 共用 Transcript。delivery 把 `config.model` 传给 writer，保留历史任务真实模型；依次尝试 Excel、Word、Markdown，单格式失败仍尝试其他格式。每次用同目录独立临时文件完成后替换固定目标，失败保留旧目标。Excel/Word 替换前回读，Markdown 编码保真由测试验证。

重导核对配置、磁盘 JSON_READY 及原 JSON 摘要，复用同一 writer、路径和模型，不读取音频、Excel 或 Key，也不调用 BL。每任务一份 delivery/status.json；人工校对文件应另存。

- 标题均为“源文件名（不含扩展名） 录音转写”，不另列音频信息行。
- Excel 使用等线、黑白无填充，第三行即表头；标题和任务说明左对齐，表头与非正文列居中，正文左对齐并自动换行。展示行高封顶，完整文本保留；真实存储超限时报错。
- Word 使用等线，标题 20 磅，其余正文、元信息、时间标签、页码 10 磅。时间标签无圆点，随下一段。正文标题保留完整文件名，不重复写入有限长的可选核心标题属性。

| 数据 | 位置 |
| --- | --- |
| API Key / BL 配置 | 私有运行目录 `.env` / `.state/bailian/` |
| 活动连接信息 | `.state/sessions/<session_id>/connection.json` |
| 交接回执 | 同一 session 目录的 `receipt.json` |
| 音频副本 | `.state/web-uploads/<session_id>/` |
| 配置与摘要 | `.state/jobs/<job_id>/config.json`、`config.sha256` |
| 执行 / 导出记录 | 同一 job 目录的 `execution/status.json` / `delivery/status.json` |
| 原始 JSON | `<json_root>/<job_id>/json/transcription.json` |
| 三种成品 | `<document_root>/<job_id>/documents/transcription.{xlsx,docx,md}` |

JSON 与文档默认根均为 `<workspace>/transcriptions/`，可分别选择。内容保真、识别质量与 Office 视觉效果分别验收。

## 界面和构建

页面使用 Vue 3、TypeScript、Element Plus。优先复用公开 props、插槽和默认交互；卡片、输入、表格、分页、摘要、按钮、结果及图标由组件库承担。CSS 负责布局、响应式和有限主题差异，避免复制组件交互。

偏好只保存当前来源下的界面语言与主题；随机端口变化时不保证跨会话继承。界面切换不改变音频语言、地域或输出文档格式。HTTP 请求携带界面语言，后端用请求范围语言上下文返回已登记消息。首页设置 HttpOnly、SameSiteStrict Cookie；URL 和前端状态不持有连接令牌。

Vite 将前端构建到 Skill 的 `scripts/asr_runtime/static/`，交付 index.html、app.js、app.css、favicon.svg 和第三方许可。用户不需要前端构建环境。开发 Node 要求 `^20.19.0 || >=22.12.0`，与 BL 运行所需 Node 18.17+ 分开维护。

```powershell
npm ci
npm run check:web
npm run test:web
npm run build:web
npm run build:login
npm run test:browser
```

`build:login` 从仓库 `scripts/console-browser.cts` 生成固定适配产物。浏览器回归使用 Playwright、本机 Edge 和真实 Python 本机服务；默认合成数据。Python 类型与运行检查见 [ACCEPTANCE](ACCEPTANCE.md)。

安装器按锁定版本准备 Python 依赖。先并行采样 PyPI 与阿里云镜像同一 pip wheel 前缀，排序只是当时短时吞吐，不保证全程速度。pip 自行处理有限连接重试、下载恢复与摘要检查；每阶段每源至多启动一次下载，最终失败才换源。完整 wheel 保存在私有目录，本机安装使用 `--no-index`；npm 失败停止。安装恢复不扩展为云端转写重试。

`scripts/build_zip.py` 按固定逐文件映射生成 ZIP：Skill 资源直接作为归档根，加上仓库根最新版 README.md 和 README.en.md。README 字节原样入包，仓库资料用完整 GitHub 链接，语言切换与 LICENSE 用包内链接。不维护第二份 README。排除开发 doc、AGENTS、UML、测试、Vue/TS 源码、构建工具、依赖环境、凭据和用户数据。

开发在 dev，master 用于验收里程碑。项目版本仅在通过验收并发布 master 时改变；当前及经授权更新的预览均沿用 v0.1.0。依赖版本由各自锁文件维护，历史实现和发布记录通过 Git 追溯。
