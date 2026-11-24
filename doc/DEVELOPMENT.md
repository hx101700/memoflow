# 开发说明

本文说明 MemoFlow 第一阶段的职责、接口和数据生命周期。用户操作见 [usage.md](../skills/asr-transcription/references/usage.md)，对象与调用关系见 [UML](UML.md)，实际验证见 [ACCEPTANCE](ACCEPTANCE.md)。

## 业务与职责

MemoFlow 的目标是从语音生成符合用户习惯、重点要求和指定格式的纪要，并采用用户确认的范例与修改反馈改善后续结果。当前 `asr-transcription` Skill 实现第一阶段：把单个录音转为原始 JSON 和 Word、Excel、Markdown 转写校对稿，并支持已有结果的本机人工回听、文字与说话人修改、独立校验稿导出。第二阶段的个性化纪要生成、偏好存储及反馈学习仍在开发中，当前代码尚未实现。

固定模型为 `qwen-audio-3.1-asr-flash-filetrans`，北京地域，使用官方百炼 CLI（BL）`2.10.5` 临时 OSS 上传。CLI、core、commands、runtime 均由 npm 锁定官方版本。版本比较及升级取舍见 [BL_COMPATIBILITY](BL_COMPATIBILITY.md)。

| 参与者 | 职责 |
| --- | --- |
| Codex 与 Skill | 选择工作目录、将本次录音带入页面、根据用户确认消息提交设置、处理认证、执行工具并交付结果 |
| Vue 页面 | 文件选择、配置与预览、复制确认消息；回听段落、播放器、校对保存与当次导出提示 |
| PowerShell 安装入口 | 校验包内或下载的 Python/Node 归档，在工作目录解压并调用 Python 安装入口 |
| Python | 管理本机会话、保存确认快照、媒体准备、调用 BL、解析结果和生成文档 |
| BL | 鉴权、临时上传、识别提交、轮询、下载与原始 JSON 落盘 |

一个完整转写工作流由一个 Skill 串联。共享 CLI 能力集中在 `utils/bailian.py`；有独立的新 BL 用户任务时再评估拆分，当前不引入通用工具注册、云客户端、数据库或消息队列。

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

`child_environment()` 复制父进程环境，保留用户代理、证书及普通系统设置，由 BL、pip 和 npm 原生解释。仅清除会覆盖工作区选择的百炼凭据／端点／工作空间、Node/Python 外部加载配置，以及 pip/npm 的外部安装目标；随后指定私有运行时、配置、缓存和临时路径。API Key 模式再从本工作目录 `.env` 注入密钥，控制台模式读取该工作目录的 BL 配置。函数不修改父进程环境，也不改写系统网络设置。

`SKILL.md` 的 name、description 和正文为技能入口。`agents/openai.yaml` 是可选展示元数据，scripts、references、assets 分别存放可执行工具、按需资料及模板。根 README 面向使用者，AGENTS 面向源码维护者；安装包的 README 直接取自仓库根。

现行用户文案统一使用“说话人区分”（speaker diarization）、“上下文增强”（context enhancement）、“API Key”和“百炼 CLI（BL）”（Bailian CLI）。前端“精度增强”（Recognition enhancements）栏目包含热词与上下文增强。网页编辑会话使用 `session_id`，交接后转写任务使用 `job_id`；第一阶段成品称“转写校对稿”（transcript drafts），第二阶段称“个性化纪要生成”（personalized minutes generation）。官方名称、协议字段和标识按原样保留；“说话人分离”作为官方术语对照。

## 模块职责

Python 模块路径相对于 `skills/asr-transcription/scripts/asr_runtime/`，前端路径相对于仓库根。前置安装入口是 Skill 内 `scripts/bootstrap.ps1`，它读取同级 `runtimes.json`，完成基础运行时准备后调用现有 Python CLI。

| 模块 | 职责 |
| --- | --- |
| `__main__.py` / `web.py` / `review_web.py` | CLI 与 HTTP 分派；配置页事件连接、回听页音频Range读取及各自服务生命周期 |
| `application/bootstrap.py` / `diagnostics.py` | 安装工作目录依赖、诊断本机条件 |
| `application/session.py` | 编辑会话、附件与原生窗口共用音频登记、内存热词导入、预览与交接 |
| `application/recovery.py` | 正常关闭及下次开页时回收可确认归属的临时文件 |
| `application/inputs.py` / `rules.py` | 读取输入事实、统一应用模型规则；rules 无 I/O |
| `application/transcription.py` | 一次执行、任务元信息查询、状态查询和重新导出 |
| `application/review.py` | 已有任务的回听会话、版本化校对草稿、音频绑定和校验稿导出 |
| `application/delivery.py` | 三种 writer 的顺序调用与交付汇总，分别写原稿与校验稿 |
| `utils/environment.py` / `auth.py` | Runtime、工作区进程环境和运行凭据 |
| `utils/installation.py` | Python/npm 固定来源测速、安装进度与结构化输出、子进程回收 |
| `utils/bailian.py` | 公开 CLI 参数映射、BL 进程和脱敏错误 |
| `utils/files.py` / `job_files.py` / `session_files.py` | 文件摘要与原子替换、任务协议、会话连接与交接回执 |
| `utils/hotwords.py` / `media.py` | Excel 导入/模板、媒体探测、单声道副本及完整MP3播放副本 |
| `utils/results.py` / `documents.py` | 结果解析、文档生成与目标替换 |
| `utils/path_picker.py` / `_path_dialog.py` | 原生文件/目录窗口、共享取消与子进程回收 |
| `utils/local_http.py` | 两类本机页面共用的端口绑定、Host/Origin/令牌校验、JSON读取与响应头 |
| `models.py` / `utils/i18n.py` | 共享类型、请求范围的本机消息语言 |
| `frontend/App.vue` / `components/` | 两步页面与 Element Plus 输入、表格、预览、结束提示 |
| `frontend/useTranscription.ts` / `model.ts` | 页面用例编排、纯状态和操作权限 |
| `frontend/ReviewApp.vue` / `useReview.ts` / `review.ts` | 回听段落与播放器、串行自动保存、导出前保存、本机HTTP及页面在场连接 |
| `frontend/api.ts` / `types.ts` | 本机 HTTP/事件传输与协议类型 |
| `frontend/preferences.ts` / `i18n.ts` | 语言、外观偏好与文案 |

Session、ReviewSession、PathPicker 持有实际生命周期；无状态操作使用模块函数。TypedDict 和 TypeScript 接口描述数据协议，不建立重复的运行时对象层。Python 保持入口 → application → utils；utils 不反向导入用例。

## 编辑会话与转写任务

| 对象 | 何时创建 | 状态与结束 | 持久数据 |
| --- | --- | --- | --- |
| 编辑会话 `session_id` | 启动网页服务时 | 编辑、预览；交接、取消或打开满两小时后结束 | 活动连接信息；成功交接回执；显式取消结果 |
| 转写任务 `job_id` | 有效预览被代码交接时 | 配置固定；一次执行，结果与记录保留 | 配置/摘要、ASR执行记录、原JSON及音频引用 |
| 回听会话 `ReviewSession` | 为已有 JSON_READY 任务打开回听服务时 | 复用job_id；保存、导出、结束，不改变转写执行状态 | job目录下review草稿、必要播放副本与临时连接 |

