# 开发说明

本文说明 MemoFlow 第一阶段的职责、接口和数据生命周期。用户操作见 [usage.md](../skills/asr-transcription/references/usage.md)，对象与调用关系见 [UML](UML.md)，实际验证见 [ACCEPTANCE](ACCEPTANCE.md)。

## 业务与职责

MemoFlow 的目标是从语音生成符合用户习惯、重点要求和指定格式的纪要，并采用用户确认的范例与修改反馈改善后续结果。当前 `asr-transcription` Skill 实现第一阶段：把单个录音转为原始 JSON 和 Word、Excel、Markdown 转写校对稿。第二阶段的个性化纪要生成、偏好存储及反馈学习仍在开发中，当前代码尚未实现。

固定模型为 `qwen-audio-3.1-asr-flash-filetrans`，北京地域，使用官方百炼 CLI（BL）`2.4.0` 临时 OSS 上传。CLI、core、commands、runtime 均由 npm 锁定官方版本。版本比较及升级取舍见 [BL_COMPATIBILITY](BL_COMPATIBILITY.md)。

| 参与者 | 职责 |
| --- | --- |
| Codex 与 Skill | 选择工作目录、将本次录音带入页面、根据用户确认消息提交设置、处理认证、执行工具并交付结果 |
| Vue 页面 | 文件选择、表格编辑、配置与预览、复制确认消息、显示结束状态 |
| PowerShell 安装入口 | 校验包内或下载的 Python/Node 归档，在工作目录解压并调用 Python 安装入口 |
| Python | 管理本机会话、保存确认快照、媒体准备、调用 BL、解析结果和生成文档 |
| BL | 鉴权、临时上传、识别提交、轮询、下载与原始 JSON 落盘 |

一个完整转写任务对应一个 Skill。共享 CLI 能力集中在 `utils/bailian.py`；有独立的新 BL 用户任务时再评估拆分，当前不引入通用工具注册、云客户端、数据库或消息队列。

## 资源边界与结构

```text
frontend/                         # Vue / TypeScript 开发源码
skills/asr-transcription/          # Skill 安装资源，业务运行时只读
├── SKILL.md
├── agents/openai.yaml
├── scripts/
│   ├── asr.py
│   ├── update.py                 # 独立标准库更新入口
│   ├── bootstrap.ps1
│   ├── runtimes.json
│   ├── requirements.txt
│   ├── bailian/
│   └── asr_runtime/
├── references/
├── assets/
│   ├── env.example
│   ├── update.lock               # 稳定只读哨兵，更新时保留
│   └── runtimes/                  # 完整发行包内的两个官方ZIP
├── skill-manifest.json           # 构建时生成的版本与受管文件清单
└── LICENSE

工作目录/
├── .asr-transcription/
│   ├── .env
│   ├── .venv/
│   ├── .tools/
│   │   ├── python/
│   │   ├── node/
│   │   └── bailian/
│   ├── .runtime/
│   └── .state/
│       ├── bailian/
│       ├── sessions/<session_id>/
│       └── jobs/<job_id>/
└── transcriptions/               # 默认保存根
```

`Runtime(workspace, skill_root)` 区分用户工作目录与 Skill 资源。`resource()` 读安装资源，`path()` 定位私有运行文件，`output_root` 给出默认输出根，`check_output_path()` 保护 Skill 资源。私有运行目录与 Skill 目录互不包含。CLI 使用脚本绝对路径并显式传入同一 `--workspace`；凭据、环境、录音和任务不写回 Skill。

`SKILL.md` 的 name、description 和正文为技能入口。`agents/openai.yaml` 是可选展示元数据，scripts、references、assets 分别存放可执行工具、按需资料及模板。根 README 面向使用者，AGENTS 面向源码维护者；安装包的 README 直接取自仓库根。

现行用户文案统一使用“说话人区分”（speaker diarization）、“上下文增强”（context enhancement）、“API Key”和“百炼 CLI（BL）”（Bailian CLI）。前端“精度增强”（Recognition enhancements）栏目包含热词与上下文增强。网页编辑会话使用 `session_id`，交接后转写任务使用 `job_id`；第一阶段成品称“转写校对稿”（transcript drafts），第二阶段称“个性化纪要生成”（personalized minutes generation）。官方名称、协议字段和标识按原样保留；“说话人分离”作为官方术语对照。

## 模块职责

Python 模块路径相对于 `skills/asr-transcription/scripts/asr_runtime/`，前端路径相对于仓库根。前置安装入口是 Skill 内 `scripts/bootstrap.ps1`，它读取同级 `runtimes.json`，完成基础运行时准备后调用现有 Python CLI。

