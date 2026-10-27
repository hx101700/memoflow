# 运行与使用

此Skill将单个本地录音转写为原始JSON和Word、Excel、Markdown转写校对稿。模型固定为`qwen-audio-3.1-asr-flash-filetrans`，地域为北京。

[最新 Release](https://github.com/hx101700/memoflow/releases/latest) 中的完整版 `asr-transcription.zip` 用于首次安装，附带 Python、Node.js 及配套 npm。后续更新由工具自动下载 `asr-transcription-lite.zip`，复用原工作目录中的运行时。Python依赖与百炼 CLI（BL）仍按锁文件联网安装。

## 运行准备

首次安装或更新都使用README中的统一安装请求。收到新ZIP后，Codex按[安装或更新Skill](../SKILL.md#安装或更新-skill)检查实际安装情况；已有安装按下方[ZIP重新安装](#zip重新安装)替换旧发行资源，沿用原工作目录并保留凭据、任务和结果。

支持已更新、包含系统 curl 的 Windows 10/11 x64。首次安装使用系统自带的 Windows PowerShell，将完整 Python 3.12.10、Node.js 24.21.0（含 npm 11.19.0）及依赖准备到工作目录，无需预先安装 Python 或 Node.js。固定版本和摘要随 Skill 维护，系统已有版本不会被更改。

首次安装先核对宿主提供的操作系统与架构，确认使用 Windows 10/11 x64 安装包。复用本次会话已约定的工作目录；无约定时使用当前 Codex 任务的现有目录并告知用户。只有缺少可用目录或目录位于 Skill 内时才另行选择。Skill 目录存放代码和参考资料；工作目录保存环境、凭据、任务和结果。录音可从本次对话附件带入，或在网页中选择。通过 `scripts/asr.py` 执行的业务命令都显式传入同一个 `--workspace`，保存位置应在 Skill 目录之外。

在 PowerShell 中准备独立运行环境。下载使用 Windows 的 TLS 实现，需要正常网络执行权限；Codex 工具支持时，从首次安装就传 `sandbox_permissions=require_escalated`，避免受限令牌导致 `SEC_E_NO_CREDENTIALS`。遵循宿主工具权限机制，普通 Windows 终端可直接运行：

```powershell
$skillDir = '替换为此Skill的安装目录'
$workspaceDir = '替换为用户工作目录'
$scriptPath = Join-Path $skillDir 'scripts/asr.py'
$bootstrapPath = Join-Path $skillDir 'scripts/bootstrap.ps1'
& "$env:SystemRoot/System32/WindowsPowerShell/v1.0/powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $bootstrapPath -Workspace $workspaceDir
$pythonPath = Join-Path $workspaceDir '.asr-transcription/.venv/Scripts/python.exe'
```

首次安装的 `bootstrap.ps1` 使用完整版 `assets/runtimes` 中的原始 Python/Node ZIP，核对固定摘要后解压到工作目录 `.asr-transcription/.tools/python` 与 `.tools/node`，随后调用 Python `bootstrap` 安装依赖。基础 Python 包含 tkinter、venv 与 ensurepip，Node.js 附带 npm。正常轻量更新保留这些已安装目录和包内归档，直接使用原绝对路径。

从源码准备环境或显式修复时，缺少包内运行时归档的安装器仍可复用工作目录缓存、从官方来源下载。完整 ZIP 保存在 `.asr-transcription/.runtime/runtime-downloads`；未完成的 `.part` 由 curl 续接，摘要失败时丢弃。连续120秒几乎没有数据传输时按curl有限重试处理。两个包均不附带已安装的业务依赖。ExecutionPolicy Bypass 仅影响本次PowerShell进程。

Python `bootstrap` 从 Skill 中的 Python/npm 依赖锁安装到工作目录，完成检查后返回安装状态及 `key_file`。成功后即可使用，后续步骤复用此次结果；`doctor` 用于主动诊断和排障，无需在成功后再跑一遍。API Key 和任务保留。安装进度输出到 stderr，依赖安装日志保存在本机，stdout 输出最终 JSON。等待同一次进程结束，正常下载没有总耗时上限。

需要下载Python依赖时，先比较官方PyPI和阿里云镜像的文件前缀速度，优先使用较快来源，并准备锁定的pip 26.2.1。pip自行恢复中断下载，单个业务依赖最多恢复5次；该来源最终失败后，自动尝试另一个来源一次。已完整下载的wheel保存在`.asr-transcription/.runtime/wheels`供后续安装复用，换源不跨进程续接未完成的文件。两个来源都失败时停止并保留`python-install.log`，不要在Codex中额外循环重跑或改动摘要。

首次安装 BL 时，也先比较 npm 官方源和 npmmirror 的包文件前缀速度，再由 `npm ci` 按锁文件安装。BL、core、commands、runtime 均固定官方 `2.5.1`，上传使用该版本原生支持的 BL timeout。下载失败先由 npm 处理有限重试；收到已识别的下载或来源错误（如连接中断、404/5xx、下载校验失败）后，安装器换到另一来源。每源至多启动一次安装进程；权限、磁盘、依赖锁或未知错误直接停止。npm 自行校验和复用工作目录中的缓存，不承诺续接未完成文件。最终失败时保留 `bootstrap.log`，不修改全局源、不放宽完整性校验，也不额外循环重装。

需要诊断环境时运行：

```powershell
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir doctor
```

虚拟环境解释器缺失或无法运行、但私有基础 Python 仍可用时，使用 `& (Join-Path $workspaceDir '.asr-transcription/.tools/python/python.exe') -E -S -B -X utf8 $scriptPath --workspace $workspaceDir doctor`。基础运行时尚未准备时，先执行上面的 PowerShell 入口。诊断只报告问题，修复按实际回执处理。

Python 依赖从 HTTPS PyPI 或阿里云镜像下载并校验摘要，然后从本机 wheel 安装。BL 由私有 Node 配套的 npm 按锁安装，更换来源不改变版本或摘要。安装不修改系统 PATH、注册表或全局包。独立运行时减少版本和路径冲突，但仍需可用网络、目录写入权限及正常 Windows 交互桌面；组织策略或安全软件阻止执行时，应按具体错误处理，不能保证所有机器都能运行。

虚拟环境记录创建时的基础 Python 路径，不能把已安装的工作目录视为可随意搬迁的便携包。旧版由系统 Python 创建的环境也不属于当前私有运行时。安装器发现基础路径不一致时保留旧环境并停止；先结束使用该环境的任务，再仅删除工作目录中的 `.asr-transcription/.venv`，按[复用已有运行时](#复用已有运行时)用基础 Python 重建。API Key、BL 配置、任务和结果保留，不删除整个 `.asr-transcription`。

### 复用已有运行时

更新后的依赖准备使用现有基础 Python，直接进入同一个 Python bootstrap：

```powershell
$basePythonPath = Join-Path $workspaceDir '.asr-transcription/.tools/python/python.exe'
& $basePythonPath -E -S -B -X utf8 $scriptPath --workspace $workspaceDir bootstrap
```

| 组件 | 工作目录内的固定位置 | 用途 |
| --- | --- | --- |
| 基础 Python | `.asr-transcription/.tools/python/python.exe` | 更新 Skill、准备依赖及诊断修复 |
| 虚拟环境 Python | `.asr-transcription/.venv/Scripts/python.exe` | 执行网页、转写与导出 |
| Node.js | `.asr-transcription/.tools/node/node.exe` | 执行 BL 与配套 npm |
| npm | `.asr-transcription/.tools/node/node_modules/npm/bin/npm-cli.js` | 由上述 Node.js 按依赖锁安装 BL |

这些路径均相对于同一个工作目录。更新复用已有运行时，依赖符合新锁时直接返回成功；依赖需要变化时按现有安装流程处理。新工作目录尚无运行时或原运行时需要修复时，使用完整版的PowerShell准备入口。

升级后在上述 bootstrap 命令末尾加 `--cleanup-old-cache`，环境准备成功后清理本工作目录的旧依赖下载缓存；实际安装了Python依赖或BL时也会自动执行清理。当前锁对应的版本与当前pip wheel保留，常规已就绪环境的bootstrap不额外扫描缓存。

Python下载文件位于 `.asr-transcription/.runtime/wheels`，安装一直使用 `--no-cache-dir`；npm缓存限定在 `.asr-transcription/.runtime/npm-cache`。npm通过其原生命令删除已识别的旧版本键，镜像CDN和作用域包按实际下载格式识别，未知键保留。系统级pip/npm缓存、已安装运行时、凭据、任务及结果均不在清理范围内。清理失败通过 `cache_cleanup_warning` 说明未完成项，环境准备成功结果不因此改为失败。

## ZIP重新安装

先完整解压新ZIP并核对 `SKILL.md` 和包内发行清单，再等待所有使用同一 Skill 安装目录的命令结束。确认旧目录是专用 Skill 资源目录、与用户工作目录分离后，用新包重新建立该资源目录，清除旧代码、旧资源及旧更新记录，避免覆盖解压留下已移除文件。若混有非Skill文件，先核对并保留其归属，不直接删除整个目录。

此操作是用户主动提供ZIP后的重新安装。原工作目录中的 `.asr-transcription`、凭据、任务与输出保持原位；替换后的 Skill 按新安装建立更新记录。重新读取新 `SKILL.md`，按[复用已有运行时](#复用已有运行时)执行 `bootstrap --cleanup-old-cache`。源ZIP由用户持有，本次用于解压的暂存目录在完成后清理，不保留旧Skill备份。

## 自动更新

Codex 开始新的使用时，用工作目录内的基础 Python 调用独立更新入口。它只依赖标准库，`.venv` 或业务依赖尚未就绪时也可先更新；基础 Python 尚不存在时先按“运行准备”安装。

执行前告知用户将检查更新；发现新版时根据程序进度说明当前版本、目标版本和正在更新，完成后用文字报告实际结果。检查失败或因活动任务暂缓时也明确说明。

```powershell
$updatePython = Join-Path $workspaceDir '.asr-transcription/.tools/python/python.exe'
& $updatePython -I -X utf8 (Join-Path $skillDir 'scripts/update.py')
```

仅本次用户明确提出“更新语音转写 Skill”“检查 asr-transcription 更新”时，调用同一入口并增加 `--check-now`。上下文可补全用户所指的 Skill；普通转写请求仍按日检缓存执行，不因已在使用此 Skill 而加该参数。该次主动检查可越过当天缓存，但同样先记日期；之后的自动调用读取这次结果，不再联网。主动检查仍受活动命令的锁保护。其他项目或 Skill 的更新请求不触发此入口。

更新器请求 MemoFlow 的最新正式 GitHub Release。发现更高版本时，下载该版本的 `asr-transcription-lite.zip`，核对下载大小、GitHub 提供的 SHA-256 和包内版本与文件清单，完整读取 ZIP 后直接覆盖 Skill 文件。旧清单中已经移除的运行文件会删除；完整包附带的运行时归档、用户凭据、工作目录环境、任务和结果保留。更新过程不创建备份。

同一个 Skill 安装目录共用 `.skill-update-state.json`。按机器本地日期每天最多联网检查一次，日期在网络请求前写入，未发现更新或请求失败当天也不再检查。`checked_today` 返回上次结果，不再次请求 GitHub；它不表示上次一定检查成功。更新只跟随正式版本，不跟随 dev 的同版本改动。

业务命令在整个运行期间共享持有 `assets/update.lock` 的只读句柄；更新器必须独占打开同一文件才能检查和覆盖。有其他工作目录正在用这个 Skill 时返回 `deferred`，尚未联网，也不占用当天的检查机会；本次请求继续使用当前安装。更新中启动的业务命令会提示稍后再运行，已有任务不会被替换脚本。关闭页面标签不等于服务结束。

`updated` 返回后，Codex 重新读取 `SKILL.md`，按[复用已有运行时](#复用已有运行时)直接用基础Python运行 `bootstrap --cleanup-old-cache`。代码和文档已经更新不代表所有工作目录的依赖都已更新；已有 BL 版本不符时，按[环境修复](errors.md#常见问题处理)只重新安装该目录的 BL，再完成 bootstrap。后续在其他工作目录使用同一 Skill 时，也应按当前 Skill 的依赖要求准备环境。凭据和结果不迁移。

即使返回 `latest` 或 `checked_today`，开始转写前仍须有本工作目录按当前 Skill 准备成功的证据；没有时先运行一次 bootstrap。共享 Skill 的当天检查结果不替代各目录的依赖准备，也不会在交接或登录返回后重复触发检查。

从v0.1.2起，正式安装包包含 `skill-manifest.json` 与自动更新入口，可获取后续更高的正式版本。v0.1.0和v0.1.1没有该入口，先通过新ZIP更新；没有清单的源码目录不参与自动更新。更新器不覆盖同版本的开发改动。

检查或下载失败时继续使用当前安装版本。覆盖文件时出错，更新器用内存中的原内容恢复已修改或删除的文件，移除本次新增文件和目录；下载与暂存文件在本次调用结束时清理，不保留备份。已写入的当天检查记录保留，以免自动重复联网。首次检查日期写入失败时尚未联网、安装文件未改，返回 `repair_required=false`；旧清单、日检状态或读取保护无法确认安装完整性，以及恢复未完成时，返回 `repair_required=true` 和非零退出码，先停止业务并修复。问题处理见[更新问题](errors.md#skill更新问题)。

`record_error` 单独报告检查记录写入失败：首次写入失败不联网，最终写入失败保留本次实际安装结果。新版本清单已完整发布时，后续调用可据此识别已完成的更新，并沿用当天结果。

按本次请求衔接后续：只检查或更新 Skill 时，完成上述更新处理并报告后结束。请求新转写时，`failed` 且 `repair_required=false`、当天失败结果的 `checked_today`、`deferred`、`unmanaged` 或附带 `record_error` 都不终止该请求；按原环境准备要求继续执行下方开页步骤。仅 `repair_required=true` 要先修复安装。

## 认证与运行

先打开本机转写页面，由用户填写、预览并将确认消息发给 Codex。成功交接后，Codex 按任务的认证方式决定是否登录；本机页面和 BL 授权页面是两个用途不同的页面。环境诊断 doctor 不执行登录。

### 控制台登录

网页保持“使用指定 API Key”未勾选。缺少模型凭据时运行以下命令，保持原进程等待授权。登录会启动系统默认浏览器：Codex 支持 `sandbox_permissions` 的执行工具从第一次调用就使用 `require_escalated`。程序在受限令牌中停止，避免以该权限启动 BL 和浏览器；普通 Windows 交互终端可直接执行。

```powershell
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir login
```

官方 BL 打开系统默认浏览器，并负责授权会话、回调和凭据保存。用户完成授权后回复“已完成”；Codex 读取原 login 会话的最终回执，继续同一个任务，不再要求确认上传和费用。需要用户操作时保留进程并结束当前回复，不另开授权页，不通过 computer-use 验证页面。

`WAITING_FOR_LOGIN` 是启动提示。最终回执包含 BL 状态查询结果；`configured=true` 表示本机模型凭据存在，不证明在线调用一定成功。失败或 BL 会话结束仍缺少凭据时报告结果并停止。BL 原生有效期见[固定版本依据](model.md#windows控制台登录)，项目不增加登录总等待上限。

凭据位于当前工作目录的 `.asr-transcription/.state/bailian`；其他目录或系统级 BL 登录不代表此处已经配置。状态未知时运行一次 `console-status`；已有模型凭据且没有已知鉴权失败时直接复用。仅 `console_configured=true` 而 `configured=false` 表示缺少模型凭据。账号准备见[官方指引](https://help.aliyun.com/zh/model-studio/first-api-call-to-qwen)。

### 指定 API Key

在页面选择“使用指定 API Key”，填写或修改北京地域的百炼 API Key。已有 API Key 加载到密码输入框，默认遮蔽。点击“保存 API Key”可单独保存到工作目录的 `.asr-transcription/.env`；普通转写点击“确认并预览”时也会保存待提交的修改。

此模式不运行 login。正式执行读取该文件当时的 API Key，通过 BL 子进程环境传入。API Key 不进入任务配置、聊天、命令参数或浏览器持久存储。单独更换 API Key 时无需录音或创建任务；保存后告知 Codex 完成，由它取消本次编辑会话。

### 后续使用与凭据有效性

两种模式都由 BL 使用模型 API Key 调用 ASR：控制台模式读取当前工作目录的 BL 配置，指定 API Key 模式读取私有 `.env`。控制台 access_token 服务于控制台能力，不能替代模型 API Key。

`console-status` 复用 `bl auth status`，`api-key-status` 检查本机 `.env`；都不发起在线验证。已有凭据直接用于实际转写，由 BL 返回的 HTTP 状态、API code 和说明判断结果。普通 API Key 没有固定有效期，删除 API Key、账号或权限变化会影响可用性；临时 API Key 另有有效期，见[官方说明](https://help.aliyun.com/zh/model-studio/get-api-key)。修复方式与新任务边界见[凭据修复](errors.md#鉴权失败与重新配置)。

## 打开转写页面

```powershell
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir serve
```

先实际执行命令，保留同一持续进程并等待 `event=listening`。命令默认请求系统浏览器打开页面；宿主有打开链接能力时使用 `serve --no-browser`，收到回执后，用宿主现有工具请求打开其中的 `url` 一次。收到监听回执且打开请求已提交后，才请用户填写并结束当前回复；文字说明“现在打开”不能代替启动与打开动作。正常使用无需 computer-use、截图或页面元素检查。原生文件与目录窗口需要正常 Windows 交互桌面，遵循执行工具的权限机制。

当前版本支持将用户本次提供的录音附件或本机路径带入同一配置页：

```powershell
$audioPath = '替换为本次录音的绝对路径'
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir serve --audio $audioPath
```

附件位置以用户提供或宿主明确标注的路径为准。多个录音时先确定本次处理的一个；附件没有可读取的本机路径时，执行不带 `--audio` 的 `serve`，正常打开页面后选择文件。录音带入时登记原路径和大小，网页显示文件名及选中状态；读取失败在音频区域说明原因，可重新选择。媒体检测与完整摘要在点击“确认并预览”时完成。

启动回执 `event=listening` 包含 `session_id`、`url`、`expires_at`、`pid`、`browser_request`，以及启动清理的 `cleanup` 数量和警告。`browser_request` 的 `skipped` 表示调用方负责开页，`requested` 表示已请求系统打开，`failed` 表示打开请求失败；不将这些值解释为“用户已看到页面”。只有打开报错或用户反馈异常时，按[页面打开问题](errors.md#页面打开问题)排查。

URL 为本机地址，不携带令牌。页面请求使用本机编辑会话 Cookie；CLI 从私有连接文件读取令牌。编辑会话编号 `session_id` 用于明确指定要交接的页面，不是密钥或云端任务编号；交接后产生的本机转写任务编号为 `job_id`。

## 网页配置

页面显示对话带入的录音，可点击音频选择区域更换文件；空页面通过同一区域调用系统文件窗口，Python 登记原文件位置。点击热词表上方的“导入 Excel”选择文件，在内存中读取；“下载模板”位于旁边。

页面有“填写”和“预览”两步。右上角可切换中文/English 及系统、浅色、深色外观；界面语言与音频语言分别设置。宽屏右侧的“当前设置”随表单更新并跟随滚动，便于随时核对；正式预览仍通过“确认并预览”进入。

1. 核对带入的录音，或选择一个音频文件。
2. 选择音频语言、说话人区分和参考人数。说话人区分初始开启，多声道会提示生成单声道 FLAC 副本，原文件保留。
3. 按需启用热词和上下文增强。热词可直接填写或导入 Excel，工具栏提供“下载模板”。导入去除表头和完全空白行，保留错误值供修改。表格序号从 1 连续显示，删除后重排；行数较多时在表格内滚动，表头固定。Excel 文件字节仅在内存中读取并填表，不生成磁盘副本。热词和上下文增强的输入仅在点击“确认并预览”时检查，错误在对应单元格或输入框中显示；编辑过程中保留原值。无法读取或表头不符的 Excel 在导入时提示文件问题。
4. 通过原生目录窗口选择 JSON 与文档保存位置，默认根目录为工作目录的 `transcriptions`。取消窗口保留原位置。
5. 点击“确认并预览”。错误留在对应输入位置；通过后进入独立预览视图，完整核对音频、选项、增强内容、认证方式及保存根目录。此时尚未产生任务编号，可点击“返回修改”。

同一热词只保留一行。所有重复行都会标红，权重相同也须由用户选择保留哪一行。上下文增强的输入问题会指出长度或字符位置，并保留原文。Excel 只用于导入，后续使用网页当前数组，原文件不修改；外部修改 Excel 后需重新导入。

修改一个单元格会清除该格的旧提示，其他错误继续保留。重复组删到一行才移除重复提示；新修改的内容在下次预览时检查。切换语言保留当前表格、滚动及错误位置，提示同步切换。关闭热词或上下文增强开关会清空对应内容，API Key 不受影响。

填写规则参见阿里云的[即时热词格式](https://help.aliyun.com/zh/model-studio/improve-asr-accuracy#hw_instant_fmt_h4)与[上下文增强](https://help.aliyun.com/zh/model-studio/improve-asr-accuracy#ctx_enhance_h2)，页面两个区域也提供入口。

确认无误后，点击“复制给 Codex”，把包含编辑会话编号的完整确认消息发送到原对话。例如：

```text
确认转写，编辑会话编号：<页面提供的 session_id>
```

Codex 使用本次用户消息中的编号调用交接代码，确认页面仍处于有效预览后才创建任务并固定设置。仅回复“继续”时，Codex 会请用户使用复制按钮，避免处理另一份页面。预览同时说明音频及启用的增强内容将发往百炼北京地域，可能产生调用费用；这次确认覆盖该任务，无需后续二次授权。

编辑会话从打开起有效 **2 小时**，操作不会延长。交接、取消或到期后，页面显示对应结束提示，网页服务退出，标签页由用户自行关闭。到期与取消清理会话临时记录，保留原文件和已经保存的 API Key；原录音直接供任务读取，转写结束前请保留文件及原路径。期限不影响已经交接的登录或转写。

同一运行服务可恢复仍在内存中的预览；填写过程没有逐次自动保存，服务结束后不能恢复未交接编辑。浏览器只持久保存当前页面来源的界面语言与主题，不保存录音、API Key、热词或上下文文本。

| 输入 | 当前要求 |
| --- | --- |
| 本机音频 | 对话中带入或通过系统窗口选择原文件，支持 MP3、WAV、M4A、FLAC 等；时长不超过 12 小时 |
| BL 实际上传文件 | 不超过 1 GB，需要合并声道时按转换后文件检查 |
| 热词表格 | 最多 2,000 个词；直接填写，或导入不超过 5 MB 的两列 `.xlsx` |
| 上下文增强 | 输入最多 400 个字符，包含期望识别的具体词语 |

GB 和 MB 按十进制计量。开启说话人区分时，官方建议不超过 2 小时。完整规则见[模型依据](model.md)。引号、换行和反斜杠按原文输入，无需手工转义。Windows 整条命令也有长度限制；交接时按实际任务路径检查，超限会保留预览，请返回修改、减少词条或缩短保存路径后重新预览。

## 交接与执行

Codex 按用户粘贴的编辑会话编号执行：

```powershell
$sessionId = '替换为本次用户确认消息中的编辑会话编号'
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir confirm --session $sessionId
```

成功回执给出 `job_id`、认证方式和保存位置。正在填写、预览未展示或已到期时，代码拒绝交接，不创建任务或上传。完整 Windows 命令过长时，同样在写入配置和回执前停止，保留预览以便返回修改，不占用执行。确认回执丢失时，以相同会话编号再次执行确认会读取同一份回执，不能产生第二个任务；见[会话交接恢复](errors.md#会话交接恢复)。

按所选认证方式准备后，执行一次：

```powershell
$jobId = '替换为交接回执中的转写任务编号'
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir transcribe --job $jobId
```

转写读取交接时保存的授权。Codex 告知已开始并等待同一进程完成；BL 负责临时上传、提交、轮询和原始 JSON 保存，Python 随后生成三种文档。成功后直接交付，无需另行 export；转写或导出失败、结果未知时停止对应业务阶段，不自动重传。更新、清理及记录写入的附带警告按所属命令的主结果处理，不能单凭警告认定业务失败。

上传和轮询各使用一小时等待预算，整个 BL 进程最多等待2小时5分；这不是预计完成时间。获取上传凭证仍为15秒。超时后保留原任务和已生成文件，按[错误说明](errors.md#转写超时)核对已知结果，不能仅凭录音大小或通用超时文本判断失败阶段。

取消尚未交接的页面使用 `cancel --session SESSION_ID`。它结束编辑会话，不能取消已经交接的云端任务。

文件位于所选根目录的 `JOB_ID/json/transcription.json` 和 `JOB_ID/documents/transcription.{docx,xlsx,md}`。转写校对稿保留原文、时间戳和启用时的说话人编号，标题为“源文件名 录音转写”。Word、Excel 使用等线字体。

## 查询与重新导出

```powershell
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir job-status --job $jobId
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir export --job $jobId
```

`job-status` 只读本地记录；`JSON_READY` 表示 JSON 可用，三种成品全部完成需 `documents_ready=true` 且 `delivery.status=COMPLETE`。`RUNNING` 不能证明进程存活或云端实时状态。

`export` 用于用户明确要求重新生成文件：核对已保存成功记录与原 JSON，覆盖固定目录中的三种同名文档，不重新识别。请先另存人工校对的成品，并等待当前导出结束。历史成功任务使用原模型标签；新识别固定当前模型。状态和失败处理见[错误说明](errors.md)。

## 中断与临时文件

关闭标签页不会终止本机服务。正常交接、取消或到期后，服务等当前请求结束，再清理会话暂存；原录音、正式 API Key、BL 凭据及结果保留。

服务被强制关闭时，清理可能未运行。下次在**同一工作目录**打开转写页，工具会回收“已经到期且原进程已结束”的旧会话，以及已结束进程留下的自有文档、状态和 Python 临时文件。仍在运行、状态无法确认、归属不完整的文件会保留；有问题时启动回执会给出警告。这不会自动恢复或重传转写。

不要为清理残留删除整个 `.asr-transcription`：其中还有凭据、环境、已交接任务与执行记录。工具不清扫系统 Temp，也不清除安装缓存或无归属的旧文件。未交接编辑仍需重新填写；已有任务用原 job_id 查询。

## 本机文件

| 内容 | 位置 |
| --- | --- |
| 独立 Python / Node.js | `WORKSPACE/.asr-transcription/.tools/python/` / `.tools/node/` |
| Python 依赖与 pip | `WORKSPACE/.asr-transcription/.venv/` |
| 百炼 CLI | `WORKSPACE/.asr-transcription/.tools/bailian/` |
| API Key | `WORKSPACE/.asr-transcription/.env` |
| BL 配置 | `WORKSPACE/.asr-transcription/.state/bailian/` |
| 活动编辑会话连接信息 | `WORKSPACE/.asr-transcription/.state/sessions/SESSION_ID/connection.json` |
| 成功交接回执 | 同一会话目录的 `receipt.json` |
| 转写任务配置与记录 | `WORKSPACE/.asr-transcription/.state/jobs/JOB_ID/` |
| 默认输出 | `WORKSPACE/transcriptions/JOB_ID/` |

连接令牌在会话结束时移除。会话回执与任务编号用于定位这次交接；凭据、录音和结果不写入 Skill 安装目录。工作目录可能属于用户自己的仓库，其敏感文件不能假定受 MemoFlow 的 Git 忽略规则保护。