转写工单只负责“填写 → 预览”，往返不生成任务编号。前端完成预览展示后登记当前版本；后端可确认“当前预览已就绪”，不把成功校验直接等同页面状态。返回修改先通知后端，成功后才恢复可编辑表单。

`review_enabled` 随工单预览和交接配置保存，不映射为BL参数。成功JSON及执行记录落盘后，true直接返回JSON_READY，由Skill打开人工回听，不调用文档导出或创建文档目录；false沿原流程自动生成三格式原稿。旧任务缺失此可选字段时按false处理，仍可按用户要求用原job_id打开回听。回听开关不影响原JSON和一次执行约束。

每个成功任务固定对应一份本机校对稿；没有修改时原JSON就是基线，有修改时同一job的 `review/draft.json` 保存最新差异。网页是临时编辑窗口，导出、取消选择、不修改或关闭服务都不删除稿件，后续按同一job恢复。

预览有“复制给 Codex”按钮，复制明确开始请求及 `session_id`。Skill 必须从当前用户确认消息读取编号；仅“继续”不能选择会话，不从启动回执、历史或目录代替用户选择。会话编号是定位信息，保护请求的令牌是另一数据。

`confirm --session ID` 定位私有连接信息并调用受保护的本机 HTTP。Session 锁内检查截止时间、预览状态和版本，核对音频 size/mtime，再按本次任务编号、音频及结果路径检查完整 Windows 命令长度。通过后先保存候选回执，再写配置及摘要，最后原子发布 config.json 作为完成标记。长度超限时保留预览供返回修改，不创建任务文件。读取回执时，只有对应配置已发布才视为交接成功；成功后配置不可修改，重复确认读取同一份回执。CLI 先读持久回执，因此响应丢失、网页服务已经结束时仍可恢复原编号。

会话有效期为从创建起固定两小时，使用一次计时器及操作时截止时间检查。到期与交接共用状态保护，只有一个终态。没有活动上报、心跳、逐次草稿保存或云端进度轮询。页面通过单向事件连接收到交接、到期或取消结果，呈现结束提示，由用户关闭标签页。

填写或预览期间用户要求取消、明确转写新录音、检查更新或安装新 ZIP，Skill 先用当前对话活动页面的编号运行 `cancel`，等待原 `serve` 退出，再按本次意图继续。新录音按更新、必要的环境准备、带入附件开页顺序执行；确认旧预览才进入交接。Session 在同一状态锁内先原子保存 `cancelled.json`，再发布取消终态；CLI 读取已有交接或取消结果，HTTP 响应丢失后复用原结果。此文件只有取消状态，没有输入内容或连接凭据；正常清理与下次回收均保留它。服务被先行强制结束且没有记录时仍返回无法核实，不把进程结束推断为取消成功。

确认发现原录音变化或无法读取时保留当前预览并拒绝交接，用户可经现有“返回修改”重新选择、校验；无需新事件或状态轮询。音频从本次附件或系统文件窗口登记的原路径读取，Excel 仅在内存解析；交接保存参数与来源引用。取消、到期只清理会话临时记录，原文件和已保存 Key 保留。结束时移除临时连接令牌并关闭服务。已经创建的任务、登录等待和转写不受两小时编辑期限影响。关闭标签页并不能可靠地证明服务结束。

### 临时文件回收

正常关闭依次执行：`Session.cleanup()` 设置关闭状态并取消原生选择窗口 → HTTP 服务器等待请求线程结束 → `recovery.finish_session()` 回收磁盘暂存。热词接收在内存中完成；writer 的 finally 先处理自身临时文件，统一回收发生在请求线程结束后。

若服务被强制终止，退出清理可能没有运行。下次同一工作目录启动 `serve` 时，`recover_workspace()` 读取有效任务配置以定位文档临时文件，并回收满足条件的会话残留。会话须同时达到原两小时截止时间、所属进程已确认结束；进程仍存活或状态未知时保留对应临时文件，任务配置不可读时保留该任务的文件。进程编号复用时也按仍存活处理。它是开页前的一次检查，不是后台定时任务，也不恢复或重传识别。

| 文件类别 | 处理与依据 |
| --- | --- |
| 输入音频与热词 Excel | 音频直接读取原路径；Excel 内存解析；不产生输入文件副本，原文件不属于清理范围 |
| 未发布配置与候选回执 | 按所属会话清理 config.json.tmp、config.sha256、候选 receipt；存在执行目录、旧版交付目录或其他归属异常时保留 |
| 会话内 Key 暂存 | .env 及 python-dotenv 的同目录临时文件随会话回收；正式运行根 .env 始终保留 |
| JSON / 文档原子写入临时文件 | 文件名记录 PID。下次 serve 只删除所属进程已结束的临时文件，保留正式 status.json 和成品 |
| Python 库临时目录 | serve、review、transcribe、export 使用私有 .runtime/tmp/python-PID-随机值，正常退出清理；死进程目录在下次 serve 回收 |
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

登录从首次调用就采用正常 Windows 桌面执行权限。`check_login_execution_context()` 拒绝已观察到会导致浏览器失败的受限令牌。官方 BL 2.10.5 的 `buildOpenInvocation()` 使用 Windows 命令引用和 `windowsVerbatimArguments` 保留完整 URL；Python 直接调用 `bl auth login --console`，由 BL 打开系统默认浏览器、等待回调并保存凭据。

官方2.10.5的浏览器登录要求text输出；Python使用`--output text`等待原进程，按退出码解释失败，原始登录stderr保留在进程内。BL先注册完成事件再异步打开浏览器，空等返回TIMEOUT，结束却未保存凭据返回GENERAL。成功后单独以JSON查询公开本机状态，区分控制台会话与ASR所需的模型Key；识别和状态命令的JSONL错误仍由explain_cli_error读取末尾根对象并脱敏。

`recognition_arguments()` 统一映射 BL 选项。热词序列化为一个 JSON 参数，上下文使用一个 `--context=<原文>` 参数，子进程采用参数数组与 `shell=False`。交接与执行准备复用同一个命令构造和长度检查；前者允许用户在生成任务前修正超长输入，后者核对即将启动的实际命令。交接不读取 Key 或启动 BL，运行凭据只在执行准备时读取。固定 BL 2.10.5 的即时热词参数仅接受 JSON 文本，没有文件或标准输入入口；规则允许的 2000 条热词不保证都能装入 Windows 的完整命令。来源见 [model.md](../skills/asr-transcription/references/model.md)。

官方 core 的 `Client.uploadFile()` 将已解析的 `settings.timeout` 经 `resolveFileUrl()`、`UploadOptions`、`uploadFile()` 传给 `uploadToOSS()`；上传计时器使用该秒数，获取上传凭证仍为15秒。core 的 JSON 请求期限覆盖响应头与 JSON 正文，并在 Node 请求中关闭较短的 undici headers/body 默认期限。上传、提交、轮询、下载与 `--out` 保存均使用官方包。

