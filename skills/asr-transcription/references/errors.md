# 状态与错误说明

先根据页面或 Codex 返回的提示定位问题。发生失败时，保留当前回执和已经生成的文件；处理完成前不要反复提交同一录音。

## 常见问题处理

| 现象 | 处理方法 |
| --- | --- |
| 安装较慢或暂时没有新输出 | 查看同一进程的stderr进度或本机安装日志。下载继续时等待；pip的120秒网络等待、npm的HTTP请求期限都不是整个安装的总时限。不要并行启动另一份安装。 |
| 安装包内运行时摘要不匹配 | 重新获取完整的 asr-transcription.zip 并按安装说明使用。保留工作目录中的已有凭据与任务，不修改锁定摘要或执行损坏的运行时归档。 |
| 基础 Python / Node.js 下载失败 | 查看 PowerShell 入口返回的官方地址和具体错误，恢复网络后重跑同一入口。只有摘要匹配的完整 ZIP 才会解压，不能跳过校验或改用全局安装掩盖问题。 |
| curl 提示 SEC_E_NO_CREDENTIALS | 已观察到 Windows 受限令牌会使系统 curl 的 TLS 初始化失败。按执行工具的权限机制重新运行相同 bootstrap 入口（Codex 使用 require_escalated）；不关闭证书校验。 |
| Python依赖下载中断或摘要不匹配 | 安装器先由pip有限恢复下载，再尝试另一来源；两个来源都失败才返回最终错误。保留日志中的下载地址、Expected与Got进一步排查，保持锁定摘要。完整文件与未完成片段分别处理，后者不能直接用于安装。 |
| 百炼 CLI（BL）下载失败 | 安装器先比较npm官方源与npmmirror。npm按锁下载并校验，已识别的下载或来源错误会切换另一个来源；每源至多一次npm ci，npm自身可能重取失败请求。缓存由npm管理，换源不保证续接未完成的文件。两个来源都失败时保留bootstrap.log并停止。 |
| npm提示权限、磁盘、锁文件或未知错误 | 这些错误不会通过换源消失，安装器直接停止。保留bootstrap.log中的error.code与具体原因，处理本机问题；不删除依赖锁、关闭校验或反复重跑安装。 |
| 安装提示目录冲突 | 让 Codex 检查提示中的安装目录及已有文件。保留凭据和用户数据，确认残留内容后再决定修复方式。 |
| 更换工作目录后环境不可用，或提示虚拟环境来自其他 Python | 旧版系统 Python 创建的 venv 或搬迁后的 venv 可能引用其他基础路径。先结束使用它的任务，仅清理当前工作目录的 .asr-transcription/.venv，再运行 bootstrap.ps1；保留 API Key、BL 配置、任务与结果，不删除整个运行目录。 |
| 转写页面没有出现 | 保留启动回执和同一serve进程，区分本机服务是否响应与浏览器是否显示，按下方“页面打开问题”处理。 |
| 页面提示录音路径无法读取 | 在音频区域重新选择文件。对话附件须有用户或宿主明确提供的本机绝对路径；确认后在转写完成前保持文件可访问。 |
| 提示运行目录或保存位置位于 Skill 内 | 选择 Skill 安装目录之外的工作目录和保存位置；这些位置用于存放环境、任务、处理文件及结果，原录音从用户选择的位置读取。 |
| 登录完成后仍提示配置不足 | 让 Codex 查看本地登录状态，确认模型调用凭据是否存在。页面登录成功不等于模型权限已验证。 |
| 文件或增强内容检查失败 | 点击“确认并预览”后，热词问题在对应行、列标红，上下文增强的输入问题在输入框提示。修正后再次点击该按钮检查，原文会保留；无法解析的 Excel 会在导入时提示文件问题。 |
| 热词重复 | 按原文相同的词条分组，所有相关行都会提示，包括首行和权重错误的行。确认需要的词条及权重后只保留一行，不是把各行权重统一后继续提交。 |
| 预览时发现设置填错 | 点击“返回修改”，后端允许退出预览后恢复填写；交接后设置固定，需要新识别时重新配置。 |
| 交接提示Windows命令过长 | 当前预览仍保留。回页面“返回修改”，减少热词或缩短保存路径，再预览并发送确认消息。此时尚未写入任务配置或回执，未占用执行、未读取凭据、未启动BL。 |
| 选择文件夹后没有出现窗口 | 检查任务栏和被遮挡的窗口。仍无窗口时点击网页的“取消等待”，让 Codex 检查网页服务所在的桌面环境。 |
| 交接响应中断 | 用相同会话编号读取原交接回执，详见下方“会话交接恢复”。不要另建识别任务代替结果核对。 |
| 转写失败、超时或等待中断 | 让 Codex 说明停止阶段和已知结果。结果未知时不要重新提交；本机停止不代表云端已取消。 |
| 已保存设置的模型与当前模型不一致 | 在当前网页重新检查并保存新配置，再按授权范围执行。旧配置、摘要和记录保持原样；已有成功JSON仍可用export本地重导，文档保留原任务模型标签。 |
| 仅部分文档生成失败 | 先使用已保存的文件。任务成功记录和原 JSON 完整时，可明确要求 Codex 重新导出，覆盖该任务的同名文档；手工修改的成品先另存。 |
| 启动或关闭提示清理未完成 | 读取 cleanup.warnings 或 cleanup_warning，检查对应会话或任务的访问权限与归属。无法确认进程状态时保留文件，不自行终止进程或删除整个运行目录；已交接任务照常按原编号处理。 |
| 提示执行记录无法保存 | 保留这次回执和文件，检查提示中的权限、空间或中断原因。后续状态查询可能是旧记录，不应据此再次识别。 |
| 错误原因未收录 | 保留脱敏的错误码和请求编号，参阅百炼官方错误说明或向服务方查询；不能仅凭状态码推断余额或权限问题。 |