| 模块 | 职责 |
| --- | --- |
| `__main__.py` / `web.py` | CLI 与 HTTP 分派、受保护的本机控制、事件连接和服务生命周期 |
| `application/bootstrap.py` / `diagnostics.py` | 安装工作目录依赖、诊断本机条件 |
| `application/session.py` | 编辑会话、附件与原生窗口共用音频登记、内存热词导入、预览与交接 |
| `application/recovery.py` | 正常关闭及下次开页时回收可确认归属的临时文件 |
| `application/inputs.py` / `rules.py` | 读取输入事实、统一应用模型规则；rules 无 I/O |
| `application/transcription.py` | 一次执行、状态查询和重新导出 |
| `application/delivery.py` | 三种 writer 的顺序调用与交付汇总 |
| `utils/environment.py` / `auth.py` | Runtime、隔离进程环境和运行凭据 |
| `utils/installation.py` | Python/npm 固定来源测速、安装进度与结构化输出、子进程回收 |
| `utils/bailian.py` | 公开 CLI 参数映射、BL 进程和脱敏错误 |
| `utils/files.py` / `job_files.py` / `session_files.py` | 文件摘要与原子替换、任务协议、会话连接与交接回执 |
| `utils/hotwords.py` / `media.py` | Excel 导入/模板、媒体探测和单声道副本 |
| `utils/results.py` / `documents.py` | 结果解析、文档生成与目标替换 |
| `utils/path_picker.py` / `_path_dialog.py` | 原生文件/目录窗口、共享取消与子进程回收 |
| `models.py` / `utils/i18n.py` | 共享类型、请求范围的本机消息语言 |
| `frontend/App.vue` / `components/` | 两步页面与 Element Plus 输入、表格、预览、结束提示 |
| `frontend/useTranscription.ts` / `model.ts` | 页面用例编排、纯状态和操作权限 |
| `frontend/api.ts` / `types.ts` | 本机 HTTP/事件传输与协议类型 |
| `frontend/preferences.ts` / `i18n.ts` | 语言、外观偏好与文案 |

Session、PathPicker 持有实际生命周期；无状态操作使用模块函数。TypedDict 和 TypeScript 接口描述数据协议，不建立重复的运行时对象层。Python 保持入口 → application → utils；utils 不反向导入用例。

## 编辑会话与转写任务

| 对象 | 何时创建 | 状态与结束 | 持久数据 |
| --- | --- | --- | --- |
| 编辑会话 `session_id` | 启动网页服务时 | 编辑、预览；交接、取消或打开满两小时后结束 | 活动连接信息；成功交接回执 |
| 转写任务 `job_id` | 有效预览被代码交接时 | 配置固定；一次执行，结果与记录保留 | 配置/摘要、执行记录、文档交付记录 |

页面只负责“填写 → 预览”，往返不生成任务编号。前端完成预览展示后登记当前版本；后端可确认“当前预览已就绪”，不把成功校验直接等同页面状态。返回修改先通知后端，成功后才恢复可编辑表单。

预览有“复制给 Codex”按钮，复制明确开始请求及 `session_id`。Skill 必须从当前用户确认消息读取编号；仅“继续”不能选择会话，不从启动回执、历史或目录代替用户选择。会话编号是定位信息，保护请求的令牌是另一数据。

`confirm --session ID` 定位私有连接信息并调用受保护的本机 HTTP。Session 锁内检查截止时间、预览状态和版本，核对音频 size/mtime，再按本次任务编号、音频及结果路径检查完整 Windows 命令长度。通过后先保存候选回执，再写配置及摘要，最后原子发布 config.json 作为完成标记。长度超限时保留预览供返回修改，不创建任务文件。读取回执时，只有对应配置已发布才视为交接成功；成功后配置不可修改，重复确认读取同一份回执。CLI 先读持久回执，因此响应丢失、网页服务已经结束时仍可恢复原编号。

会话有效期为从创建起固定两小时，使用一次计时器及操作时截止时间检查。到期与交接共用状态保护，只有一个终态。没有活动上报、心跳、逐次草稿保存或云端进度轮询。页面通过单向事件连接收到交接、到期或取消结果，呈现结束提示，由用户关闭标签页。

音频从本次附件或系统文件窗口登记的原路径读取，Excel 仅在内存解析；交接保存参数与来源引用。取消、到期只清理会话临时记录，原文件和已保存 Key 保留。结束时移除临时连接令牌并关闭服务。已经创建的任务、登录等待和转写不受两小时编辑期限影响。关闭标签页并不能可靠地证明服务结束。