`WAIT_SECONDS=3600` 用于上传、提交和单次查询；BL 轮询也以该值建立总截止时间，轮询间隔为5秒。`PROCESS_SECONDS=WAIT_SECONDS*2+300=7500` 限制整个 BL 子进程，给上传和轮询各一小时及300秒余量；结果下载没有独立 BL 时限。各阶段可累积，整体上限不是每次请求时限或云端完成保证。`Request timed out.` 是多种请求超时的统一文本，不能从录音大小推断历史失败阶段；未知云端结果仍维持一次尝试约束。本机合约与真实云端验收分开记录。

`transcribe --job ID` 读取交接授权，核对协议与当前模型，再独占创建 execution 目录。一次任务只有一次尝试，准备失败也保留占用；重复调用读取既有状态，不自动重试。它约束本地尝试次数，不是云端恰好一次保证。启动后 Codex 持续等待同一进程，直到文档交付或明确失败。

额度与计费失败复用 `error_catalog.json` 和 `explain_cli_error()`：按服务精确码给出免费额度、欠费、预算或实际账单状态的中文说明，不依赖CLI退出码4或HTTP状态推断。Skill从原回执读取原因与原任务编号，具体指引统一见[额度与计费提示](../skills/asr-transcription/references/errors.md#额度与计费提示)。两种认证方式共用此路径，不增加前置查余额、自动调整计费、重试、模型切换或新状态；BL未暴露的错误仍保留未知。

| 字段 | 含义 |
| --- | --- |
| `CONFIGURED` | 确认配置中的固定值；job-status在execution不存在且配置有效时派生此结果 |
| `PREPARING` | 已取得执行占用，最近处于本机准备 |
| `RUNNING` | 已写入启动前保守记录，不证明云端受理或进程存活 |
| `STOPPED` | 此次执行停止，以 phase 与 cloud_outcome 解释 |
| `JSON_READY` | 原始 JSON 通过结构检查 |
| `documents_ready=true` | 仅当次CLI导出回执包含：delivery 为 COMPLETE，三格式均完成，不写入执行记录 |
| `OUTCOME_UNKNOWN` | 读取已有执行目录但记录不可读时合成的查询结果；不是新的持久执行阶段 |
| `record_error` | 记录写入失败，磁盘可能滞后于当次回执 |

成功 JSON 记录写入失败时保留 JSON 并在导出前返回。当前没有补签摘要或恢复成功记录入口。`job-status` 只读本地记录，不查询云端或进程存活。[转写流程](UML.md#07-转写流程)展示各方职责，分别保留编辑会话、执行记录和独立交付边界；保存失败导致的当次回执与磁盘滞后见[图08](UML.md#08-记录保存失败)。具体状态与修复见 [errors.md](../skills/asr-transcription/references/errors.md)。

`jobs [--query TEXT]`由 `list_jobs()` 读取当前工作目录下已发布的任务配置与执行状态，仅返回job_id、audio_name、confirmed_at、status，按确认时间倒序排列。query对录音名或编号作大小写无关的包含匹配；时间描述由Codex核对返回的confirmed_at，多匹配先让用户选择。逐项问题放入issues，其余候选保留；已有执行目录但记录损坏时保留候选并标记OUTCOME_UNKNOWN。查询不读取原转写正文、校对草稿或凭据，不调用BL、不创建目录或另建索引；选定任务后继续使用原review或job-status入口。

## 文档交付与路径

results 唯一解析原始 JSON，三个 writer 共用 Transcript。delivery 把 `config.model` 传给 writer，保留历史任务真实模型；依次尝试 Excel、Word、Markdown，单格式失败仍尝试其他格式，中断则停止剩余格式。每次用同目录独立临时文件完成后替换固定目标，失败保留旧目标。Excel/Word 替换前回读，Markdown 编码保真由测试验证。

`export --job` 重导核对配置、磁盘 JSON_READY 及原 JSON 摘要，复用同一 writer、路径和模型，不读取音频、Excel 或 Key，也不调用 BL；此入口只导出原JSON。回听页面导出由原生窗口选择目录，使用 `录音名-reviewed-JOB_ID` 文件名。文件名取 `Path(config["audio"]["name"]).stem[:80]` 与完整job_id，同任务在同目录重导覆盖自己的同名文件；文档标题保留完整源文件名。需保留外部编辑时，用户应先改名或另存已有成品。

Skill按用户所指稿件分派：明确原始稿使用export；明确已校对稿、最新稿或当前正在回听的稿件使用回听页导出。泛称重导且没有活动回听编辑时读取job-status：对JSON_READY任务，review.revision大于0走回听页，review缺失或revision为0表示没有已保存修改，可使用原JSON；草稿状态OUTCOME_UNKNOWN先核对来源，其他执行状态按实际回执处理。它只选择已有入口，不新增导出状态或正文搜索。

两类三格式文件的生命周期均在导出后结束，用户可改名、移动或编辑，MemoFlow不再跟踪。`export_documents()`只返回当次COMPLETE／PARTIAL／FAILED和各格式files；实际发生原稿导出时，transcribe或export将其连同documents_ready附入当次CLI回执，不改写ASR记录。开启回听的transcribe没有这些导出字段，成功JSON落盘后仍正常退出0。回听只显示本次提示，不保存导出结果或路径，也不比较导出版本。长期业务数据仅保留音频引用／必要播放副本、原JSON、校对草稿与必要ASR任务记录；旧版本导出记录及用户文件保持原位，不自动删除或迁移。

- 标题均为“源文件名（不含扩展名） 录音转写”，不另列音频信息行。
- Excel 使用等线、黑白无填充，第三行即表头；标题和任务说明左对齐，表头与非正文列居中，正文左对齐并自动换行。展示行高封顶，完整文本保留；真实存储超限时报错。
- Word 使用等线，标题 20 磅，其余正文、元信息、时间标签、页码 10 磅。时间标签无圆点，随下一段。正文标题保留完整文件名，不重复写入有限长的可选核心标题属性。
- Markdown的标题、元信息、时间与说话人标签、正文共用文本转义，人工姓名中的Markdown或HTML按文字输出。

| 数据 | 位置 |
| --- | --- |
| API Key / BL 配置 | 私有运行目录 `.env` / `.state/bailian/` |
| 活动连接信息 | `.state/sessions/<session_id>/connection.json` |
| 交接回执 | 同一 session 目录的 `receipt.json` |
| 显式取消结果 | 同一 session 目录的 `cancelled.json` |
| 音频来源 | 本次对话附件或用户通过系统窗口选择的原始绝对路径，任务只保存引用 |
| 热词来源 | 浏览器发送的 Excel 字节在内存读取，任务保存词典 |
| 配置与摘要 | `.state/jobs/<job_id>/config.json`、`config.sha256` |
| ASR执行记录 | 同一 job 目录的 `execution/status.json` |
| 校对草稿 | 同一 job 目录的 `review/draft.json` |
| 回听连接 / 播放副本 | 同一 job 目录的 `review/connection.json` / 按需生成的 `review/playback.mp3` |
| 原始 JSON | `<json_root>/<job_id>/json/transcription.json` |
| 原稿导出目标 | `<document_root>/<job_id>/documents/transcription.{xlsx,docx,md}`；完成后不跟踪 |
| 校验稿导出目标 | `<本次原生窗口选定目录>/<录音名>-reviewed-<job_id>.{xlsx,docx,md}`；完成后不跟踪 |

JSON 与文档默认根均为 `<workspace>/transcriptions/`，可分别选择。内容保真、识别质量与 Office 视觉效果分别验收。

## 人工回听与校对

`review --job ID [--port PORT] [--no-browser]` 由CLI进入 `serve_review()`。不知道编号时先用jobs核对已有任务。首次打开通过 `ReviewSession` 核对确认配置、磁盘JSON_READY及原JSON摘要，恢复与该摘要绑定的草稿；没有草稿文件时直接使用原JSON，不创建空草稿。这些条件不满足就停止，不补签原结果或重新识别。回听沿用job_id，不创建新的编辑session_id，不读取模型凭据。

服务绑定127.0.0.1并将port、token、pid写到任务的 `review/connection.json`。`serve_review()`先请求已有连接的描述：任务匹配且未关闭时复用该服务；服务无响应时，只有原PID已确认结束才重新创建，存活或未知时停止并提示检查。`listening`回执包含job_id、url、pid、reused及browser_request，不含token。回听没有转写配置页的两小时期限，使用独立页面在场连接管理最后一个页面离开后的收尾。

普通调用由服务请求系统浏览器开页；仅传入 `--no-browser` 时由Codex在listening回执后请求宿主打开URL。browser_request只说明开页请求结果，不证明用户已看到页面。

页面连接采用浏览器原生[EventSource](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)，离页处理使用[pagehide](https://developer.mozilla.org/en-US/docs/Web/API/Window/pagehide_event)；服务端直接观察连接断开，因此关闭进程时不依赖离页事件一定触发。

### HTTP边界

`review_web.py` 与配置页共享 `LocalHTTPServer` / `LocalHandler`。静态入口 `/review` 提供同一构建资源并设置HttpOnly、SameSite=Strict Cookie；Cookie仅用于访问认证，校对正文和进度保存在任务JSON文件。受保护接口接受当前Cookie或X-ASR-Token，始终检查精确Host，有Origin时必须同源，POST必须带本机Origin。JSON请求沿用512KiB上限。页面不能传任意文件路径要求读取音频或直接指定导出目录。

| 接口 | 请求与结果 |
| --- | --- |
| `GET /api/review` | 返回原模型、文件名、revision、句子/说话人、audio可用性及closed；每句含original_text与original_speaker_id供比较/重置，不返回录音绝对路径或导出信息 |
| `GET /api/review/presence` | 保持受保护SSE连接，登记页面在场；服务端通过连接EOF识别离开，不发送周期心跳 |
| `GET /api/review/audio`、`HEAD /api/review/audio` | 读取当前绑定录音；单段起止、开放结尾或后缀Range返回206及Content-Range，不满足返回416及总字节数；HEAD不发音频正文 |
| `POST /api/review/save` | revision加可选sentences与speakers；返回ok及已保存revision；旧版本返回409，校验错误422 |
| `POST /api/review/export` | 严格提交revision与picker_id；选择目录取消返回cancelled=true，完成返回cancelled=false及当次delivery，不返回文字revision |
| `POST /api/review/select-audio` | picker_id关联原生窗口；取消保留绑定，匹配原录音后返回audio，不传入或返回文字revision |
| `POST /api/review/prepare-audio` | 按需生成或复用完整播放副本，返回audio；不改变原稿或调用ASR |
| `POST /api/review/close` | 关闭会话及选择器，返回closed后停止服务；不代替保存请求 |

### 保存与独立导出

句子编号、音轨和时间来自原JSON；只允许修改原有句子的text、speaker_id，以及非负整数说话人编号对应的name。空姓名沿用原编号标签，None表示未标注。描述中的original_text与original_speaker_id始终来自原JSON；单句重置把这两个原值提交给现有save，不增加重置接口，也不改变统一说话人姓名。`ReviewSession`在锁内检查revision、合并本批改动，先原子保存 `draft.json`，成功后才更新内存和版本；仅正文、归属或姓名变化递增revision，无实际改动不递增。草稿保存source_sha256、revision、句子改动、姓名及可选重选音频路径，原JSON与确认配置保持不变。重选录音只保存新路径，保留服务端最新文字内容及revision，前端只接收audio，不能借此更新旧页面的文字版本。每次保存覆盖最新草稿，不保存逐次编辑历史；草稿无自动到期清理，关闭服务仅移除连接信息。恢复依赖原任务文件及原JSON，和是否导出无关。

前端 `useReview` 用800ms延迟及失焦触发串行保存；保存期间的新输入保留为下一批，不被旧回执覆盖。失败后保留输入、停止自动保存，用户可明确重试；409冲突要求先保留输入并重新读取。导出与重选录音先等待同一保存队列成功，再发对应请求。直接关闭浏览器标签页不会替用户完成保存；未保存或保存中通过标准beforeunload提示。

导出请求先检查revision，再通过共享PathPicker打开目录窗口，由用户在系统窗口中选择或取消。前端只为本次请求生成picker_id，不保存独立的选择等待状态，也不提供回听专用取消接口。初始目录从配置中的documents逐级向上查找最近可用目录，原盘也不可用时回退工作目录，不读取历史导出路径或预先创建文档目录。取消返回cancelled=true，不生成文件。用户选定目录后再次核对会话、revision及导出占用，才冻结已保存内容快照，锁外复用 `export_documents(..., review_directory=selected)`。窗口等待期间其他页面保存了新版本时，旧请求被拒绝，不导出混合内容。

三个writer共用合并后的Transcript；`Sentence.speaker_name`只用于输出人工姓名，原结果解析仍保留原编号。校验稿按上节任务命名规则直接写到选定目录，原documents及原JSON保持。当次回执含各已处理格式的实际结果，前端全部成功时显示一次短提示，部分或全部失败显示告示；不把回执存入稿件或更新本页文字revision。其他页面在导出期间保存的修改仍受后续save版本检查保护。

`job-status`在ASR执行状态之外附加review，只返回已保存草稿的revision或读取问题，不启动回听、不返回正文，也不读取导出信息。页面未保存的改动不在磁盘查询结果中；查询不能说明用户是否已经导出、移动或修改成品。

### 音频与关闭

打开回听时依次尝试草稿记录的重选路径、配置中的原位置、已有 `execution/mono.flac`、已有 `review/playback.mp3`。重选文件核对大小及SHA-256，原位置核对确认时的文件属性；同一路径只尝试一次，避免重选摘要检查失败后降级为属性检查。恢复只复用已有文件，不增加转码或缓存。全部不可读时仍显示校对内容并要求重选原录音。已绑定文件每次读取核对路径、大小、mtime与文件身份；同内容文件移动后可以重选，其他录音会被拒绝。

浏览器播放当前绑定的录音或已有副本。当前绑定不是已生成的播放副本，且浏览器明确不支持或解码失败时，前端先用同一端点HEAD核实可读，再请求一次 `prepare-audio`；网络失败不触发转码。`prepare_playback()`使用现有PyAV将第一音轨转成完整MP3，经临时文件、源文件属性检查和媒体探测后发布；不逐句生成文件。底部普通播放连续进行，行内“回听本句”从原开始时间播放到结束时间暂停，没有连续模式开关。进度条拖动值与音频实际位置分开，释放后才seek；暂停时seek也更新当前句高亮。滚动跟随响应实际currentIndex变化及重新开启跟随，正文编辑期间不滚动。

前端通过EventSource保持 `/api/review/presence`，服务端等待socket EOF并统计活动页面；这不是周期HTTP请求或心跳。短暂断线由浏览器自动重连，页面保留当前输入，不增加手动重连按钮或重新GET稿件。presence只表示页面在场，连接错误不代替保存结果；实际保存失败仍沿saveError保留输入并等待用户重试。最后一个页面断开后启动10秒宽限计时，期间任何页面重连会取消计时，另有页面连接时不安排退出。到期仍无人连接才关闭会话及服务；刷新短暂断开可继续原会话，网络中断超过宽限期也可能触发收尾。页面离开时关闭在场连接，重连不代替校对保存。

页面不提供单独结束按钮。用户等待已保存后关闭标签，Codex仍可按明确请求调用 `review-close --job ID`；该命令不能保存浏览器中尚未提交的输入。主动关闭在finally中停止服务，关闭响应遇到断管也会收尾；正常退出等待请求线程并移除连接记录，保留草稿、播放副本及成品，下次打开恢复已保存版本。没有持久化的closed终态回执，也不套用配置页的cancelled.json；缺少连接时返回closed表示没有登记的活动服务。强制中断时不保证清理完成或未保存输入可恢复，现有回收器不自动删除review数据。

## Skill 自动更新

更新是安装维护能力，由 `scripts/update.py` 独立完成，使用 Python 标准库，不依赖待更新的业务模块和 pip 包。Codex 在开始新的使用时直接用工作目录的基础 `.tools/python/python.exe -I -X utf8` 调用；更新入口不接收 `--workspace`，也不要求 `.venv` 完好。版本判断和下载由代码执行。更新源固定为 `hx101700/memoflow` 的最新正式 Release，不跟随 dev 或同版本内容替换。

`scripts/build_zip.py` 将根 package.json 的版本与固定运行文件列表写入两包相同的 `skill-manifest.json`。该清单只记录受管路径，不包含用户资料、开发文件、运行时归档、自身或稳定哨兵。最新版本号高于本地时，更新器下载 Release 的轻量 ZIP，核对 API 返回的文件大小及可用的 SHA-256，再核对包内版本和路径集合；逐个读取文件的 ZIP CRC 检查全部完成后才替换。文件直接覆盖、不备份；旧清单独有的文件删除，清单外的文件保留，最后发布新清单。

`.skill-update-state.json` 位于安装目录，记录 `checked_on`、结果和必要的覆盖状态，同一 Skill 的多个工作目录共享。日期使用 `date.today()`，在首次网络请求前保存；日检次数按整次操作计算，包含本次允许的有限重试。检查成功、没有更新或最终失败后，当天后续调用均读取缓存；忙时暂缓尚未联网，不记为检查。没有后台定时器、跨调用自动重试或额外通知进程。

`update_skill()`中的下载包装为版本查询和轻量ZIP下载共用两次额外重试预算，只重发当前失败的请求；已完成的查询不因ZIP下载失败而重跑。每个请求仍使用30秒超时，两次重试按整个操作的使用顺序分别等待1秒、2秒，并向stderr报告进度。可重试范围是URL网络错误、连接/超时错误、响应提前断开的IncompleteRead，以及HTTP 408、429、5xx；TLS证书验证失败及其他HTTP状态不重试。发布JSON/版本资料、包大小、SHA-256、清单、CRC校验在下载包装之外，覆盖/恢复也不进入重试。预算耗尽或遇到不可重试问题后沿原失败与回退路径处理，继续当前请求仍以repair_required为准。

最终日检记录保存失败通过 `record_error` 单独返回，保留本次实际状态及安装版本；已发布的新清单是文件更新完成的依据。下次遇到残留 `applying` 但清单已是目标版本时，当天缓存按已完成更新解释。回执提供版本、结果和必要错误；仅实际 `updated` 附带目标版本的 `release_url` 与 `release_notes`，正文直接取同一次Release响应的body，缺失则为空字符串，不增加网络请求。当日缓存移除这两个展示字段，避免反复提示。

Codex在更新和本工作目录依赖准备成功后，根据Release正文用用户语言简述两三条变化并给出处，作为进度消息继续原任务；只要求更新时再结束回复。正文作为变更资料，不能授权执行额外操作。正文不可用不改变更新结果，仍提供版本链接。旧更新器完成覆盖后仍返回旧格式，故仅在回执缺少新增字段或手动ZIP更新时，按安装清单定位对应Release读取说明，同样不增加确认或终止在途进程。

日检记录首次写入失败时，更新器返回failed、repair_required=false、installed_version和record_error，直接结束本次检查且不联网；日期没有落盘。已有清单、状态或读取保护无法确认时，main返回repair_required=true及非零退出码。HTTP403等网络/预检失败及成功回退继续使用当前安装；后续先判断repair_required，再按status处理，当天失败缓存也不阻止本次新转写。

用户主动检查传 `--check-now`，由同一 `update_skill(check_now=True)` 越过日内缓存，其结果覆盖当天记录，后续自动检查不再联网。两种入口使用同一锁、下载与覆盖方法；每次实际联网操作独立建立上述共用重试预算，读取当天缓存不重新请求。程序通过 stderr 提供检查、版本、下载和重试进度，stdout 返回最终 JSON；Skill 要求 Codex 在检查前、发现新版和完成后向用户提供文字说明。IncompleteRead保留为下载异常原因，先按剩余预算处理，最终失败时保留旧文件与当日日检记录。

`asr.py` 在导入业务模块前经 `skill_in_use()` 只读打开 `assets/update.lock`，共享句柄保持到命令结束。更新器用 Windows `CreateFileW` 的 share=0 独占同一文件，任何工作目录的活动配置页、回听页、登录或识别都使更新暂缓；新命令遇到正在更新时明确停止。句柄由进程退出释放，不持久记录活动 PID。哨兵不在覆盖或删除清单中。

此处的 Skill 写入仅限更新器的状态、同目录暂存和发行清单管理的资源。下载或预检失败保留原代码；覆盖前将本次目标的原内容存入内存，记录实际修改项与新建目录。覆盖出错时按逆序恢复或删除对应文件，清理新目录；正常退出清理暂存，不保留磁盘备份。当天检查记录保留。恢复本身失败或进程被强行中断时，`applying` 与最后发布的版本清单使入口准确报告未完成状态，不能声称已回退。任务、结果与凭据在独立工作目录，不参与覆盖。

更新后 Codex 重新读取 SKILL.md，并调用原 bootstrap 准备本次目录依赖；BL 版本冲突继续使用现有定点修复，不新增第二个依赖安装器。其他工作目录按当前依赖要求分别准备。

更新检查只决定安装维护结果，不能把新录音请求改派为确认旧预览。原请求为新转写时，Codex随后实际执行serve，取得listening回执，再按宿主现有方式请求打开URL；这些动作完成后才请用户填写。其他任务或回听页仍在使用共享Skill时允许更新暂缓，保持这些服务并用当前安装继续新录音开页。仅检查或更新Skill的请求完成相应处理后结束。转写/导出的停止条件按对应业务结果解释，不扩展到可恢复更新失败或附带警告。

用户提供新 ZIP 的重新安装由 Codex 使用文件工具完成：先核对完整新包，等待该 Skill 安装的全部命令结束，确认专用资源目录与用户工作目录分离，再用新包重建资源目录。此步骤清除旧代码、旧资源与旧检查记录，适用于没有发行清单的旧安装；非 Skill 文件先核对归属。它不会清理独立工作目录中的环境、凭据、任务或输出。自动更新仍复用当前清单的受管文件覆盖，不增加第二个安装器。

这属于 MemoFlow 从v0.1.2起提供的安装更新协议。[OpenAI Skill 文档](https://learn.chatgpt.com/docs/build-skills)说明 Skill 的脚本与资源结构，并推荐使用插件分发可复用能力；[工作区插件管理](https://learn.chatgpt.com/docs/enterprise/plugin-management)的每日市场同步由宿主管理。普通 ZIP Skill 的每日下载覆盖不是该平台保证，本项目通过上述入口实现。v0.1.0/v0.1.1先通过新ZIP获得入口和清单，再获取后续更高的正式版本；发布者继续提供两个ZIP即可。

## 界面和构建

页面使用 Vue 3、TypeScript、Element Plus。优先复用公开 props、插槽和默认交互；卡片、输入、表格、滚动、摘要、按钮、结果及图标由组件库承担。CSS 负责布局、响应式和有限主题差异，避免复制组件交互。

品牌旁的版本号使用Element Plus ElText的small/info样式，与MemoFlow放在同一行内文本容器中按字体基线对齐，仅保留局部水平间距。Runtime.skill_version只读取当前skill-manifest.json中的version；Session创建时保存该值，description通过既有/api/session返回skill_version: string|null。源码目录缺少发行清单时返回null并显示开发版。版本不进入转写任务配置、业务授权或浏览器持久偏好，展示不触发额外请求或表单重建。

偏好只保存当前来源下的界面语言与主题；随机端口变化时不保证跨会话继承。界面切换不改变表格、滚动位置、预览版本、音频语言、地域或输出文档格式。网页错误及警告使用 `LocalizedText={zh,en}`，动态参数在后端一次生成两种文字，页面按当前语言呈现，无需重发请求或重新校验。HTTP 的界面语言只用于原生窗口、模板示例等当次呈现；CLI 异常仍为可打印文本。首页设置 HttpOnly、SameSiteStrict Cookie；URL 和前端状态不持有连接令牌。

音频使用大块 `ElButton` 打开原生文件窗口，规格说明位于框内；选中反馈使用绿色文件图标与 success 标签，选择框保持中性背景；等待使用原生 v-loading 遮罩。Excel 使用 `ElUpload` 的按钮入口在内存导入，与下载模板并排。热词编辑使用 `ElTable` 与 `ElInput`，表尾添加入口使用公开的 `append` 插槽。错误标红通过 `row-class-name`；组件原有聚焦、禁用、滚动和主题行为保持一致。

界面成功反馈使用组件 success 类型，规则链接使用 primary 类型，错误与警告使用红色。页面与卡片、输入区通过 Element Plus 的背景和填充变量区分；提示条和错误条与卡片共用同一个主列容器，保持边缘对齐。

当前灰阶参考 [OpenAI Apps SDK UI 原色](https://github.com/openai/apps-sdk-ui/blob/0f00143c7a639906f1621fe58e1b6be7b5bea46d/src/styles/variables-primitive.css)与[语义色](https://github.com/openai/apps-sdk-ui/blob/0f00143c7a639906f1621fe58e1b6be7b5bea46d/src/styles/variables-semantic.css)，以及 [Codex 公开外观示例](https://learn.chatgpt.com/docs/reference/settings#appearance)。页面、卡片、输入区使用中性灰，通过 Element Plus 背景、文本与边框变量映射；蓝色链接、绿色成功提示和红色错误保留明确语义。此处只参考公开色板，未引入 OpenAI 的 React 组件、字体或图标资源。

编辑视图在宽度至少 1100px 时显示右侧 `SettingsSummary.vue`，通过 CSS Grid 分列、sticky 跟随，并按可用高度允许摘要内部滚动。摘要只读取当前表单中的文件名、大小、识别选项、增强计数和认证选择；不读取 Key、不请求校验或产生预览版本。较窄窗口保持单列；正式预览仍由 ReviewPanel 独立展示，遵循原来的确认交接协议。

全局提示与字段卡片由同一个主列控制宽度。配置页初次加载失败时进入unavailable；已打开页面的事件连接中断则保留原phase、表单、API Key输入、预览及操作，由EventSource自动重连。连接状态只用于恢复提示，不作为HTTP可用性判断；各请求仍由后端检查并沿原错误处理，不额外GET会话或重建表单。cancelled／expired／handed_off保持独立终态说明，收到终态或卸载后关闭连接。

回听路由 `/review` 使用独立 `ReviewApp.vue`，复用转写页的page-shell、AppHeader、语言和主题。主标题为“回听校对”；录音名以纯文本放在“说话人名称”按钮之前，两项顶部操作等宽等高。播放器保留在弹性工作区底部，播放/暂停使用32px方形按钮内的基本图形。中间阅读区使用共享8px圆角，滚动区域外上下各留24px，逐句使用ElCard无阴影圆角卡片，卡片间隔8px，内边距上下8px、左右16px（窄屏12px）。正文14px、1.7倍行距，阅读与编辑共用文字边距和尺寸；焦点使用原生textarea的preventScroll避免进入编辑时跳动。时间、说话人和重置附在对应句子。时间使用Clock图标的无边框按钮，当前句时间仅加粗，文字颜色保持。

正文或说话人归属与原值不同时，段落显示绿色改动底色与绿色标记；当前播放句使用蓝色高亮，两种状态同时存在时保留蓝色播放高亮和绿色改动标记。单句可重置原值；底部“跟随当前句”旁的“下一处修改”使用无图标的有框按钮，按原句顺序循环定位，暂停播放后聚焦目标正文，没有修改时禁用。该导航只保存本页定位序号，不增加接口或任务状态。点击正文时使用[标准文字定位接口](https://developer.mozilla.org/en-US/docs/Web/API/Document/caretPositionFromPoint) `Document.caretPositionFromPoint()` 定位点击的文字位置，再进入原位编辑；无法取得对应位置或键盘进入时使用文本末尾。滚动跟随在正文编辑时不移动页面，说话人姓名在集中对话框编辑。

说话人对话框使用 `ElScrollbar`，列表高度上限为 `min(360px, 50vh)`；标题、说明和底部新增/完成按钮位于滚动区外。新增仍调用原 `useReview.addSpeaker()`，等待Vue更新后滚到列表末项并聚焦新增名称输入，焦点使用preventScroll避免移动外层页面；自动保存逻辑保持。

回听页在录音名旁以ElText小字显示“保存中”或“已保存”；本次导出成功使用ElMessage短提示，失败沿已有告示呈现，不缓存导出状态。提示区只在加载、音频转换、连接中断或错误等需要说明时出现。导出期间播放器继续响应播放和暂停。音频重选失败且录音仍不可用时保留重选入口，用户直接在系统窗口选择或取消，不增加页面等待/取消操作。不以播放或导出结果代表稿件保存完成。

Vite 将前端构建到 Skill 的 `scripts/asr_runtime/static/`，交付 index.html、app.js、app.css、favicon.svg 和第三方许可。用户不需要前端构建环境。开发 Node 要求由根 package.json 的 `^20.19.0 || >=22.12.0` 约束；Skill 使用固定 Node 24.21.0，满足该条件。具体环境前提与验证命令统一见下节。

## 开发与验证

在 Windows 10/11 x64 的仓库根目录运行；浏览器回归需要本机 Microsoft Edge。代码测试使用合成数据、本机HTTP服务和固定BL；安装环境需要联网，测试本身不会发起真实授权或云端识别。

全新检出可使用现有安装器准备专用合约工作目录。此目录不作为用户转写工作目录；已有开发环境可直接复用。下面的第一段只用于首次准备：

```powershell
$repoDir = (Get-Location).Path
$contractDir = Join-Path $repoDir '.runtime/dev-workspace'
New-Item -ItemType Directory -Path $contractDir -Force | Out-Null
$skillDir = Join-Path $repoDir 'skills/asr-transcription'
& "$env:SystemRoot/System32/WindowsPowerShell/v1.0/powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $skillDir 'scripts/bootstrap.ps1') -Workspace $contractDir
```

bootstrap成功后，使用该工作目录的基础Python准备仓库`.venv`，以便浏览器测试调用固定入口。业务库复用安装器已下载并核对的wheel；开发依赖单独安装，包含类型工具及官方Skill校验器需要的PyYAML：

```powershell
$runtimeDir = Join-Path $contractDir '.asr-transcription'
$basePython = Join-Path $runtimeDir '.tools/python/python.exe'
& $basePython -I -X utf8 -m venv (Join-Path $repoDir '.venv')
$pythonPath = Join-Path $repoDir '.venv/Scripts/python.exe'
& $pythonPath -I -X utf8 -m pip install --no-cache-dir --no-index --find-links (Join-Path $runtimeDir '.runtime/wheels') --require-hashes --only-binary=:all: -r (Join-Path $skillDir 'scripts/requirements.txt')
& $pythonPath -I -X utf8 -m pip install --no-cache-dir -r requirements-dev.txt
$nodeDir = Join-Path $runtimeDir '.tools/node'
$env:PATH = "$nodeDir;$env:PATH"
$env:MEMOFLOW_BL_CONTRACT_WORKSPACE = $contractDir
npm ci
```

上述PATH只影响当前PowerShell进程。接续已有环境时重新设置这几个路径变量即可。`MEMOFLOW_BL_CONTRACT_WORKSPACE`应指向已安装当前固定BL的工作目录；缺失时部分合约会跳过，不能写成完整通过。`tests/support.py`的默认目录按BAILIAN_VERSION生成为`.runtime/bl-<版本>-workspace`；新机器应显式设置。环境和进程合约需要正常Windows执行权限，受限令牌下的拒绝访问应按权限说明处理。

按变更范围选择检查，完整发布复核采用：

```powershell
& $pythonPath -X utf8 -m unittest discover -s tests -t . -q
& $pythonPath -X utf8 -m mypy
npm run check:web
npm run test:web
npm run build:web
npm run test:browser
& $pythonPath -X utf8 scripts/check_docs.py
npm run check:uml
npm run render:uml
```

浏览器测试使用仓库`.venv`和构建后的静态资源，所以先构建。UML生成方法与主题见[图稿说明](UML.md)。文档检查验证本仓库使用的相对文件和章节链接，不检查外网可用性。Skill格式可使用当前Codex提供的`skill-creator/scripts/quick_validate.py`，传入`skills/asr-transcription`；PyYAML来自上述开发依赖，校验器不复制进仓库。格式通过还须通过入口场景推演，不能代替实际流程检查。

人工回听的本机用例与HTTP边界分别由 `tests/test_review.py`、`tests/test_review_web.py` 验证，使用合成JSON与录音，不调用云端。长列表页面验收可在完成前端构建后运行 `& $pythonPath -X utf8 -m tests.review_browser_server --workspace .runtime/新的回听验收目录`：夹具生成一千秒单声道录音、一千句结果和原始三格式文档，输出listening回执供浏览器打开。目录必须位于仓库.runtime内，已存在fixtures时拒绝覆盖；结束后保留合成数据。HTTP测试通过不代表实际浏览器播放、布局或Office视觉检查已经通过，实际范围记录在ACCEPTANCE。

发行包构建使用`scripts/build_zip.py`。轻量包直接生成；完整版用`--runtime-directory`指向与`runtimes.json`摘要匹配的两个官方ZIP目录。打包测试检查固定文件集、当前README、manifest和源码一致性；生成文件放`dist`，实际运行结果追加[ACCEPTANCE](ACCEPTANCE.md)。本机测试、真实用户授权、云端识别与Office视觉排版分别记录验收范围。

## 安装实现

首次安装使用完整版，由 Windows PowerShell 执行 `scripts/bootstrap.ps1 -Workspace`，核对 `scripts/runtimes.json` 中的固定摘要，再从包内 `assets/runtimes` 解压原始 ZIP 到工作目录 `.asr-transcription/.tools/python` 和 `.tools/node`。Python 为安装管理器的完整 ZIP，含 Tk、venv 和 ensurepip；Node ZIP 含配套 npm。PowerShell 随后用私有 Python 调用现有 `asr.py --workspace ... bootstrap`，pip/npm 依赖安装仍由 Python 用例负责。

后续自动下载轻量包，保留已安装运行时；依赖准备直接由现有基础 Python 进入同一个 Python bootstrap，不重复走运行时准备。npm 的位置由私有 Node 目录派生，使用该 Node 执行 npm-cli.js。源码安装或显式恢复缺少包内归档时，原 PowerShell 工具仍支持工作目录缓存和官方来源下载；此分支不属于正常轻量更新。

运行命令始终使用工作目录内的 Python/Node 绝对路径。安装不注册系统 Python，不修改全局 PATH、npm registry 或用户的其他环境；网络和组织策略导致的失败仍按实际错误停止。bootstrap 与 doctor 共用 `installed_python_versions()`，在同一个 venv 子进程中核对平台、`sys.base_prefix` 和依赖加载及版本。旧版系统环境或迁移后路径不符时保留并停止；结束使用环境的任务后仅重建 `.venv`，凭据、BL 安装、任务与结果保留。doctor 的 `python_base` 是诊断进程信息，实际 venv 绑定从目标 venv 子进程读取，不以调用者路径代替。

该本地探针用退出码2表示绑定不符、3表示依赖缺失，其余执行失败报告实际退出码；只有依赖缺失或版本不匹配才进入依赖安装。bootstrap 成功已经包含必要验证，正常更新后不再额外调用 doctor。BL 包信息由调用方读取一次，可用性检查直接启动固定入口并核对运行版本，正式业务调用仍独立核对当前 BL 版本。

升级使用 `bootstrap --cleanup-old-cache`：环境全部准备成功后，`installation.prune_download_cache()` 按当前Python依赖锁与pip版本删除旧wheel，按npm锁保留当前实际包名及版本。实际安装了依赖或BL时也清理旧缓存；普通环境复用不额外扫描。清理数量放在cache_cleanup，失败单独放cache_cleanup_warning，保持已完成的环境准备结果。

Python始终使用`--no-cache-dir`，本项目只清理自己保存的.runtime/wheels。[pip官方说明](https://pip.pypa.io/en/stable/topics/caching/)区分原生缓存与下载目标。npm使用私有Node调用公开的cache ls/clean/verify，并显式指定工作目录的.runtime/npm-cache，索引和内容删除交给npm。[npm说明](https://docs.npmjs.com/cli/v11/commands/npm-cache/)及[11.19.0源码](https://github.com/npm/cli/blob/v11.19.0/lib/commands/cache.js)提供依据。旧包逐键clean后执行一次verify回收失效索引：同一旧包的官方源和镜像键可能共享内容，批量clean遇到已删除的共享内容会提前结束；真实隔离缓存已复现该问题。verify仅在删除旧键后使用，属于npm缓存整理，不是重复的环境检查。

镜像缓存包含cdn.npmmirror.com/packages路径，原生cache ls按包规格筛选不能覆盖这类键，因此不能据此计算删除差集。本项目仅识别固定两源的registry路径及实际镜像CDN路径，按锁中的实际name处理npm别名包；元数据和未知键保留。真实缓存合约已验证旧条目删除后当前条目仍可读取。系统缓存、已装运行时、凭据、任务和输出不在此清理范围。

安装日志统一保存为 UTF-8。普通 pip 命令显式传入 `-X utf8`；Python 3.12 的 ensurepip 内部子进程使用本地编码，因此只在该调用按 `locale.getencoding()` 解码。二者均保持 `-I` 隔离模式，不修改标准库或系统编码。

Python 安装器继续按锁定版本准备依赖。先并行采样 PyPI 与阿里云镜像同一 pip wheel 前缀，排序只是当时短时吞吐，不保证全程速度。pip 自行处理有限连接重试、下载恢复与摘要检查；每阶段每源至多启动一次下载，最终失败才换源。完整 wheel 保存在私有目录，本机安装使用 `--no-index`。

首次安装 BL 时，`rank_npm_registries()` 复用 `_sample_download()` 比较 npm 官方源与 npmmirror 的固定 BL 包前缀。正文采样窗口从响应就绪后开始，评分包含连接等待。`_install_bailian()` 按顺序每源至多调用一次原生 `npm ci`，由 `--registry` 切换下载位置，保留锁定版本及 integrity；`fetch-retries=2` 与 `prefer-offline` 分别交给 npm 处理有限重试和缓存复用。正常下载没有额外总时限。

BL 安装资源只有 `scripts/bailian/package.json` 与 `package-lock.json`，由 npm 下载官方 `2.10.5` 包及锁定依赖。安装检查要求当前固定版本；版本不匹配时按 [错误说明](../skills/asr-transcription/references/errors.md#常见问题处理)仅重新安装工作目录的 BL，凭据及任务位于独立目录。两个发行包均使用同一套官方依赖锁。

`run_installer()` 可将 stdout 写入调用方持有的临时文件，stderr 仍逐行写入安装日志和进度。BL 安装从 npm `--json` 的 `error.code` 判断是否换源：已识别连接、请求/正文超时、404/408/429/5xx、下载校验错误可以切换；权限、磁盘、锁冲突、未知错误或无法解析的结果立即停止。临时 JSON 关闭后删除，无需新的持久状态或日志解析器。第二次 ci 重建的是本次新安装目录，已有冲突安装仍由 bootstrap 在开始前拒绝。两源失败保留 bootstrap.log；缓存复用不等于文件断点续传，这些策略不扩展为云端转写重试。

Windows 虚拟环境的 Python 启动器可能另起实际工作进程。本机有限命令 `run_process()` 和安装命令 `run_installer()` 持有本次 `Popen`，在超时、中断或异常退出时共用 `stop_process_tree()` 结束其进程树；正常完成不触发停止。选择窗口只依赖标准库与 tkinter，直接使用 `sys.base_prefix/python.exe`，使取消动作对应实际窗口进程。停止范围限于本次创建的进程，不枚举其他 Python 或浏览器进程；BL 登录和识别沿用各自的生命周期。

## 发行构建

`scripts/build_zip.py` 按固定逐文件映射生成两个 ZIP：Skill 资源直接作为归档根，加上仓库根最新版 README.md 和 README.en.md。完整包 `asr-transcription.zip` 额外包含 `assets/runtimes/python-3.12.10-amd64.zip` 与 `assets/runtimes/node-v24.21.0-win-x64.zip` 两个原始官方归档；轻量包 `asr-transcription-lite.zip` 不附运行时。两包代码与说明相同，Python 依赖和 BL 安装仍需联网。README 字节原样入包，仓库资料用完整 GitHub 链接，语言切换与 LICENSE 用包内链接。排除开发 doc、AGENTS、UML、测试、Vue/TS 源码、构建工具、已安装依赖、凭据和用户数据。

在仓库根目录使用开发环境构建。未提供 `--runtime-directory` 时输出轻量包；提供包含两个原始官方 ZIP 的目录时，先校验摘要，再输出完整包：

```powershell
& ./.venv/Scripts/python.exe scripts/build_zip.py
& ./.venv/Scripts/python.exe scripts/build_zip.py --runtime-directory '替换为两个官方ZIP所在目录'
```

默认输出到 `dist/`，已有同名文件不会覆盖；需要另选目标时使用 `--output`。

开发在 dev，master 保存正式发布里程碑。版本以根 package.json 为准，在验收发布时递增，并同步锁文件、标签和Release。正式标签和附件发布后保留，新版本使用新标签。依赖版本由各自锁文件维护，历史实现和发布记录通过Git追溯。