提交问题反馈时，提供使用步骤、环境版本和脱敏错误信息，去除 API Key、登录链接、音频正文及私人路径。

## 页面打开问题

这里处理127.0.0.1的本机配置页。阿里云登录授权页来自单独的BL login命令，应结合该命令的输出排查；两种页面的打开状态分别确认。

以下检查只在打开报错或用户反馈页面未出现时执行；正常打开后直接让用户操作。先读取同一`serve`进程的`event="listening"`回执，取得实际URL和进程信息。没有启动回执时先核对命令是否执行、退出或仍在运行，不猜端口、不把doctor通过当成页面已经打开。

- 用回执URL检查本机首页。无响应时检查该服务的实际输出和存活状态；不要直接创建另一个会话掩盖原问题。
- 首页可响应时，通过宿主打开链接能力重新打开同一完整URL。返回queued表示等待在对应对话中显示。请用户描述实际结果；此排查不要求computer-use、桌面扫描或浏览器自动化。
- 普通serve的`browser_request=failed`说明系统打开请求失败；`requested`表示请求被接受。`--no-browser`对应`skipped`，调用方工具负责打开。
- 对话中的录音可以直接带入页面；浏览器音频选择区域也可添加或更换文件，无需在聊天中手工填写路径。

启动 URL 不含令牌；会话连接令牌由工具从私有运行目录读取，不写入聊天或日志。

## BL登录页没有打开

先区分BL登录进程与本机转写页面。登录必须从第一次调用就使用正常桌面执行权限，Codex支持时传`sandbox_permissions=require_escalated`。程序检测到Windows受限令牌会在启动BL前返回提示；按执行工具权限机制运行同一login命令即可，不自行提权或关闭Chrome安全设置。

本版在BL开页之前转交完整URL，只请求系统浏览器打开一次。若仍报错，保留具体错误与本次进程结果并停止，核对实际执行权限及是否使用最新Skill资源；不能把浏览器失败归因为账号或API Key无效，也不以另开页面或自动重试掩盖问题。

## 鉴权失败与重新配置