### 临时文件回收

正常关闭依次执行：`Session.cleanup()` 设置关闭状态并取消原生选择窗口 → HTTP 服务器等待请求线程结束 → `recovery.finish_session()` 回收磁盘暂存。热词接收在内存中完成；writer 的 finally 先处理自身临时文件，统一回收发生在请求线程结束后。

若服务被强制终止，退出清理可能没有运行。下次同一工作目录启动 `serve` 时，`recover_workspace()` 读取有效任务配置以定位文档临时文件，并回收满足条件的会话残留。会话须同时达到原两小时截止时间、所属进程已确认结束；进程仍存活或状态未知时保留对应临时文件，任务配置不可读时保留该任务的文件。进程编号复用时也按仍存活处理。它是开页前的一次检查，不是后台定时任务，也不恢复或重传识别。

| 文件类别 | 处理与依据 |
| --- | --- |
| 输入音频与热词 Excel | 音频直接读取原路径；Excel 内存解析；不产生输入文件副本，原文件不属于清理范围 |
| 未发布配置与候选回执 | 按所属会话清理 config.json.tmp、config.sha256、候选 receipt；存在执行/交付记录或其他归属异常时保留 |
| 会话内 Key 暂存 | .env 及 python-dotenv 的同目录临时文件随会话回收；正式运行根 .env 始终保留 |
| JSON / 文档原子写入临时文件 | 文件名记录 PID。下次 serve 只删除所属进程已结束的临时文件，保留正式 status.json 和成品 |
| Python 库临时目录 | serve、transcribe、export 使用私有 .runtime/tmp/python-PID-随机值，正常退出清理；死进程目录在下次 serve 回收 |
| 原录音、mono.flac、原始 JSON、成品、任务与执行占用 | 保留，供执行、核对、状态查询或重导 |
| 正式 API Key、BL 凭据、安装包缓存及无归属旧文件 | 保留；不扫描系统 Temp 或任意用户目录 |

`connection.json` 保存 port、token、pid、deadline，既用于本机控制，也提供会话回收依据。启动回执的 `cleanup` 返回已回收数量和警告；正常关闭未能完全清理时输出 `cleanup_warning`。会话记录不全、权限不足或会话目录含未知文件时保留并报告；不属于本工具命名规则的旧临时文件保持原样。

