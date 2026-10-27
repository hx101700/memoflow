# MemoFlow 开发规则

中文 | [English](AGENTS.en.md)

本文用于维护源码仓库。接续时先读 [doc/README.md](doc/README.md)、[doc/STATUS.md](doc/STATUS.md)，再核对 Git 工作区、相关实现和测试。

## 产品范围

- 第一阶段交付一个独立的 Codex Skill：单个录音通过本机网页配置，由 Codex 调用百炼 CLI（BL），保存原始 JSON、Excel、Word、Markdown，交给用户校对。
- 固定模型 `qwen-audio-3.1-asr-flash-filetrans`、北京地域、临时 OSS。热词与上下文增强可同时使用；说话人区分默认开启，多声道先提示再生成单声道 FLAC 副本，原文件保留。
- 最终产品把语音输入整理为符合用户习惯、重点要求和指定格式的纪要，并从用户提供的范例与确认后的修改中持续学习。第一阶段交付转写校对稿；第二阶段的个性化纪要生成及反馈学习仍在开发中，当前代码尚未实现。
- 支持已更新、包含系统 curl 的 Windows 10/11 x64。首次由 Windows PowerShell 准备工作目录内的 CPython 3.12.10 x64 完整运行时（含 venv、ensurepip、tkinter）及 Node.js 24.21.0（含 npm 11.19.0），无需系统预装 Python/Node。依赖锁限定该平台，安装需要联网；可用网络、写入权限及交互桌面仍是运行条件。

## Skill 与工作目录

