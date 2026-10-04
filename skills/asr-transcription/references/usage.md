# 运行与使用

此Skill将单个本地录音转写为原始JSON、Word、Excel和Markdown，完成后由用户校对。模型固定为`qwen-audio-3.1-asr-flash-filetrans`，地域为北京。

## 运行准备

本机需要Windows 10/11 x64、CPython 3.12 x64（含venv、ensurepip和tkinter）、Node.js 18.17.0或更高版本及npm。依赖安装需要联网。运行时可从[Python](https://www.python.org/downloads/windows/)和[Node.js](https://nodejs.org/en/download)官方页面获取。

复用本次会话已约定的工作目录；无约定时使用当前Codex任务的现有目录并告知用户。只有缺少可用目录或目录位于Skill内时才另行选择。Skill目录存放代码和参考资料；工作目录保存环境、凭据、任务和结果，录音在网页中通过文件选择器添加。所有命令都显式传入同一个`--workspace`，保存位置应在Skill目录之外。

在PowerShell中准备位置并安装依赖：

```powershell
$skillDir = '替换为此Skill的安装目录'
$workspaceDir = '替换为用户工作目录'
$scriptPath = Join-Path $skillDir 'scripts/asr.py'
python -S -X utf8 $scriptPath --workspace $workspaceDir bootstrap
$pythonPath = Join-Path $workspaceDir '.asr-transcription/.venv/Scripts/python.exe'
```

bootstrap从Skill中的Python/npm依赖锁安装到工作目录的`.asr-transcription`，完成依赖检查后返回安装状态及`key_file`。成功后即可使用环境；doctor用于故障诊断。已有可用环境直接复用，已有Key文件保留。安装进度持续输出到stderr并同步写入本机日志；stdout输出最终JSON。正常下载没有总耗时上限，等待同一次进程结束。

需要下载Python依赖时，先比较官方PyPI和阿里云镜像的文件前缀速度，优先使用较快来源，并准备锁定的pip 26.2.1。pip自行恢复中断下载，单个业务依赖最多恢复5次；该来源最终失败后，自动尝试另一个来源一次。已完整下载的wheel保存在`.asr-transcription/.runtime/wheels`供后续安装复用，换源不跨进程续接未完成的文件。两个来源都失败时停止并保留`python-install.log`，不要在Codex中额外循环重跑或改动摘要。

需要诊断环境时运行：

```powershell
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir doctor
```

工作目录的虚拟环境解释器缺失或无法运行时，使用首次准备环境的 CPython 3.12 执行 `python -S -X utf8 $scriptPath --workspace $workspaceDir doctor`。诊断只报告问题，修复按实际回执处理。

Python依赖从HTTPS PyPI或阿里云镜像下载并校验摘要，然后从本机wheel安装。BL由npm按锁文件安装，失败停止。Skill不附带Python、Node、wheel或已安装依赖，不修改系统PATH或全局包。

## 认证与运行

先打开本机转写页面，由用户填写、预览并将确认消息发给 Codex。成功交接后，Codex 按任务的认证方式决定是否登录；本机页面和 BL 授权页面是两个用途不同的页面。环境诊断 doctor 不执行登录。

### 控制台登录

网页保持“使用指定 API Key”未勾选。缺少模型凭据时运行以下命令，保持原进程等待授权。登录会启动系统默认浏览器：Codex 支持 `sandbox_permissions` 的执行工具从第一次调用就使用 `require_escalated`。程序在受限令牌中停止，避免以该权限启动 BL 和浏览器；普通 Windows 交互终端可直接执行。

```powershell
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir login
```

适配将 BL 的完整授权 URL 交给系统浏览器一次，保留原授权会话、回调和凭据保存。用户完成授权后回复“已完成”；Codex 读取原 login 会话的最终回执，继续同一个任务，不再要求确认上传和费用。需要用户操作时保留进程并结束当前回复，不另开授权页，不通过 computer-use 验证页面。

`WAITING_FOR_LOGIN` 是启动提示。最终回执包含 BL 状态查询结果；`configured=true` 表示本机模型凭据存在，不证明在线调用一定成功。失败或 BL 会话结束仍缺少凭据时报告结果并停止。BL 原生有效期见[固定版本依据](model.md#windows登录转交)，项目不增加登录总等待上限。

凭据位于当前工作目录的 `.asr-transcription/.state/bailian`；其他目录或系统级 BL 登录不代表此处已经配置。状态未知时运行一次 `console-status`；已有模型凭据且没有已知鉴权失败时直接复用。仅 `console_configured=true` 而 `configured=false` 表示缺少模型凭据。账号准备见[官方指引](https://help.aliyun.com/zh/model-studio/first-api-call-to-qwen)。

### 指定 API Key

在页面选择“使用指定 API Key”，填写或修改北京地域的百炼 Key。已有 Key 加载到密码输入框，默认遮蔽。点击“保存 API Key”可单独保存到工作目录的 `.asr-transcription/.env`；普通转写点击“确认并预览”时也会保存待提交的修改。

此模式不运行 login。正式执行读取该文件当时的 Key，通过 BL 子进程环境传入。Key 不进入任务配置、聊天、命令参数或浏览器持久存储。单独更换 Key 时无需录音或创建任务；保存后告知 Codex 完成，由它取消本次编辑会话。

### 后续使用与凭据有效性

两种模式都由 BL 使用模型 API Key 调用 ASR：控制台模式读取当前工作目录的 BL 配置，指定 Key 模式读取私有 `.env`。控制台 access_token 服务于控制台能力，不能替代模型 Key。

`console-status` 复用 `bl auth status`，`api-key-status` 检查本机 `.env`；都不发起在线验证。已有凭据直接用于实际转写，由 BL 返回的 HTTP 状态、API code 和说明判断结果。普通 Key 没有固定有效期，删除 Key、账号或权限变化会影响可用性；临时 Key 另有有效期，见[官方说明](https://help.aliyun.com/zh/model-studio/get-api-key)。修复方式与新任务边界见[凭据修复](errors.md#鉴权失败与重新配置)。

## 打开转写页面

```powershell
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir serve
```

命令持续运行，默认请求系统浏览器打开页面。宿主有打开链接能力时使用 `serve --no-browser`，收到启动回执后打开 URL 一次，随即让用户操作。正常使用无需 computer-use、截图或页面元素检查。原生目录窗口需要正常 Windows 交互桌面，遵循执行工具的权限机制。

启动回执 `event=listening` 包含 `session_id`、`url`、`expires_at`、`pid`、`browser_request`，以及启动清理的 `cleanup` 数量和警告。后者的 `skipped` 表示调用方负责开页，`requested` 表示已请求系统打开，`failed` 表示打开请求失败；不将这些值解释为“用户已看到页面”。只有打开报错或用户反馈异常时，按[页面打开问题](errors.md#页面打开问题)排查。

URL 为本机地址，不携带令牌。页面请求使用本机会话 Cookie；CLI 从私有连接文件读取令牌。会话编号用于明确指定要交接的页面，不是密钥或云端任务编号。

## 网页配置

点击“选择音频文件”调用系统文件窗口，Python 登记原文件位置；网页不接收音频字节，也不提供音频拖拽入口。用户无需手工填写路径。

页面有“填写”和“预览”两步。右上角可切换中文/English 及系统、浅色、深色外观；界面语言与音频语言分别设置。

1. 添加一个音频文件。
2. 选择音频语言、发言人区分和参考人数。发言人区分初始开启，多声道会提示生成单声道 FLAC 副本，原文件保留。
3. 按需启用热词和上下文。热词可直接填写或导入 Excel，工具栏提供“下载模板”。导入去除表头和完全空白行，保留错误值供修改。表格序号从 1 连续显示，删除后重排，跨页继续累计。Excel 文件字节仅在内存中读取并填表，不生成磁盘副本。热词和上下文内容仅在点击“确认并预览”时检查，错误在对应单元格或输入框中显示；编辑过程中保留原值。无法读取或表头不符的 Excel 在导入时提示文件问题。
4. 通过原生目录窗口选择 JSON 与文档保存位置，默认根目录为工作目录的 `transcriptions`。取消窗口保留原位置。
5. 点击“确认并预览”。错误留在对应输入位置；通过后进入独立预览视图，完整核对音频、选项、增强内容、认证方式及保存根目录。此时尚未产生任务编号，可点击“返回修改”。

同一热词只保留一行。所有重复行都会标红，权重相同也须由用户选择保留哪一行。上下文问题会指出长度或字符位置，并保留原文。Excel 只用于导入，后续使用网页当前数组，原文件不修改；外部修改 Excel 后需重新导入。

确认无误后，点击“复制给 Codex”，把包含会话编号的完整确认消息发送到原对话。例如：

```text
确认转写，会话编号：<页面提供的 session_id>
```

Codex 使用本次用户消息中的编号调用交接代码，确认页面仍处于有效预览后才创建任务并固定设置。仅回复“继续”时，Codex 会请用户使用复制按钮，避免处理另一份页面。预览同时说明音频及启用的增强内容将发往百炼北京地域，可能产生调用费用；这次确认覆盖该任务，无需后续二次授权。

编辑会话从打开起有效 **2 小时**，操作不会延长。交接、取消或到期后，页面显示对应结束提示，网页服务退出，标签页由用户自行关闭。到期与取消清理会话临时记录，保留原文件和已经保存的 Key；原录音直接供任务读取，转写结束前请保留文件及原路径。期限不影响已经交接的登录或转写。

同一运行服务可恢复仍在内存中的预览；填写过程没有逐次自动保存，服务结束后不能恢复未交接编辑。浏览器只持久保存当前页面来源的界面语言与主题，不保存录音、Key、热词或上下文。

| 输入 | 当前要求 |
| --- | --- |
| 本机音频 | 通过系统窗口选择原文件，支持 MP3、WAV、M4A、FLAC 等；时长不超过 12 小时 |
| BL 实际上传文件 | 不超过 1 GB，需要合并声道时按转换后文件检查 |
| 热词表格 | 最多 2,000 个词；直接填写，或导入不超过 5 MB 的两列 `.xlsx` |
| 上下文 | 最多 400 个字符，包含期望识别的具体词语 |

GB 和 MB 按十进制计量。开启发言人区分时，官方建议不超过 2 小时。完整规则见[模型依据](model.md)。引号、换行和反斜杠按原文输入，无需手工转义；命令过长时按提示缩短路径或减少词条。

## 交接与执行

Codex 按用户粘贴的会话编号执行：

```powershell
$sessionId = '替换为本次用户确认消息中的会话编号'
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir confirm --session $sessionId
```

成功回执给出 `job_id`、认证方式和保存位置。正在填写、预览未展示或已到期时，代码拒绝交接，不创建任务或上传。确认回执丢失时，以相同会话编号再次执行确认会读取同一份回执，不能产生第二个任务；见[会话交接恢复](errors.md#会话交接恢复)。

按所选认证方式准备后，执行一次：

```powershell
$jobId = '替换为交接回执中的任务编号'
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir transcribe --job $jobId
```

转写读取交接时保存的授权。Codex 告知已开始并等待同一进程完成；BL 负责临时上传、提交、轮询和原始 JSON 保存，Python 随后生成三种文档。成功后直接交付，无需另行 export；失败或结果未知时停止，不自动重传。

取消尚未交接的页面使用 `cancel --session SESSION_ID`。它结束编辑会话，不能取消已经交接的云端任务。

文件位于所选根目录的 `JOB_ID/json/transcription.json` 和 `JOB_ID/documents/transcription.{docx,xlsx,md}`。文档保留原文、时间戳和启用时的发言人编号，标题为“源文件名 录音转写”。Word、Excel 使用等线字体。

## 查询与重新导出

```powershell
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir job-status --job $jobId
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir export --job $jobId
```

`job-status` 只读本地记录；`JSON_READY` 表示 JSON 可用，三种成品全部完成需 `documents_ready=true` 且 `delivery.status=COMPLETE`。`RUNNING` 不能证明进程存活或云端实时状态。

`export` 用于用户明确要求重新生成文件：核对已保存成功记录与原 JSON，覆盖固定目录中的三种同名文档，不重新识别。请先另存人工校对的成品，并等待当前导出结束。历史成功任务使用原模型标签；新识别固定当前模型。状态和失败处理见[错误说明](errors.md)。

## 中断与临时文件

关闭标签页不会终止本机服务。正常交接、取消或到期后，服务等当前请求结束，再清理会话暂存；原录音、正式 Key、BL 凭据及结果保留。

服务被强制关闭时，清理可能未运行。下次在**同一工作目录**打开转写页，工具会回收“已经到期且原进程已结束”的旧会话，以及已结束进程留下的自有文档、状态和 Python 临时文件。仍在运行、状态无法确认、归属不完整的文件会保留；有问题时启动回执会给出警告。这不会自动恢复或重传转写。

不要为清理残留删除整个 `.asr-transcription`：其中还有凭据、环境、已交接任务与执行记录。工具不清扫系统 Temp，也不清除安装缓存或无归属的旧文件。未交接编辑仍需重新填写；已有任务用原 job_id 查询。

## 本机文件

| 内容 | 位置 |
| --- | --- |
| API Key | `WORKSPACE/.asr-transcription/.env` |
| BL 配置 | `WORKSPACE/.asr-transcription/.state/bailian/` |
| 活动会话连接信息 | `WORKSPACE/.asr-transcription/.state/sessions/SESSION_ID/connection.json` |
| 成功交接回执 | 同一会话目录的 `receipt.json` |
| 任务配置与记录 | `WORKSPACE/.asr-transcription/.state/jobs/JOB_ID/` |
| 默认输出 | `WORKSPACE/transcriptions/JOB_ID/` |

连接令牌在会话结束时移除。会话回执与任务编号用于定位这次交接；凭据、录音和结果不写入 Skill 安装目录。工作目录可能属于用户自己的仓库，其敏感文件不能假定受 MemoFlow 的 Git 忽略规则保护。