`process_is_running()` 通过 Windows 进程句柄作即时状态查询，权限不足返回未知；不枚举整机进程、不终止别的进程。依据见 [model.md](../skills/asr-transcription/references/model.md#本机进程与临时文件)。

## 输入检查

`serve --audio <绝对路径>` 可将用户本次提供的录音路径或宿主明确标注的附件路径带入配置页；CLI 将 Path 传给 `web.serve()`、`create_server()` 和 `Session`。没有路径时打开空表单，多个附件未指定时由用户选择本次处理的一个。

`Session._register_audio()` 供初始路径与 `select_audio()` 共用：规范原路径、核对文件和扩展名、读取大小并建立 `AudioSelection`，替换选择时清除旧预览和初始错误。初始路径读取失败转换为 `LocalizedText`，会话继续处于填写状态。`/api/session` 的 `audio: AudioSelection | null` 与 `audio_error: LocalizedText | null` 让页面加载或刷新后显示当前录音及原因；前端用现有选中反馈与更换入口，语言切换只重新选择错误文本。

浏览器普通文件输入不提供原始完整路径，参见 [MDN 文件输入说明](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/file)。手动更换文件由 PathPicker 取得真实路径，再调用同一登记方法，页面只提交 audio_id。音频与目录共用一个选择器及取消入口。媒体探测与 SHA 基线在预览时建立，原录音在转写完成前保持可访问；只有声道合并创建 mono.flac。

| 时机 | 行为 | 消费者 |
| --- | --- | --- |
| 登记录音 | 本次附件路径或系统窗口返回路径，统一检查文件位置与格式、读取大小并登记 audio_id | 原文件引用与页面展示 |
| 导入热词 | 有界接收 Excel 字节，在内存读取工作表 | 热词数据数组 |
| 预览 | 选项与增强规则、音频探测和 SHA、输出根目录 | 内存预览快照与版本 |
| 交接 | 预览就绪、截止时间、音频 size/mtime、实际 Windows 命令长度 | 不可变授权配置 |
| 执行 | 配置协议/摘要、音频完整摘要、当前凭据 | 本次 BL 命令 |
| 重导 | 已保存成功记录与原始 JSON 摘要 | 固定任务目录的三种文件 |

热词从 Excel 去除表头、忽略完全空白行，保留无效单元格及原值供修正。网页行序号按当前数组从 1 连续编号，删除后重排。后端错误的行号在接收时绑定组件稳定键；后续删行时，提示随原词条保留。表格最大高度为 420px，更多行在组件内滚动，表头保持可见。

Excel 使用 BytesIO 在内存读取并填充数据数组，文件不可读、表头或结构不符时提示导入问题。热词与上下文内容仅在点击“确认并预览”后通过 `/api/validate` 校验：热词调用 `validate_hotword_rows()` → `build_vocabulary()`，上下文调用 `validate_context()`。编辑、导入成功、失焦和语言切换均不触发内容校验。相同文本的重复行与权重问题在最终检查后定位标红；输入原值保留供修改。

检查期间保留表单及摘要，只暂时禁用输入、导入和选择操作；成功后展示这次输入的预览，失败后恢复编辑。主表单不维护额外修订计数，也不因检查期间的变动自动请求返回编辑。真正发出下一次 `/api/validate` 前替换旧词表诊断，保留数据、稳定行键和导入记录；新响应显示当次结果。Key 异步读取仍保留独立版本，用于丢弃认证方式切换后的迟到响应。

编辑单元格只清除该格已过时的诊断。重复错误带本次检查的 `duplicate_group`；修改词语或删行后，组内仍有两条以上未改词语时保留红标，剩一条才移除重复提示。该处理维护已有检查结果，不在前端重新实现热词规则；新内容仍在下次预览时检查。导入失败保留原表格和原有行错误。

上下文文本按 400 个 Unicode 字符及可传输字符检查，错误指出具体长度或字符位置并保留原文；本机不推断其是否与录音语义相关。热词与上下文增强可同时使用，关闭对应开关清空该区域的内容和提示。API Key 的显示、保存与认证选择独立。Excel 只是导入来源，执行消费确认快照的 vocabulary。

输出根由默认位置或本次原生目录窗口批准；选择试写、预览和实际生成分别在各自写入边界复用 `check_output_path()`。窗口起点不可用时从工作目录打开，取消保留原路径。多声道且启用说话人区分时，按预览提示创建单声道 FLAC，保留原文件与采样率，检查新副本事实和上传大小，失败停止。

## 认证与执行

API Key 与任务快照分离。`KeyDisplay.vue` 的局部状态持有密码输入；专用受保护请求加载/保存私有 `.env`，配置只记录认证方式。网页可以单独保存 Key，预览前按需保存未提交的修改，执行时读取当前值。保存复用 python-dotenv，在会话目录的 .env 副本完成修改后替换正式 .env，使中断残留具有明确归属。Key 不进入任务配置、日志、聊天或浏览器持久存储。

控制台模式复用当前工作目录的 BL 模型凭据；未知时查询一次本机状态，缺失才登录。两种模式的在线有效性都由实际 BL 调用判断。用户交接时已确认上传范围与可能的费用；登录完成回复“已完成”后，Codex 读取原 BL 结果并执行同一任务，不再次询问业务授权。

登录从首次调用就采用正常 Windows 桌面执行权限。`check_login_execution_context()` 拒绝已观察到会导致浏览器失败的受限令牌。官方 BL 2.4.0 的 `buildOpenInvocation()` 使用 Windows 命令引用和 `windowsVerbatimArguments` 保留完整 URL；Python 直接调用 `bl auth login --console`，由 BL 打开系统默认浏览器、等待回调并保存凭据。

`recognition_arguments()` 统一映射 BL 选项。热词序列化为一个 JSON 参数，上下文使用一个 `--context=<原文>` 参数，子进程采用参数数组与 `shell=False`。交接与执行准备复用同一个命令构造和长度检查；前者允许用户在生成任务前修正超长输入，后者核对即将启动的实际命令。交接不读取 Key 或启动 BL，运行凭据只在执行准备时读取。固定 BL 2.4.0 的即时热词参数仅接受 JSON 文本，没有文件或标准输入入口；规则允许的 2000 条热词不保证都能装入 Windows 的完整命令。来源见 [model.md](../skills/asr-transcription/references/model.md)。

官方 core 的 `Client.uploadFile()` 将已解析的 `settings.timeout` 经 `resolveFileUrl()`、`UploadOptions`、`uploadFile()` 传给 `uploadToOSS()`；上传计时器使用该秒数，获取上传凭证仍为15秒。core 的 JSON 请求期限覆盖响应头与 JSON 正文，并在 Node 请求中关闭较短的 undici headers/body 默认期限。上传、提交、轮询、下载与 `--out` 保存均使用官方包。

`WAIT_SECONDS=3600` 用于上传、提交和单次查询；BL 轮询也以该值建立总截止时间，轮询间隔为5秒。`PROCESS_SECONDS=WAIT_SECONDS*2+300=7500` 限制整个 BL 子进程，给上传和轮询各一小时及300秒余量；结果下载没有独立 BL 时限。各阶段可累积，整体上限不是每次请求时限或云端完成保证。`Request timed out.` 是多种请求超时的统一文本，不能从录音大小推断历史失败阶段；未知云端结果仍维持一次尝试约束。本机合约与真实云端验收分开记录。

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
| 音频来源 | 本次对话附件或用户通过系统窗口选择的原始绝对路径，任务只保存引用 |
| 热词来源 | 浏览器发送的 Excel 字节在内存读取，任务保存词典 |
| 配置与摘要 | `.state/jobs/<job_id>/config.json`、`config.sha256` |
| 执行 / 导出记录 | 同一 job 目录的 `execution/status.json` / `delivery/status.json` |
| 原始 JSON | `<json_root>/<job_id>/json/transcription.json` |
| 三种成品 | `<document_root>/<job_id>/documents/transcription.{xlsx,docx,md}` |

JSON 与文档默认根均为 `<workspace>/transcriptions/`，可分别选择。内容保真、识别质量与 Office 视觉效果分别验收。

## Skill 自动更新

更新是安装维护能力，由 `scripts/update.py` 独立完成，使用 Python 标准库，不依赖待更新的业务模块和 pip 包。Codex 在开始新的使用时直接用工作目录的基础 `.tools/python/python.exe -I -X utf8` 调用；更新入口不接收 `--workspace`，也不要求 `.venv` 完好。版本判断和下载由代码执行。更新源固定为 `hx101700/memoflow` 的最新正式 Release，不跟随 dev 或同版本内容替换。

`scripts/build_zip.py` 将根 package.json 的版本与固定运行文件列表写入两包相同的 `skill-manifest.json`。该清单只记录受管路径，不包含用户资料、开发文件、运行时归档、自身或稳定哨兵。最新版本号高于本地时，更新器下载 Release 的轻量 ZIP，核对 API 返回的文件大小及可用的 SHA-256，再核对包内版本和路径集合；逐个读取文件的 ZIP CRC 检查全部完成后才替换。文件直接覆盖、不备份；旧清单独有的文件删除，清单外的文件保留，最后发布新清单。

`.skill-update-state.json` 位于安装目录，记录 `checked_on`、结果和必要的覆盖状态，同一 Skill 的多个工作目录共享。日期使用 `date.today()`，在首次网络请求前保存。检查成功、没有更新或网络失败后，当天调用均读取缓存；忙时暂缓尚未联网，不记为检查。没有后台定时器、失败重试循环或额外通知进程。

最终日检记录保存失败通过 `record_error` 单独返回，保留本次实际状态及安装版本；已发布的新清单是文件更新完成的依据。下次遇到残留 `applying` 但清单已是目标版本时，当天缓存按已完成更新解释。回执只提供版本、结果和必要错误，不反复输出整份文件路径或重复状态布尔字段。

用户主动检查传 `--check-now`，由同一 `update_skill(check_now=True)` 越过日内缓存，其结果覆盖当天记录，后续自动检查不再联网。两种入口共用锁、下载与覆盖方法。程序通过 stderr 提供检查、版本和下载进度，stdout 返回最终 JSON；Skill 要求 Codex 在检查前、发现新版和完成后向用户提供文字说明。正文提前断开产生的 `IncompleteRead` 转为下载失败回执，保留旧文件与当日日检记录。

`asr.py` 在导入业务模块前经 `skill_in_use()` 只读打开 `assets/update.lock`，共享句柄保持到命令结束。更新器用 Windows `CreateFileW` 的 share=0 独占同一文件，任何工作目录的活动页面、登录或识别都使更新暂缓；新命令遇到正在更新时明确停止。句柄由进程退出释放，不持久记录活动 PID。哨兵不在覆盖或删除清单中。

此处的 Skill 写入仅限更新器的状态、同目录暂存和发行清单管理的资源。下载或预检失败保留原代码；覆盖前将本次目标的原内容存入内存，记录实际修改项与新建目录。覆盖出错时按逆序恢复或删除对应文件，清理新目录；正常退出清理暂存，不保留磁盘备份。当天检查记录保留。恢复本身失败或进程被强行中断时，`applying` 与最后发布的版本清单使入口准确报告未完成状态，不能声称已回退。任务、结果与凭据在独立工作目录，不参与覆盖。

更新后 Codex 重新读取 SKILL.md，并调用原 bootstrap 准备本次目录依赖；BL 版本冲突继续使用现有定点修复，不新增第二个依赖安装器。其他工作目录按当前依赖要求分别准备。

用户提供新 ZIP 的重新安装由 Codex 使用文件工具完成：先核对完整新包，等待该 Skill 安装的全部命令结束，确认专用资源目录与用户工作目录分离，再用新包重建资源目录。此步骤清除旧代码、旧资源与旧检查记录，适用于没有发行清单的旧安装；非 Skill 文件先核对归属。它不会清理独立工作目录中的环境、凭据、任务或输出。自动更新仍复用当前清单的受管文件覆盖，不增加第二个安装器。

这属于 MemoFlow 的安装更新协议。[OpenAI Skill 文档](https://learn.chatgpt.com/docs/build-skills)说明 Skill 的脚本与资源结构，并推荐使用插件分发可复用能力；[工作区插件管理](https://learn.chatgpt.com/docs/enterprise/plugin-management)的每日市场同步由宿主管理。普通 ZIP Skill 的每日下载覆盖不是该平台保证，本项目通过上述入口实现。旧安装需先用包含该入口和清单的新 ZIP 更新；发布者只需继续提供两个 ZIP，不新增独立清单附件。

## 界面和构建

页面使用 Vue 3、TypeScript、Element Plus。优先复用公开 props、插槽和默认交互；卡片、输入、表格、滚动、摘要、按钮、结果及图标由组件库承担。CSS 负责布局、响应式和有限主题差异，避免复制组件交互。

偏好只保存当前来源下的界面语言与主题；随机端口变化时不保证跨会话继承。界面切换不改变表格、滚动位置、预览版本、音频语言、地域或输出文档格式。网页错误及警告使用 `LocalizedText={zh,en}`，动态参数在后端一次生成两种文字，页面按当前语言呈现，无需重发请求或重新校验。HTTP 的界面语言只用于原生窗口、模板示例等当次呈现；CLI 异常仍为可打印文本。首页设置 HttpOnly、SameSiteStrict Cookie；URL 和前端状态不持有连接令牌。

音频使用大块 `ElButton` 打开原生文件窗口，规格说明位于框内；选中反馈使用绿色文件图标与 success 标签，选择框保持中性背景；等待使用原生 v-loading 遮罩。Excel 使用 `ElUpload` 的按钮入口在内存导入，与下载模板并排。热词编辑使用 `ElTable` 与 `ElInput`，表尾添加入口使用公开的 `append` 插槽。错误标红通过 `row-class-name`；组件原有聚焦、禁用、滚动和主题行为保持一致。

Vite 将前端构建到 Skill 的 `scripts/asr_runtime/static/`，交付 index.html、app.js、app.css、favicon.svg 和第三方许可。用户不需要前端构建环境。开发 Node 要求由根 package.json 的 `^20.19.0 || >=22.12.0` 约束；Skill 使用固定 Node 24.21.0，满足该条件。开发命令在已有开发环境中执行：

```powershell
npm ci
npm run check:web
npm run test:web
npm run build:web
npm run test:browser
```

浏览器回归使用 Playwright、本机 Edge 和真实 Python 本机服务；默认合成数据。Python 类型与运行检查见 [ACCEPTANCE](ACCEPTANCE.md)。

首次安装使用完整版，由 Windows PowerShell 执行 `scripts/bootstrap.ps1 -Workspace`，核对 `scripts/runtimes.json` 中的固定摘要，再从包内 `assets/runtimes` 解压原始 ZIP 到工作目录 `.asr-transcription/.tools/python` 和 `.tools/node`。Python 为安装管理器的完整 ZIP，含 Tk、venv 和 ensurepip；Node ZIP 含配套 npm。PowerShell 随后用私有 Python 调用现有 `asr.py --workspace ... bootstrap`，pip/npm 依赖安装仍由 Python 用例负责。

后续自动下载轻量包，保留已安装运行时；依赖准备直接由现有基础 Python 进入同一个 Python bootstrap，不重复走运行时准备。npm 的位置由私有 Node 目录派生，使用该 Node 执行 npm-cli.js。源码安装或显式恢复缺少包内归档时，原 PowerShell 工具仍支持工作目录缓存和官方来源下载；此分支不属于正常轻量更新。

运行命令始终使用工作目录内的 Python/Node 绝对路径。安装不注册系统 Python，不修改全局 PATH、npm registry 或用户的其他环境；网络和组织策略导致的失败仍按实际错误停止。bootstrap 与 doctor 共用 `installed_python_versions()`，在同一个 venv 子进程中核对平台、`sys.base_prefix` 和依赖加载及版本。旧版系统环境或迁移后路径不符时保留并停止；结束使用环境的任务后仅重建 `.venv`，凭据、BL 安装、任务与结果保留。doctor 的 `python_base` 是诊断进程信息，实际 venv 绑定从目标 venv 子进程读取，不以调用者路径代替。

该本地探针用退出码2表示绑定不符、3表示依赖缺失，其余执行失败报告实际退出码；只有依赖缺失或版本不匹配才进入依赖安装。bootstrap 成功已经包含必要验证，正常更新后不再额外调用 doctor。BL 包信息由调用方读取一次，可用性检查直接启动固定入口并核对运行版本，正式业务调用仍独立核对当前 BL 版本。

升级使用 `bootstrap --cleanup-old-cache`：环境全部准备成功后，`installation.prune_download_cache()` 按当前Python依赖锁与pip版本删除旧wheel，按npm锁保留当前实际包名及版本。实际安装了依赖或BL时也清理旧缓存；普通环境复用不额外扫描。清理数量放在cache_cleanup，失败单独放cache_cleanup_warning，保持已完成的环境准备结果。

Python始终使用`--no-cache-dir`，本项目只清理自己保存的.runtime/wheels。[pip官方说明](https://pip.pypa.io/en/stable/topics/caching/)区分原生缓存与下载目标。npm使用私有Node调用公开的cache ls/clean/verify，并显式指定工作目录的.runtime/npm-cache，索引和内容删除交给npm。[npm说明](https://docs.npmjs.com/cli/v11/commands/npm-cache/)及[11.19.0源码](https://github.com/npm/cli/blob/v11.19.0/lib/commands/cache.js)提供依据。旧包逐键clean后执行一次verify回收失效索引：同一旧包的官方源和镜像键可能共享内容，批量clean遇到已删除的共享内容会提前结束；真实隔离缓存已复现该问题。verify仅在删除旧键后使用，属于npm缓存整理，不是重复的环境检查。

当前镜像真实缓存键使用cdn.npmmirror.com/packages路径，原生cache ls按包规格筛选只命中55个当前条目中的2个，不能据此计算删除差集。本项目仅识别固定两源的registry路径及实际镜像CDN路径，按锁中的实际name处理npm别名包；元数据和未知键保留。真实缓存合约已验证旧条目删除后当前条目仍可读取。系统缓存、已装运行时、凭据、任务和输出不在此清理范围。

安装日志统一保存为 UTF-8。普通 pip 命令显式传入 `-X utf8`；Python 3.12 的 ensurepip 内部子进程使用本地编码，因此只在该调用按 `locale.getencoding()` 解码。二者均保持 `-I` 隔离模式，不修改标准库或系统编码。

Python 安装器继续按锁定版本准备依赖。先并行采样 PyPI 与阿里云镜像同一 pip wheel 前缀，排序只是当时短时吞吐，不保证全程速度。pip 自行处理有限连接重试、下载恢复与摘要检查；每阶段每源至多启动一次下载，最终失败才换源。完整 wheel 保存在私有目录，本机安装使用 `--no-index`。

首次安装 BL 时，`rank_npm_registries()` 复用 `_sample_download()` 比较 npm 官方源与 npmmirror 的固定 BL 包前缀。正文采样窗口从响应就绪后开始，评分包含连接等待。`_install_bailian()` 按顺序每源至多调用一次原生 `npm ci`，由 `--registry` 切换下载位置，保留锁定版本及 integrity；`fetch-retries=2` 与 `prefer-offline` 分别交给 npm 处理有限重试和缓存复用。正常下载没有额外总时限。

BL 安装资源只有 `scripts/bailian/package.json` 与 `package-lock.json`，由 npm 下载官方 `2.4.0` 包及锁定依赖。安装检查要求当前固定版本；版本不匹配时按 [错误说明](../skills/asr-transcription/references/errors.md#常见问题处理)仅重新安装工作目录的 BL，凭据及任务位于独立目录。两个发行包均使用同一套官方依赖锁。

`run_installer()` 可将 stdout 写入调用方持有的临时文件，stderr 仍逐行写入安装日志和进度。BL 安装从 npm `--json` 的 `error.code` 判断是否换源：已识别连接、请求/正文超时、404/408/429/5xx、下载校验错误可以切换；权限、磁盘、锁冲突、未知错误或无法解析的结果立即停止。临时 JSON 关闭后删除，无需新的持久状态或日志解析器。第二次 ci 重建的是本次新安装目录，已有冲突安装仍由 bootstrap 在开始前拒绝。两源失败保留 bootstrap.log；缓存复用不等于文件断点续传，这些策略不扩展为云端转写重试。

Windows 虚拟环境的 Python 启动器可能另起实际工作进程。本机有限命令 `run_process()` 和安装命令 `run_installer()` 持有本次 `Popen`，在超时、中断或异常退出时共用 `stop_process_tree()` 结束其进程树；正常完成不触发停止。选择窗口只依赖标准库与 tkinter，直接使用 `sys.base_prefix/python.exe`，使取消动作对应实际窗口进程。停止范围限于本次创建的进程，不枚举其他 Python 或浏览器进程；BL 登录和识别沿用各自的生命周期。

`scripts/build_zip.py` 按固定逐文件映射生成两个 ZIP：Skill 资源直接作为归档根，加上仓库根最新版 README.md 和 README.en.md。完整包 `asr-transcription.zip` 额外包含 `assets/runtimes/python-3.12.10-amd64.zip` 与 `assets/runtimes/node-v24.21.0-win-x64.zip` 两个原始官方归档；轻量包 `asr-transcription-lite.zip` 不附运行时。两包代码与说明相同，Python 依赖和 BL 安装仍需联网。README 字节原样入包，仓库资料用完整 GitHub 链接，语言切换与 LICENSE 用包内链接。排除开发 doc、AGENTS、UML、测试、Vue/TS 源码、构建工具、已安装依赖、凭据和用户数据。

在仓库根目录使用开发环境构建。未提供 `--runtime-directory` 时输出轻量包；提供包含两个原始官方 ZIP 的目录时，先校验摘要，再输出完整包：

```powershell
& ./.venv/Scripts/python.exe scripts/build_zip.py
& ./.venv/Scripts/python.exe scripts/build_zip.py --runtime-directory '替换为两个官方ZIP所在目录'
```

默认输出到 `dist/`，已有同名文件不会覆盖；需要另选目标时使用 `--output`。

开发在 dev，master 保存正式发布里程碑。当前验收发布版本为 v0.1.1；项目版本仅在下次通过验收并发布 master 时按变更递增。正式标签和附件发布后保留，新版本使用新标签。依赖版本由各自锁文件维护，历史实现和发布记录通过 Git 追溯。

界面成功反馈使用组件 success 类型，规则链接使用 primary 类型，错误与警告使用红色。页面与卡片、输入区通过 Element Plus 的背景和填充变量区分；提示条和错误条与卡片共用同一个主列容器，保持边缘对齐。

当前灰阶参考 [OpenAI Apps SDK UI 原色](https://github.com/openai/apps-sdk-ui/blob/0f00143c7a639906f1621fe58e1b6be7b5bea46d/src/styles/variables-primitive.css)与[语义色](https://github.com/openai/apps-sdk-ui/blob/0f00143c7a639906f1621fe58e1b6be7b5bea46d/src/styles/variables-semantic.css)，以及 [Codex 公开外观示例](https://learn.chatgpt.com/docs/reference/settings#appearance)。页面、卡片、输入区使用中性灰，通过 Element Plus 背景、文本与边框变量映射；蓝色链接、绿色成功提示和红色错误保留明确语义。此处只参考公开色板，未引入 OpenAI 的 React 组件、字体或图标资源。

编辑视图在宽度至少 1100px 时显示右侧 `SettingsSummary.vue`，通过 CSS Grid 分列、sticky 跟随，并按可用高度允许摘要内部滚动。摘要只读取当前表单中的文件名、大小、识别选项、增强计数和认证选择；不读取 Key、不请求校验或产生预览版本。较窄窗口保持单列；正式预览仍由 ReviewPanel 独立展示，遵循原来的确认交接协议。

全局提示与字段卡片由同一个主列控制宽度。加载失败或事件连接中断时，前端进入 unavailable，统一显示一个错误结果页并隐藏填写引导、步骤和操作栏。cancelled／expired／handed_off保持独立终态说明。
