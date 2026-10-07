# 官方依据与固定能力

API资料核验基线：2026-10-04，当前模型为Qwen-Audio-3.1-ASR-Flash-Filetrans。百炼 CLI（BL）固定2.1.0，对照源码提交`8bbbbc722d70fb200641ef22b6f6d033aeae9f74`及本机发布包；不把未核实的新版本能力加入当前接口。

精度增强[A04]与说话人区分（官方术语：说话人分离，speaker diarization）[A03]的参数依据见下表。2026-10-07 再次核对模型介绍[A01]及中英文模型总览[A02]：Qwen 3.1 支持多地区中文方言、热词和上下文增强。产品输入方式和媒体处理以项目实现为准。

## 来源

| 编号 | 来源 | 用途 |
| --- | --- | --- |
| A01 | [模型详情](https://help.aliyun.com/zh/model-studio/qwen-audio-3-1-asr-flash-filetrans) | 固定模型与地域 |
| A02 | [模型与音频规格](https://help.aliyun.com/zh/model-studio/asr-model) / [English](https://help.aliyun.com/en/model-studio/asr-model/) | 版本对应的语言与方言、容器、时长、采样率、模型文件大小 |
| A03 | [Filetrans HTTP API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api) | 参数、句子JSON、子任务结果 |
| A04 | [提高识别准确率](https://help.aliyun.com/zh/model-studio/improve-asr-accuracy) | 即时热词、超级词、上下文增强 |
| A05 | [定制热词Python SDK参考](https://docs.bailian.console.aliyun.com/zh/model-studio/vocabulary-python-sdk) | 区分词条text/weight与预编译词表prefix的约束 |
| A06 | [临时文件URL](https://help.aliyun.com/zh/model-studio/get-temporary-file-url/) | 临时OSS限制及有效期 |
| A07 | [异步任务管理](https://help.aliyun.com/zh/model-studio/manage-asynchronous-tasks) | 通用任务状态 |
| A08 | [百炼错误码](https://www.alibabacloud.com/help/zh/model-studio/error-code) | API错误解释 |
| A09 | [模型系列SDK状态示例](https://help.aliyun.com/zh/model-studio/funauidio-asr-recorded-speech-recognition-python-sdk) | 状态/错误依据，不采用SDK实现 |
| A10 | [CLI安装与鉴权](https://docs.bailian.console.aliyun.com/zh/model-studio/cli/installation) | 控制台授权与本地状态 |
| A11 | [API Key获取与时效](https://help.aliyun.com/zh/model-studio/get-api-key) | 普通Key、临时Key及失效条件 |
| A13 | [CLI语音识别](https://help.aliyun.com/zh/model-studio/cli/speech) | 公开recognize与out参数 |
| W01 | [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw) | Windows命令行长度 |
| W02 | [cmd](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/cmd)、[os.startfile](https://docs.python.org/3.12/library/os.html#os.startfile) | BL系统浏览器调用与完整链接转交 |
| M01 | [PyAV18.1.0安装](https://github.com/PyAV-Org/PyAV/blob/v18.1.0/docs/overview/installation.rst) | wheel包含FFmpeg库 |
| M02 | [AudioResampler](https://github.com/PyAV-Org/PyAV/blob/v18.1.0/av/audio/resampler.py) | 声道变换、flush |
| C01 | [python-dotenv](https://bbc2.github.io/python-dotenv/) | 只解析指定.env且不展开变量 |
| O01 | [Codex构建Skill](https://learn.chatgpt.com/docs/build-skills) | SKILL.md元信息、脚本与参考资料的技能结构 |

## 模型和本地阈值

Qwen 3.1 的官方语言说明列出上海、南昌、宁波、客家、杭州、温州、湖南、福建、粤语和苏州方言[A01/A02]。项目介绍采用该版本的能力说明；识别表现还取决于录音质量与内容，使用热词及上下文补充相关术语后仍需用户校对。

| 项目 | 当前依据与处理 |
| --- | --- |
| 模型/地域 | qwen-audio-3.1-asr-flash-filetrans，首版北京[A01] |
| 输入 | 单文件；模型<=2GB、<=12小时，任意采样率[A02] |
| 容器 | aac/amr/avi/flac/flv/m4a/mkv/mov/mp3/mp4/mpeg/ogg/opus/wav/webm/wma/wmv；只处理音频，不提供视频编辑[A02] |
| 临时上传 | 官方1GB，项目采用1,000,000,000字节阈值；限制实际上传的原文件或声道合并文件，超限不压缩/切片重试[A06] |
| 临时资源 | 有效48小时，与主账号/模型绑定；没有本流程可主动删除临时音频的公开入口，不能承诺立即清除[A06] |
| 说话人区分 | 模型要求单声道，建议<=2小时；产品按用户要求默认开启，人数2–100为参考值，不保证真实人数[A03] |
| 语言 | API可多语种，但当前BL --language只收单值；产品自动或一种语言[A03/A13] |
| 热词 | 词→权重映射，<=2000条；权重1–5或50；超级词<=50；含非ASCII总长<=15字符，纯ASCII按空格<=7段[A04] |
| 上下文增强 | 单段文本<=400个Unicode字符，应包含要识别的相关原词，不作为模型行为指令[A04] |
| 组合增强 | input.context和parameters.vocabulary可同时存在；BL同一请求已核对[A03] |
| 音轨 | channel_id指音轨，默认[0]；不同于PyAV音轨内的channels。当前不开放选择 |
| 未开放参数 | 固定BL2.1的help及commands/core/runtime发布源码均无keep_dialect、special_word_filter入口；当前沿用模型缺省行为，不绕过CLI接入这些API参数 |

Excel的5MB、20MiB解压、200个内部文件、10001行和两列是本地解析资源限制，集中在utils/hotwords.py，不冒称模型限额。模型输入规则集中在application/rules.py，界面从服务端取得显示限制。

2026-10-04复核[A04]：热词和上下文规则保持上述来源。导入和手填的热词统一在“确认并预览”时校验；权重文本只接受明确的`1`–`5`或`50`，Excel真实公式与普通文本分别处理。官方说明超过400字符的上下文会从末尾截断，本项目在本机提示用户精简后重查，避免静默丢失内容；不使用关键词规则判断上下文与录音的语义相关性。

同日核对[A05]原页面：`text`要求实际词语及上述长度，`weight`常用值为4；未列出禁止英文缩写的规则。仅小写字母和数字、长度不超过10的限制针对预编译词表`prefix`，不是热词内容。该SDK页面的通用权重表为1–5；本项目使用Qwen 3.1即时热词，权重50的支持以[A03/A04]中明确针对该模型的说明为准。

重复词由本项目在表格阶段拒绝：按原文精确比较，全部重复行（包括首次出现、权重相同或权重非法的行）都提示保留一行；不自动合并、统一权重、改写大小写或去除空白。这是本工具的输入约束，不把它宣称为已验证的云端错误行为。

## BL复用边界

官方仓库：[modelstudioai/cli](https://github.com/modelstudioai/cli)。npm版本与完整性摘要以Skill中的`scripts/bailian/package-lock.json`为依赖来源；安装时由npm ci按锁文件获取依赖，不维护第二份依赖版本表。

| 能力 | 固定源码依据 | 本项目处理 |
| --- | --- | --- |
| 配置目录 | [paths.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/core/src/config/paths.ts) | BAILIAN_CONFIG_DIR指向WORKSPACE/.asr-transcription/.state/bailian |
| 环境Key | [resolver.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/core/src/auth/resolver.ts) | 用DASHSCOPE_API_KEY子进程环境，不把Key放argv |
| 官方登录 | [login-console.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/commands/src/commands/auth/login-console.ts)、[status.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/commands/src/commands/auth/status.ts) | BL负责回调与保存；登录后检查模型Key存在，不再调用模型验证 |
| 完整ASR | [recognize.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/commands/src/commands/speech/recognize.ts) | 本地上传、提交、轮询、下载、out保存均由BL完成 |
| 临时上传 | [upload.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/core/src/files/upload.ts) | 国内策略15秒、上传120秒；整文件读入内存，接近上限的大文件未全面验收 |
| 失败/轮询 | [http.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/core/src/client/http.ts)、[polling.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/runtime/src/utils/polling.ts) | 当前ASR请求失败上抛，正常未完成才轮询；不据此声称整个CLI所有命令都没有重试 |

使用recognize完整模式，不传--async。项目传timeout=3600、poll-interval=5；Python进程上限3900秒。这是项目等待策略，不是官方处理承诺。最后JSON下载使用原生fetch，没有单独下载超时，保留外层进程上限。

2026-10-04的真实BL本机合约确认：`--model qwen-audio-3.1-asr-flash-filetrans`被原样提交，热词与上下文可一起进入请求；全部可选设置关闭时仍有`parameters={"channel_id":[0]}`，符合[A03]对3.1必须携带parameters对象的要求。BL2.1帮助中的增强描述仍提到3.0，云端3.1能力以[A01/A03/A04]为依据，本机合约只验证CLI实际请求，不作为云端识别成功证明。

BL可能跳过失败子项、写空数组，或在没有子结果时不写文件；因此退出0仍需检查实际JSON。固定单文件成功结果已实测为对象，包含file_url/properties/transcripts；句子含begin_time/end_time/text及可空speaker_id，时间单位毫秒。Python不猜字段别名，也不声称获得了全部云端子任务信封。

完整模式不稳定暴露task_id，当前没有独立恢复入口。BL会在真实本地文件dry-run判断前执行上传，因此不能把本地文件dry-run当作无上传的预览。

### 增强文本与Windows参数

锁定的BL 2.1.0发布包中，bailian-cli-runtime/dist/index.mjs的parsePath先识别独立的--help/--version，parseFlags将分离参数中以--开头的值视为缺少参数值。解析器也支持以首个等号分隔选项和值，因此本项目将上下文构造成单个`--context=<原文>`参数；其中后续等号、引号、换行和反斜杠作为文本保留。

热词由`json.dumps`编码为一个JSON参数，再由BL的parseInstantVocabulary通过JSON.parse还原。bailian-cli-core/dist/index.mjs中的buildAsrContextMessages将上下文直接包装为input_text。本项目使用参数数组、Node入口和shell=False；Windows参数引用交给Python标准库处理。[Python参数传递规则](https://docs.python.org/3.12/library/subprocess.html#converting-an-argument-sequence-to-a-string-on-windows)、[JSON序列化](https://docs.python.org/3.12/library/json.html#json.dumps)

完整命令受Windows的32767个UTF-16单元限制（含末尾NUL）。交接时生成实际任务编号和路径后，复用正式参数映射检查完整Node命令；超限在配置与回执写入前返回，保留当前预览供用户返回修改。此检查不读取凭据或启动BL；执行时仍核对当次完整命令。[CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw)

固定BL 2.1.0的即时热词参数接收JSON文本，未提供读取词典文件的公开参数。因此模型允许的2000条词语在Windows上仍可能超过整条命令长度；超限时需要减少词条或缩短路径，不把输入另存文件并假定CLI能够读取。参数入口见[recognize.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/commands/src/commands/speech/recognize.ts)。

### Windows登录转交

2026-10-03再次核对固定源码及本机2.1.0发布包：[local-server.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/commands/src/commands/shared/local-server.ts)在Windows调用cmd/start传入URL，&needapikey参数存在被拆开的引用问题。[login-console.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/commands/src/commands/auth/login-console.ts)在打开失败时输出完整备用链接，保持原回调服务至授权完成或15分钟超时；该版本未提供已核实的auth login禁用浏览器选项。

本项目仅在Windows控制台登录时使用Node预加载适配：拦下上述已知的`cmd/start`登录开页调用，使BL进入其完整URL输出分支；Python验证URL后通过`os.startfile`打开一次。BL包文件保持原样，授权state、回调、凭据保存和原生15分钟会话计时均由BL负责；Python不再叠加登录总等待上限。开发源为`scripts/console-browser.cts`，发行产物为Skill内`scripts/bailian/console-browser.cjs`。适配仅覆盖该固定版本已核实的浏览器调用，不扩展为通用Node拦截器。

本项目首次调用login即要求正常Windows桌面执行权限；Windows进程令牌对照读取得到受限执行为true、正常桌面为false，程序在启动BL前用[IsTokenRestricted](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-istokenrestricted)拒绝受限令牌。此API检查限制SID列表，不是对所有桌面可用性或浏览器内部状态的检测。

### 后续调用与凭据修复

2026-10-03核对固定2.1.0源码及本机CLI：模型凭据解析器选择显式参数、环境变量或配置中的api_key；控制台access_token用于另一类控制台请求。`auth status`读取本机authStore描述，不能证明Key当前可被云端接受。[resolver.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/core/src/auth/resolver.ts)、[status.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/commands/src/commands/auth/status.ts)

控制台登录仅在本机未保存模型Key时设置`needApiKey=true`。[login.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/commands/src/commands/auth/login.ts)。明确无效的旧Key可通过`bl config set --config default --key api_key --value= --quiet`清空，然后复用官方登录。`config set`由BL更新指定字段，本机隔离合约已确认空Key不再出现在auth status中且console凭据保留；该命令不等于在线验证。[set.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/commands/src/commands/config/set.ts)

普通Key无固定失效时间，临时Key最长1800秒；具体失效条件以[A11]为准。Python只读写用户工作目录和解释BL错误，不实现Key刷新或独立鉴权服务。

### 更新与安装副作用

BL中间件会检查版本并可能写update-state.json；quiet阻止后续自动升级/提示，不完全禁止版本查询。DO_NOT_TRACK=1关闭遥测。依据：[middleware.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/runtime/src/middleware.ts)、[update-checker.ts](https://github.com/modelstudioai/cli/blob/8bbbbc722d70fb200641ef22b6f6d033aeae9f74/packages/runtime/src/utils/update-checker.ts)。

首次安装由 `scripts/bootstrap.ps1` 准备工作目录内的基础运行时，固定来源与 SHA-256 见 `scripts/runtimes.json`。完整包的 `assets/runtimes` 直接附原始官方 ZIP；轻量包由官方来源下载，相同摘要适用于两种来源。Python 使用官方 [Windows 运行时索引](https://www.python.org/ftp/python/index-windows.json)中的 `python-3.12.10-amd64.zip` 完整包。官方允许直接解压安装管理器提供的 ZIP 并从目标目录运行；嵌入式包不含 Tcl/Tk 和 pip，不能满足本项目的文件窗口和依赖安装。[完整运行时解压](https://docs.python.org/3/using/windows.html#offline-installs)、[嵌入式包范围](https://docs.python.org/3/using/windows.html#the-embeddable-package)

运行时下载复用 Windows 自带 curl 的 HTTPS、连接重试与续接，摘要由 PowerShell `Get-FileHash` 校验。系统 curl 使用 Schannel；受限令牌下已观察到 `SEC_E_NO_CREDENTIALS`，因此安装入口从首次调用就遵循执行工具的正常网络权限机制。[Windows curl 官方说明](https://learn.microsoft.com/en-us/windows/curl/)

Node 使用 [24.21.0 Windows x64 ZIP](https://nodejs.org/dist/v24.21.0/)，随包 npm 为 11.19.0，版本对应关系与摘要来自 [Node 发布索引](https://nodejs.org/dist/index.json)和 [SHASUMS256](https://nodejs.org/dist/v24.21.0/SHASUMS256.txt)。两套运行时均从工作目录绝对路径调用，不依赖系统 Python/Node，也不修改全局 PATH 或注册表。已创建的 Python venv 保留基础解释器路径，不保证搬迁后可用。[venv 可移植性说明](https://docs.python.org/3.12/library/venv.html#how-venvs-work)

安装使用官方[npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci/)和[pip require-hashes](https://pip.pypa.io/en/stable/topics/secure-installs/)；BL与Python依赖分别由`package-lock.json`、`requirements.txt`锁定。Python包摘要来自官方PyPI，对应Windows x64 CPython3.12或py3-none-any包：[PyAV](https://pypi.org/pypi/av/18.1.0/json)、[dotenv](https://pypi.org/pypi/python-dotenv/1.2.3/json)、[python-docx](https://pypi.org/pypi/python-docx/1.2.0/json)、[lxml](https://pypi.org/pypi/lxml/6.1.3/json)、[typing-extensions](https://pypi.org/pypi/typing-extensions/4.16.0/json)。安装前比较官方PyPI和[阿里云镜像](https://developer.aliyun.com/mirror/pypi/)的文件前缀吞吐，再分别使用一个`--index-url`下载；`--extra-index-url`没有来源优先级，不能作为按顺序的备用源。[pip来源选择说明](https://pip.pypa.io/en/stable/cli/pip_install/#finding-packages)

安装工具固定为[pip 26.2.1](https://pypi.org/pypi/pip/26.2.1/json)，wheel路径和SHA-256维护在`utils/installation.py`。从同一wheel采样至多256KiB、约5秒；仅用于来源排序，不落盘或参与安装。正式下载使用`--retries 2 --resume-retries 5 --timeout 120`，其中timeout是socket等待超时。安装进程没有总时限。pip 25.2默认启用续传，26.2进一步修正部分断流与Range处理；支持206时续接，不支持时重新下载，完整文件仍须通过摘要检查。[参数定义](https://pip.pypa.io/en/stable/cli/pip/)、[版本记录](https://pip.pypa.io/en/stable/news/#v26-2)、[固定版本下载器](https://github.com/pypa/pip/blob/26.2.1/src/pip/_internal/network/download.py)

`pip download`先保存完整wheel，失败才换第二个来源；`pip install --no-index --find-links`只使用本机文件，本机安装错误不再次换源。跨来源或跨进程不保留未完成下载的断点；已有完整wheel可复用。这些策略仅用于依赖准备，云端转写仍不自动重试。Skill没有随包wheel。PyAV许可见[官方LICENSE](https://github.com/PyAV-Org/PyAV/blob/v18.1.0/LICENSE.txt)；项目自身LICENSE不替代第三方许可。

BL 首次安装复用同一前缀采样方法，并行比较 `registry.npmjs.org` 与 [npmmirror](https://npmmirror.com/) 上固定版本的 `bailian-cli-2.1.0.tgz`：最多 256 KiB、约 5 秒，仅排序，不保存采样包。正式安装由 npm 完成；当前命令指定 `registry`，npm 默认的 `replace-registry-host=npmjs` 将原锁中的官方 tarball 地址切换到所选来源，版本与 integrity 保持原值，不改全局配置。该公开配置见 [npm 11](https://docs.npmjs.com/cli/v11/using-npm/config/#replace-registry-host) 与 [npm 9](https://docs.npmjs.com/cli/v9/using-npm/config/#replace-registry-host)。

两类来源的 5 秒采样窗口均从响应就绪后开始，评分包含此前的连接与响应头等待；单次 socket 等待上限为 5 秒，完整测速总耗时可能更长。采样结果仅代表该时刻的一段请求，不能保证 npm/pip 的完整安装速度。

每个来源至多运行一次 `npm ci` 进程，保留 `ignore-scripts`、关闭 audit/fund、隔离用户配置，设置 `fetch-retries=2`。stdout 的临时 JSON 用于读取 `error.code`，stderr 实时保存为安装日志。仅已识别的下载或来源错误（如连接中断、404/5xx、下载校验失败）可换源；权限、磁盘、锁冲突、结果无法解析或未知错误立即停止，不通过匹配日志文字猜测。第二来源的 `npm ci` 会重建本次安装目录中的 `node_modules`，而启动前已存在的冲突安装仍保留并报错。[npm ci 行为](https://docs.npmjs.com/cli/v11/commands/npm-ci/)

结构化错误入口为固定 npm 的 [jsonError.code 输出](https://github.com/npm/cli/blob/v11.19.0/lib/utils/output-error.js)。来源切换按返回码区分下载错误与本机失败；合约检查使用合成包和 127.0.0.1，已执行结果见仓库验收记录。

两次安装通过 `prefer-offline` 复用工作目录的 npm 缓存，缓存内容由 npm 校验；不自行操作其内部格式，也不把缓存复用描述成文件断点续传。npm 在单次进程内仍可能发起多次下载请求。来源均不可用时保留日志并停止，下载恢复不适用于云端识别。[npm 缓存与完整性](https://docs.npmjs.com/cli/v11/commands/npm-cache/)

## 本机进程与临时文件

`utils/environment.py::process_is_running` 使用 [OpenProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess) 获取进程句柄，再以 [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject) 的零毫秒等待读取状态。等待要求 [SYNCHRONIZE 权限](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights)。项目仅查询并关闭句柄；无法确认时保留文件，PID 被其他活动进程复用时也保留。

`application/recovery.py` 在下次 serve 前根据会话截止时间、PID 和已发布配置回收自有残留。正常退出先等待请求线程，再清理会话目录。具体保留范围是项目文件协议，不是 BL 的云端资源删除能力；已上传临时 OSS 仍遵循 A06。

serve、transcribe、export 用 Python 标准库 [TemporaryDirectory](https://docs.python.org/3.12/library/tempfile.html#tempfile.TemporaryDirectory) 管理工作目录内的进程临时文件。Key 仍通过 python-dotenv 修改，在会话目录暂存后替换正式 .env；不新增凭据解析器。

## 本机窗口与成品

- [tkinter.askdirectory](https://docs.python.org/3.12/library/dialog.html#tkinter.filedialog.askdirectory)：选择现有目录。当前无人工总时限，取消与进程回收由项目处理；显示窗口需要正常交互桌面。
- [python-docx文本/分页](https://python-docx.readthedocs.io/en/latest/user/text.html)：段落、keep_with_next和widow_control；不代表无需实际页面检查。
- [Word复杂文字字号](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.fontsizecomplexscript?view=openxml-3.0.1)：`w:szCs`以半磅设置复杂文字的字号，缺省时沿样式层级继承。项目同时设置普通文字与复杂文字的字号，标题20磅，其余正文、元信息、时间标签及页码10磅。
- [openpyxl样式](https://openpyxl.readthedocs.io/en/stable/styles.html)及[Excel规格](https://support.microsoft.com/en-us/excel/excel-specifications-and-limits)：单元格32767字符、工作表1048576行、行高409。项目正文自动换行，按内容估算展示行高并封顶409，单元格保留长段全文；存储超限不截断。

使用步骤见[usage.md](usage.md)，任务状态和错误解释见[errors.md](errors.md)。