先读取BL返回的`code`、`http_status`和说明，区分凭据、模型权限、地域、业务空间及额度问题。`configured=true`只说明本机有凭据；不能仅凭401/403就断言API Key过期，也不要对所有错误都要求重新登录。

| 已确认的问题 | 处理方式 |
| --- | --- |
| 指定API Key缺失、填写错误或已失效 | 打开新的配置页，选择“使用指定 API Key”，让用户填写有效的北京地域API Key并点击“保存 API Key”。提示用户看到保存成功后回Codex发送“完成”或“继续”；据此调用 cancel --session SESSION_ID 结束编辑会话。无需录音、交接任务、login或转写。 |
| 控制台模式缺少模型API Key | 运行现有login入口，由BL获取并保存模型凭据。 |
| 控制台令牌失效 | 需要使用控制台能力时运行login；ASR使用的是模型API Key，不能因控制台令牌变化就认定模型API Key也无效。 |
| 控制台模式中已保存的模型API Key被明确拒绝 | 按用户的修复意图，用下方BL原生命令清空本工作目录default Profile的api_key，再运行现有login入口；也可由用户选择改用网页指定API Key。 |
| 模型访问权限、地域、业务空间或额度问题 | 按官方错误说明处理对应配置或权限；重新登录或换API Key不一定能解决。 |