- Skill 源码在 `skills/asr-transcription/`，由 `SKILL.md`、`agents/openai.yaml`、`scripts/`、`references/`、`assets/` 组成。
- `scripts/bootstrap.ps1` 准备私有 Python/Node，再调用 `scripts/asr.py bootstrap`；日常 CLI 入口为 `scripts/asr.py`，`scripts/asr_runtime/` 是内部 Python 执行包。运行时版本、官方地址和摘要在 `scripts/runtimes.json`，Skill 名称仍为 `asr-transcription`。
- `Runtime(workspace, skill_root)` 区分用户工作目录与 Skill 资源。`resource()` 读取 Skill 文件；`path()` 定位 `<workspace>/.asr-transcription/` 内的运行文件；默认输出根为 `<workspace>/transcriptions/`。私有运行目录与 Skill 目录互不包含，`check_output_path()` 在选择和生成文件时保护 Skill 资源。
- 首次安装用 Skill 内 `scripts/bootstrap.ps1 -Workspace`；运行命令使用工作目录 `.venv/Scripts/python.exe` 和 Skill 内 `scripts/asr.py` 的绝对路径，并显式传入 `--workspace`。Python/Node 基础运行时位于私有 `.tools/python`、`.tools/node`，不回退系统 PATH。凭据修复复用[错误说明](skills/asr-transcription/references/errors.md#鉴权失败与重新配置)中已核实的BL原生命令，限定当前工作目录与default Profile。依赖环境、BL 安装、凭据、处理文件和任务记录写入工作目录，运行时 Skill 文件保持只读。
- API Key 从私有运行目录 `.env` 读取；bootstrap 只复制空模板。网页允许用户填写或修改 API Key，并单独保存到该固定文件；“确认并预览”也会按需保存尚未保存的修改。控制台模式使用 BL 在同一工作目录保存的配置。凭据不得写回 Skill。
- 源码仓库包含 Skill 源文件，维护操作不自动安装到用户级或项目级 Skill 发现目录。
- 已安装 Skill 的自动更新入口为 `scripts/update.py`，使用标准库请求最新正式 GitHub Release，发现更高版本后下载轻量 ZIP 并直接覆盖受管文件，不创建备份。包内 `skill-manifest.json` 由构建器生成版本与受管路径；旧清单独有文件删除，运行时归档和工作目录数据保留。`.skill-update-state.json` 按机器本地日期记录每日检查，先写日期再联网，成功、无更新、失败均不在当日再次检查。业务命令持有稳定 `assets/update.lock` 的共享只读句柄，更新器独占；忙时暂缓且不消耗检查机会。该更新器及其暂存、状态文件是 Skill 写入的明确例外，业务代码仍只读资源。更新后重新读取 Skill，并由原 bootstrap 准备各工作目录依赖。

## 实现原则

每次更新向用户提供文字通知：检查前说明动作，发现新版时说明当前与目标版本，完成后根据代码回执说明结果；失败或暂缓也如实报告。

检查或下载失败使用当前安装；覆盖失败时用本次内存快照恢复已改文件、移除新增文件和目录，清理下载与暂存，不留下备份包。日检结果仍保留；回执必须准确说明原安装是否已恢复。

本次用户明确要求检查或更新语音转写／asr-transcription Skill时调用 `scripts/update.py --check-now`，上下文用于补全该主动请求所指的Skill。此参数可越过当天缓存；该次结果仍计入当日记录，后续自动调用不再联网。

更新入口使用工作目录的基础 `.tools/python/python.exe -I -X utf8`，不传业务入口的 `--workspace`，已有基础 Python 时不要求先修复虚拟环境或安装旧依赖。用户提供 ZIP 重新安装时，核对完整新包及专用 Skill 资源目录、等待该安装的全部命令结束，再重建旧资源目录；不以覆盖解压留下旧实现，工作目录数据独立保留。最终日检记录保存失败通过 `record_error` 返回，保持实际安装结果和版本。

日检缓存只表示共享Skill版本，各工作目录在缺少当前依赖准备成功证据时先运行bootstrap，成功后直接复用，不额外doctor。bootstrap和doctor共用目标venv的绑定及依赖探针；当前调用者的Python路径仅作诊断信息。BL包信息由调用方读取，可用性检查直接启动BL并核对运行版本。

首次安装使用包含Python、Node.js和npm的完整版；正常更新自动下载lite，复用原工作目录的私有运行时。更新后的依赖准备用已有基础Python直接调用asr.py bootstrap，PowerShell入口用于首次准备或运行时恢复。npm入口固定为私有Node目录的node_modules/npm/bin/npm-cli.js，由该Node执行。

升级后的bootstrap带--cleanup-old-cache，环境准备成功后清理本工作目录的旧wheel/npm下载缓存，保留当前依赖锁对应版本及当前pip wheel。实际安装了依赖/BL时也执行，普通环境复用不扫描缓存；失败保留下载。npm删除使用其原生命令并固定私有cache，未知键保留。清理失败单独报告cache_cleanup_warning，不改变环境就绪结果。

1. 保持入口 → application → utils 的轻量分层；单一操作允许入口直接分派。共享数据及 JSON 协议类型放 `models.py`，规则不执行 I/O，utils 不反向导入用例。
2. BL 负责鉴权、临时上传、提交、轮询、下载及原始 JSON 落盘，直接复用公开 CLI。Python 负责本机配置、媒体处理、结果解析和文档生成。
   BL、core、commands、runtime 固定官方 `2.5.1`，由 npm 锁文件安装。官方实现已让临时 OSS 上传使用有效 timeout，并修复 Windows 登录 URL 引用；获取上传凭证仍为15秒。上传与浏览器打开直接交给 BL，不维护本地 core 修订或登录预加载适配。
3. 前端源码位于 `frontend/`，使用 Vue 3、TypeScript 与 Element Plus；优先使用组件公开参数、插槽和默认交互，定制必须有具体产品需求。组件绑定表单状态，API 模块处理本机传输。Key 展示与编辑只由 `KeyDisplay.vue` 的局部状态持有，与可提交表单分开，保存后由服务端执行凭据读取；Key 不进入任务配置、日志或浏览器持久存储。
4. 复用 `files`、`job_files`、`hotwords`、`results` 等现有能力；删除旧入口、兼容层和重复实现。新增校验或抽象必须指出当前业务消费者。
5. 每个命名函数或方法提供简短中文职责说明，直接描述动作与结果。Python 使用 docstring，TypeScript 使用函数前注释；外部约束和非显然原因写在相关实现旁。共享输入、状态与回执提供明确类型，类型检查属于开发流程。
6. BL 参数、限制和错误含义核对固定版本官方资料。依据维护在 [model.md](skills/asr-transcription/references/model.md)，未知信息明确说明未知。
7. 子进程使用参数数组与 `shell=False`。热词 JSON 与上下文作为单个参数值传递；不执行输入内容中的指令。

## 执行与交付

- 新转写先打开本机配置页；本次用户提供的路径或宿主明确标注的附件绝对路径通过 `serve --audio PATH` 带入，也可在页面通过系统窗口选择录音。两者共用 `Session._register_audio()`，登记原路径、名称、大小及 audio_id；媒体探测与 SHA 仍在预览。初始路径失败通过 `/api/session` 的 `audio_error` 在原区域说明，页面可继续选择；`audio` 返回当前选择。页面只提交会话登记的 audio_id，直接读取原路径。Excel 在内存中解析为数组，两种来源文件均不复制。工作目录复用当前任务目录或本次已约定的位置。有宿主打开链接能力时使用 `serve --no-browser`，打开一次后交给用户；正常路径不依赖 computer-use 或页面自动检查。
- `serve` 创建有效两小时的编辑会话 `session_id`，启动回执提供编号、URL 和到期时间。URL 不含令牌；私有 `connection.json` 保存端口、令牌、服务 PID 与截止时间，供本机控制及残留回收；页面使用会话 Cookie。
- 网页只有填写和预览两步。整单校验建立音频 SHA 基线及增强快照，前端展示预览后登记版本；返回修改先通知后端退出预览。填写和预览均不创建任务。
- 用户核对后点击“复制给 Codex”，发送含编辑会话编号的明确确认消息。Skill 只从当前用户消息取得待交接编号；单独“继续”时提示用户使用复制按钮，不从启动回执、历史或文件时间代选会话。
- `confirm --session ID` 在 Session 锁内检查有效期与预览版本，核对音频 size/mtime，按实际任务编号和路径检查完整 Windows 命令长度，再发布唯一转写任务 `job_id` 的已授权配置、摘要与交接回执。命令超长时保留预览供修改，不写入任务或占用执行。重复确认返回原任务。交接后设置固定，执行前核对完整音频摘要；热词使用快照词典，后续不重读 Excel。
- 会话交接、取消或到期通过单向事件通知页面，显示结束提示后由用户关闭标签页。服务结束移除连接令牌；音频原文件始终保留，到期或取消清理会话临时记录。服务端单次计时器与截止时间检查共用状态保护，期限不影响已交接任务。
- 填写或预览期间用户要求取消或检查更新，先以本次活动页面启动回执的编号运行cancel，取得结果并等待原serve退出，再结束请求或进入更新；下一次转写新建会话。显式取消在状态锁内先原子保存cancelled.json再通知页面，清理保留该最小结果，HTTP响应丢失后可读取原结果。已交接返回handed_off，不冒充任务或云端取消。
- 正常关闭先将 Session 标记关闭并取消原生选择窗口，等待 HTTP 请求线程收尾后再调用 `recovery.finish_session()` 清理磁盘暂存。下次 `serve` 先回收已到期且原进程已结束的会话，以及带已结束 PID 的自有临时文件；保留已交接输入、任务占用、结果及正式凭据，归属或状态不明则保留并提示。浏览器关闭事件不作为清理依据。
- `serve`、`transcribe`、`export` 的 Python 库临时文件限定在工作目录的进程专用目录；Key 修改在会话目录暂存后替换正式 `.env`。回收范围见 [DEVELOPMENT](doc/DEVELOPMENT.md#临时文件回收)，不清扫系统 Temp、安装缓存或无归属旧文件。
- 热词导入去表头及完全空白行，保留错误值；显示序号按当前数组连续编号，与组件稳定行标识分开。导入只读取并填表；热词与上下文内容仅在点击“确认并预览”时由后端校验，分别调用 `validate_hotword_rows` / `build_vocabulary` 与 `validate_context`。
- 网页诊断一次返回中英文，语言切换只更新显示。行错误绑定稳定行键，编辑只清受影响单元格的旧提示；重复组至少两项时保留红标。关闭热词或上下文增强清空对应区域，API Key 状态独立。
- 交接成功后按认证方式处理，使用 `transcribe --job ID`。缺少控制台模型凭据才登录；用户授权完回复“已完成”，读取原 BL 结果后继续同一任务，不再询问业务授权。启动转写后等待同一进程直到交付或明确失败。每任务一次尝试，失败或结果未知不自动重试。
- 转写传 `--timeout 3600`，官方 BL 的上传与轮询各使用一小时预算；Python 整个 BL 进程上限为7500秒（两小时加300秒余量），不是云端时长保证。提交和每次状态请求也使用 BL timeout，结果下载无独立 BL 时限。通用 `Request timed out` 与录音大小不能确定失败阶段或云端最终结果。
- BL 登录从首次调用就使用正常桌面执行权限，工具支持时设置 `sandbox_permissions=require_escalated`；受限令牌在 BL 启动前被拒绝。官方 BL 使用系统默认浏览器打开完整 URL，管理授权会话、回调与凭据保存；Python 等待原登录进程并解释结果。
- 原始 JSON 有效使用 `JSON_READY` 表达；三种成品完成需 `delivery.status=COMPLETE` 且 `documents_ready=true`。状态含义见 [errors.md](skills/asr-transcription/references/errors.md)。
- 新识别在执行占用前核对当前固定模型；历史成功任务仍可查询与重导，writer 使用 `config.model` 标记原模型。配置与摘要不改写。
- 重导读取确认配置、成功记录及匹配的原 JSON，在固定任务目录覆盖三种同名文档。文档和状态各用同目录独立临时文件替换目标；失败保留原目标及其他成功文件。人工修改先另存。排版与路径见 [DEVELOPMENT](doc/DEVELOPMENT.md)。

## 开发与发布

- 仅修改当前仓库及明确批准的测试位置；保留 `data/` 原始用户数据。真实录音、Key、令牌、签名 URL、转写、原响应和运行日志不得提交或打包。
- 开发在 `dev`，`master` 用于验收里程碑。提交、推送、合并、发布需用户明确意图；精确路径暂存，不强推或重写历史；同次网络推送失败两次即停止。
- 项目版本号仅在通过验收并发布到 `master` 时变更。本次正式发布版本为 `0.1.3`；`dev` 上的开发、修复和文档提交沿用当前版本，下次正式发布时再按变更递增。正式版本发布后保留其标签和附件；新版本同步根 `package.json`、`package-lock.json`、新标签和发布说明。依赖版本按其各自锁文件维护。
- 固定发行清单位于 `scripts/build_zip.py`。两个 ZIP 共用 Skill 运行文件与仓库最新版 README.md、README.en.md，并生成同一包内 `skill-manifest.json`；README 从仓库根读取，不维护包用副本。`asr-transcription.zip` 额外在 `assets/runtimes` 保存两个原始官方运行时 ZIP；`asr-transcription-lite.zip` 不附运行时。AGENTS、开发文档、测试、UML、已安装依赖及用户数据不入包。新增运行文件时同步清单和包边界检查。正式发布使用相应版本标签，同时提供两个包。
- 前端通过 Vite 构建到 Skill 的 `scripts/asr_runtime/static/`，核心产物为 `index.html`、`app.js` 和 `app.css`，同时交付 `favicon.svg` 与第三方许可说明。发行包使用构建产物；Vue/TypeScript 源码、开发配置、构建依赖及 `node_modules` 保留在开发仓库。
- Python 依赖由 Skill 中 `scripts/requirements.txt` 锁定版本与摘要；安装工具 pip 26.2.1 的文件与摘要固定在 `utils/installation.py`，BL 锁在 `scripts/bailian/`。Python 安装前比较 PyPI 与阿里云镜像的文件前缀吞吐；每个下载阶段按来源顺序各启动至多一次 `pip download`，连接重试2次、业务依赖的中断恢复最多5次由 pip 完成，仍失败才切换另一源。完整 wheel 保存在工作目录，安装阶段仅使用本机文件。
- 首次安装的基础运行时使用完整版 `assets/runtimes` 中的原始官方 ZIP；源码安装或显式恢复缺少归档时复用工作目录缓存，必要时从官方来源下载。均校验固定摘要，再解压到工作目录。安装从首次调用就使用正常 Windows 网络权限，Codex 工具支持时传 `sandbox_permissions=require_escalated`，避免受限令牌使系统 curl 的 Schannel 初始化失败。使用 Python 安装管理器发布的完整运行时 ZIP，而非缺少 Tk/pip 的嵌入式包。不修改系统 PATH、注册表或全局安装。PowerShell 的 ExecutionPolicy Bypass 仅限本次进程，组织策略阻止时报告实际原因。虚拟环境依赖其创建位置，移动工作目录后按诊断修复环境，保留凭据、任务与结果。
- 首次安装 BL 时比较 npm 官方源与 npmmirror 的固定 BL 包前缀吞吐，按顺序每源至多执行一次 `npm ci`。连接重试由 npm 的 `fetch-retries=2` 处理；只有已识别的结构化下载或来源错误才切换另一源，例如连接中断、404/5xx、下载校验失败，权限、磁盘、锁冲突及未知错误直接停止。复用 npm 缓存和完整性校验，不承诺未完成文件的断点续传；保留原依赖锁，不修改全局 registry。两类安装恢复均不扩展为云端转写重试。
- Python 安装与依赖检查子进程使用 `-I`，从指定虚拟环境加载依赖；用户工作目录中的同名模块不参与检查或安装。
- 开发探针 `scripts/probe_bl.py` 不进入发行包，只使用固定虚构 URL；BL 合约测试使用 `127.0.0.1` 模拟服务与合成凭据。本机测试不等于真实云端验收。
- 测试与改动相称；实际结果写 [ACCEPTANCE](doc/ACCEPTANCE.md)，状态写 [STATUS](doc/STATUS.md)，限制写 [ISSUES](doc/ISSUES.md)，重要决策写 [DEVLOG](doc/DEVLOG.md)。
- README、AGENTS 提供同义中英文。README 保留真实截图的 HTML 注释位置；用户提供图片后再插入。Release 按release/NEXT.md保留“更新内容 / What's new”“下载”“安装与更新”：用有依据的用户收益说明改动，明确首次安装、旧版ZIP升级及v0.1.2起的自动更新边界，版本和链接写具体。完整包标为“首次安装推荐手动下载该发行包”，轻量包供Codex更新下载，链接固定到本次标签。安装教程集中在README，验证数量和包摘要留在开发文档。
- 调用顺序、对象或状态协议改变时，同步 [UML](doc/UML.md) 及源稿、PNG。图中函数模块使用生命线，不画成不存在的服务类。