BL 2.1.0发现已保存的模型API Key时，不会仅因重新控制台登录就请求另一份API Key。这一分支使用BL公开配置命令，不手工改写BL配置文件，也不清除控制台等其他凭据。以下沿用[运行准备](usage.md#运行准备)中的变量，仅在已确认需要更换控制台模式的模型API Key时执行：

```powershell
$blEntry = Join-Path $workspaceDir '.asr-transcription/.tools/bailian/node_modules/bailian-cli/dist/bailian.mjs'
$nodePath = Join-Path $workspaceDir '.asr-transcription/.tools/node/node.exe'
$previousBlConfigDir = $env:BAILIAN_CONFIG_DIR
try {
    $env:BAILIAN_CONFIG_DIR = Join-Path $workspaceDir '.asr-transcription/.state/bailian'
    & $nodePath $blEntry config set --config default --key api_key '--value=' --quiet
    if ($LASTEXITCODE -ne 0) { throw 'BL未完成本机Key配置更新。' }
} finally {
    $env:BAILIAN_CONFIG_DIR = $previousBlConfigDir
}
& $pythonPath -X utf8 $scriptPath --workspace $workspaceDir login
```

配置修复不改变已失败任务的执行记录，也不触发重传。若用户明确要求再次转写，说明原任务的已知`cloud_outcome`，按新录音流程重新确认设置并创建新任务；不删除旧占用或自动以新编号重试。命令依据见[固定BL登录与配置行为](model.md#后续调用与凭据修复)。

## 会话交接恢复

确认响应丢失时，用**本次用户确认消息中的相同编辑会话编号 `session_id`**再次运行 `confirm --session SESSION_ID`。入口先读取该会话的持久回执；成功交接过的会话返回原转写任务编号 `job_id`，不依赖网页服务仍在运行，也不创建另一任务。

- 仍在填写或预览未就绪：让用户回原页面完成“确认并预览”，核对后重新发送复制消息。不得从曾经通过校验推断当前预览已展示。
- Windows 命令过长：当前预览保留，返回修改后重新预览；同一编辑会话仍可交接，尚无已发布任务或执行占用。
- 已到期或已取消：本次编辑已结束，没有可执行任务。用户需要继续时重新打开页面；原文件和已保存的凭据保留。
- 已交接：已知原执行进程仍在运行时，继续等待该进程。执行情况未知时才用 `job-status --job JOB_ID` 读取记录；尚未执行则按认证方式继续同一任务，遵守一次执行约束。
- 连接文件存在但服务不可达，且没有结束回执：报告无法确认会话结果，保留记录并排查，不猜测“最新任务”或自动提交新的识别。

只有活动服务中已通过检查的预览可以恢复。未提交编辑没有逐次持久保存；关闭标签页不等于服务结束，两小时到期或显式取消负责清理会话临时记录，原文件保留。已交接任务的配置固定，不会因“返回修改”产生替代编号。

用户只回复“继续”而没有带会话编号时，请其使用预览页的“复制给 Codex”。编号用于明确用户选择，连接令牌另由工具私下读取；不要把编号当作密钥，也不要从启动日志替用户选择会话。

## 状态字段参考

本节供排障和 Codex 解释回执使用。上游CLI/API错误映射位于[错误字典](../scripts/asr_runtime/error_catalog.json)，记录固定版本、核验日期和官方来源；本地错误由项目代码定义。

### 官方云端状态

依据：[Filetrans HTTP API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api)、[模型系列状态示例](https://help.aliyun.com/zh/model-studio/funauidio-asr-recorded-speech-recognition-python-sdk)、[通用异步任务管理](https://help.aliyun.com/zh/model-studio/manage-asynchronous-tasks)。

| 状态 | 官方含义 | 当前实现的实际可见性 |
| --- | --- | --- |
| PENDING | 排队中 | BL正常轮询，Python不接收逐次状态事件 |
| RUNNING | 正在执行 | 同上，不能等同本地RUNNING的细分阶段 |
| SUCCEEDED | 顶层任务成功 | BL继续处理子项/下载；不代表三种成品已完成 |
| FAILED | 云端任务失败 | BL停止，Python解释暴露的错误，不重提 |
| CANCELED / UNKNOWN | 通用任务取消/不存在或未知 | 不承诺固定模型会返回；BL2.1.0识别路径未将它们作为完成条件，可能轮询到超时 |

本项目没有公网回调服务、第二个轮询器或已验收的云端取消/恢复查询入口。终止本地等待不等于取消云端。未知状态不能解释成成功，但也不能声称Python能即时观察BL未暴露的状态。

### CLI与API错误

- 官方退出码见[CLI定义](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/core/src/errors/codes.ts)，API解释见[百炼错误码](https://www.alibabacloud.com/help/zh/model-studio/error-code)，具体映射在error_catalog.json。
- CLI退出码、HTTP状态和API code是独立字段，按原回执分别解释。
- Python读取BL结构化stderr的error.api_code、message、request_id、http_status，将api_code映射为本地回执的code，脱敏后给用户；cli_exit_code取自进程退出码。原始stderr、cause、hint和完整响应不进入回执。
- 未知code明确说明字典未收录，不猜余额、权限、音频损坏或套用其它模型含义。
- FILE_DOWNLOAD_FAILED等只使用固定模型系列明确示例；不能把Paraformer专有FILE_*说明搬过来。[HTTP示例](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api)
- 官方可能建议重试；本项目只解释，不自动执行重试。

### 本地网页HTTP

来自web.py，不是阿里云状态码：200本机操作完成；400请求格式错误；403Host/Origin/会话不符；404接口/资源不存在；413本机JSON请求超过512KiB；422输入或文件操作未完成。

编辑与预览请求失败时，按对应字段或连接错误处理；交接响应不明时通过同一会话回执恢复。服务端未捕获异常可能使请求断开，不承诺总能返回统一错误 JSON。

### 编辑会话状态（session_id）

| state / phase | 含义 |
| --- | --- |
| editing | 正在填写，或尚未登记预览展示；不能交接 |
| preview | 当前校验版本已在页面展示，可按用户明确编号交接 |
| handed_off | 授权配置已发布，交接回执对应唯一任务 |
| expired | 从打开起满两小时，尚未交接的会话结束 |
| cancelled | 编辑会话已取消或正常结束；已交接任务不因此取消 |

这些状态由本机 Session 定义，与 BL 的登录或云端任务状态无关。结束事件经单向连接发送给页面；交接回执在服务结束后仍可读取。配置发布失败的候选回执不视为成功，工具仅在对应 config.json 已发布时返回任务。

### 转写任务记录（job_id）

| status | 含义 |
| --- | --- |
| CONFIGURED | 会话已交接，授权配置固定，还没有execution占用 |
| PREPARING | 已占用执行，最近处于本地准备；不保证进程仍活着 |
| RUNNING | 最近进入BL进程阶段，不能区分上传/识别/下载 |
| JSON_READY | JSON通过本地结构检查，文档另看delivery |
| STOPPED | 本地准备、BL执行或JSON检查停止，失败不重试 |
| OUTCOME_UNKNOWN | 占用已存在但执行记录不可读，不能当作未执行 |

cloud_outcome取not_started/unknown/result_received。当前BL完整模式未提供可靠的云端任务编号，执行记录不生成task_id字段，也不用本地job_id冒充云端ID。执行目录永久保留；本地准备失败也不自动删除占用重跑。

| 本地code | 含义 |
| --- | --- |
| LOCAL_PROCESS_START_FAILED | BL进程未启动 |
| LOCAL_WAIT_INTERRUPTED | 本机等待中断，不能推断云端未受理或已取消 |
| LOCAL_EXECUTION_STOPPED | 准备或结果检查未完成，看具体中文说明 |
| LOCAL_RECORD_SAVE_FAILED | 本地执行记录写入失败或被中断；保留当次回执，磁盘记录可能滞后 |

LOCAL_EXECUTION_STOPPED保留error.phase和error_type，BL错误沿用已有code并补充phase。已知输入错误解释具体原因，文件错误提示存在性/权限/空间/占用，未知程序异常仅公开类型，不输出可能含正文的异常原文。

| phase | 定位范围 |
| --- | --- |
| prepare_input | 本地环境、音频摘要、运行凭据、参数及必要声道转换 |
| run_bl | BL启动与等待；更细的上传/识别/下载状态仍由BL内部处理 |
| read_result | 读取、解析并检查原始JSON |
| save_status | 写执行状态；record_error.attempted_status说明哪次状态未保存 |

执行记录写入失败或中断放在独立record_error中，不替换原始执行事实，也不自动重写。PREPARING/RUNNING写入失败时，本次回执明确STOPPED/not_started；JSON_READY写入失败时仍返回JSON_READY/result_received、结果摘要和目标路径，documents_ready=false且不进入导出。此时job-status可能仍读到旧状态；export仍要求已保存的JSON_READY及摘要，没有补签、恢复记录或重新识别入口。

json_path是已确定的JSON目标位置，不单独证明文件存在或有效；JSON_READY才表示本次已成功读取并通过结构检查。RUNNING在启动BL前保守落盘，因此后续仅凭该磁盘记录不能证明是否已启动。命令参数、配置等入口错误仍可能直接返回failed/message。上述本地code不是官方错误码。

### 文档交付记录

| delivery.status | 含义 |
| --- | --- |
| EXPORTING | 最近记录在导出，不保证进程仍活着 |
| COMPLETE | 三种成品已保存，Excel/Word回读核验通过，Markdown编码写入完成 |
| PARTIAL | 部分格式成功，其余失败；保留成功文件 |
| FAILED | 全部失败或无法创建输出目录，原JSON保留 |
| OUTCOME_UNKNOWN | 导出中断或记录不可读/写，不声称成品齐备 |

files内分别记录本次各格式的READY/FAILED、路径/大小或错误类型。单格式生成失败时已有目标文件保留，文件仍存在不代表本次导出成功。已知格式错误有本地说明，文件系统错误提示权限/空间/占用；未知程序异常只报告类型，不假装一定是磁盘问题。

导出失败不把JSON_READY改成云端失败。显式export核对执行记录中的结果JSON摘要，在该任务的documents文件夹生成三格式并覆盖同名成品，不重新识别；记录缺少摘要或结果发生变化时停止，不补摘要。每个任务的导出状态保存在`WORKSPACE/.asr-transcription/.state/jobs/<job_id>/delivery/status.json`，job-status读取该记录，不重新验证成品存在或摘要。
