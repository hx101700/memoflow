# 百炼 CLI 2.5.1 适配与复用审查

核对日期：2026-10-27。本文逐项比较官方 **v2.4.0 → v2.5.1**，聚焦 MemoFlow 当前消费的语音识别、增强参数、上传、HTTP、登录与错误协议。MemoFlow v0.1.3固定官方2.5.1；已发布v0.1.2的2.4.0依赖及历史验收保持原有事实。

## 官方版本与源码

| 版本 | 官方源码 | 对照用途 |
| --- | --- | --- |
| v2.4.0 | [3638180f48b8fb1c7f99d5db91d3882d021710e5](https://github.com/modelstudioai/cli/tree/3638180f48b8fb1c7f99d5db91d3882d021710e5) | 升级前固定版本 |
| v2.5.1 | [3c8031f4d994c30820eb4d145d9404ba4a0acd39](https://github.com/modelstudioai/cli/tree/3c8031f4d994c30820eb4d145d9404ba4a0acd39) | 当前实现与依赖依据 |

官方[发布记录](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/CHANGELOG.md)用于定位变化；下列结论以两个固定提交的源码比较为准。源码缓存位于`.runtime/cli-2.4.0`和`.runtime/cli-2.5.1`，不进入发行包。

## 当前调用路径的比较

| 路径 | v2.4.0 → v2.5.1的实际变化 | MemoFlow处理 |
| --- | --- | --- |
| `speech/recognize.ts`与`client/asr-routes.ts` | 文件内容一致：固定模型仍走异步`file_urls`路径；即时热词、上下文、语言、说话人数与`--out`映射不变 | 继续复用完整识别入口，不增加新的API调用或异步恢复入口 |
| `speech/vocabulary-input.ts` | 文件内容一致：即时热词只解码JSON、确认对象形状与权重为有限数值 | 本机表格仍负责模型约束、重复行和单元格定位；不把CLI基础校验当成完整模型校验 |
| `buildAsrContextMessages()` | 所在`asr-routes.ts`一致：将原文包装为一条`input_text`，不执行400字符限制 | 保留预览前的非空、400个Unicode字符与可传输字符检查 |
| `files/upload.ts`与`client/http.ts` | 文件内容一致；`Client.uploadFile()`调用链也未改变 | 直接复用官方上传和HTTP期限，不恢复本地core修订或上传适配 |
| `auth/login-console.ts` | 先注册完成事件及15分钟计时器，再异步打开浏览器；空等明确返回TIMEOUT；结束却未保存凭据返回GENERAL；回调限制Origin、支持本地网络预检、要求`access_token`，并防止重复保存及关闭残留连接 | 正常登录仍由BL打开系统默认浏览器、管理回调和保存；Python继续等待原进程并解释非零结果 |
| `auth/login.ts` | 新增可选`--no-browser`与`--token-stdin`；限制其与登录模式、站点、地域的组合。OpenAPI登录先验证生成的控制台token再保存 | 当前仍调用`auth login --console --console-site domestic`；不因新增可选入口改变浏览器选择或增加token导入流程 |
| `auth/status.ts`、`auth/resolver.ts`与`auth/store.ts` | 文件内容一致：状态由本机凭据生成，模型Key与控制台token仍是不同凭据域 | 登录后继续调用公开状态命令，检查`api_key`存在；`authenticated=true`和登录退出0均不能单独证明ASR模型凭据存在或在线有效 |
| `auth/refresh-token.ts`与`Client.console()` | 按实际控制台地域、站点和switch agent刷新；透传已存`security_token`；校验非空生成结果；重放原控制台请求成功后才写入新token，并更新Client内存凭据 | 交给官方实现；当前ASR使用模型API Key及`requestJson()`，不经过此控制台刷新分支，不据此增加识别自动重试或模型Key刷新 |
| `shared/local-server.ts` | 文件内容一致：Windows仍通过完整URL引用、`cmd /d /v:off /s /c`与`windowsVerbatimArguments`打开系统默认处理程序 | 保持官方打开方式，不新增浏览器预加载、Python链接转交或浏览器指定 |
| `runtime/args.ts`与`errors/codes.ts` | 文件内容一致：未知参数、重复标量、缺值与无效数值校验不变；退出码集合不变 | 保留参数数组、单个`--context=原文`参数及官方结构化错误协议；错误字典的版本与源码依据同步更新 |

原生登录会先向stderr写进度与登录URL，失败时由[runtime/error-handler.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/runtime/src/error-handler.ts)追加错误JSON。本机超时合约确认原有整段json.loads会丢失这条官方说明，现读取末尾根JSON对象后沿用原脱敏处理；没有新增错误协议或登录器。

固定2.5.1源码：[recognize.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/commands/src/commands/speech/recognize.ts)、[vocabulary-input.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/core/src/speech/vocabulary-input.ts)、[asr-routes.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/core/src/client/asr-routes.ts)、[upload.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/core/src/files/upload.ts)、[http.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/core/src/client/http.ts)、[login-console.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/commands/src/commands/auth/login-console.ts)、[login.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/commands/src/commands/auth/login.ts)、[status.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/commands/src/commands/auth/status.ts)、[refresh-token.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/core/src/auth/refresh-token.ts)、[client.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/core/src/client/client.ts)、[local-server.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/commands/src/commands/shared/local-server.ts)、[args.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/runtime/src/args.ts)、[codes.ts](https://github.com/modelstudioai/cli/blob/3c8031f4d994c30820eb4d145d9404ba4a0acd39/packages/core/src/errors/codes.ts)。

## 原生能力与本机消费者

本次对照`utils/bailian.py`、`utils/auth.py`、`application/rules.py`及其`Session.validate()`预览消费者。在这些边界内，未发现可直接删除且不影响当前消费者的独立重复实现；仍有相同基础规则在界面预检和CLI执行入口分别检查，但职责和回执不同。

| 官方已提供的能力 | 当前项目中的对应职责 | 结论 |
| --- | --- | --- |
| 上传、识别提交、轮询、结果下载及原始JSON写入 | `recognition_arguments()`映射已确认配置，`run_recognition()`启动一次BL | 已复用；不维护另一套云端请求或轮询实现 |
| 系统浏览器打开、授权state、回调、凭据保存及登录超时 | `login_console()`检查桌面执行条件、等待原BL进程，并映射本地模型Key状态 | 已复用；先前core修订、Node预加载和Python链接转交已移除。本地`IsTokenRestricted`检查处理启动权限，不替代官方浏览器打开 |
| 控制台token刷新与本地凭据解析 | `console_status()`读取BL的公开JSON；Key模式从固定`.env`注入子进程环境 | 已复用；Python没有控制台刷新器，也不将控制台token当作模型Key |
| `auth login --api-key`在线验证并写入BL配置 | `auth.py`保存网页提供的Key到工作目录`.env`，仅检查空值/空白，不在线验证 | 保存位置、凭据生命周期和界面状态有明确消费者；不能替换为另一种会在线请求并写BL配置的登录操作 |
| 即时热词JSON形状与数值类型检查 | `rules.py`在上传前校验表格形状、Excel错误、词条长度、权重集合、2000条/50个超级词、重复组，并返回行/单元格错误 | 基础类型校验有交集；完整模型规则与界面定位未由CLI提供，应保留 |
| `--speaker-count`依赖`--diarization`及数字参数解析 | `validate_options()`在预览前返回对应字段错误，并限定整数2–100与本产品语言选项 | 依赖规则有交集，但本地预览有消费者；CLI未提供相同范围与字段回执 |
| 原文上下文封装、CLI参数解析 | `validate_context()`给出长度/字符位置；`check_command_length()`在发布任务前按真实Node命令计算Windows限制 | 官方没有等价的表单诊断或任务发布前长度检查，保留当前实现 |
| 结构化错误和退出码 | `explain_cli_error()`读取官方错误，隐藏Key/URL/增强原文，再映射本机任务错误回执 | 本地隐私与任务记录仍需此转换，不按通用错误推断云端是否已受理 |
| JSON和终端文本输出 | 本机媒体探测/单声道副本、结果结构检查及Excel/Word/Markdown校对稿生成 | 具有独立产品消费者；官方识别命令没有替代本项目的成品交付与会话授权协议 |

2.5.0新增/迁移的Memory、Workspace端点和dsh集成，以及2.5.1新增的调用者归属声明，均不改变当前ASR消费者。当前不因此接入个性化记忆、Agent编排或新增遥测；仍通过`DO_NOT_TRACK=1`关闭遥测。

## 保持的限制与执行策略

- 固定模型仍为`qwen-audio-3.1-asr-flash-filetrans`，北京地域、单文件、即时热词与上下文同时使用、说话人区分及输出结构保持。语音帮助仍提到Qwen 3.0，3.1能力依据模型官方API，不据帮助文字排除该模型。
- 取得临时上传凭证仍固定15秒；OSS上传仍整文件读入内存。项目传`--timeout 3600`，上传和识别轮询各使用3600秒预算；提交及每次状态请求也使用该timeout。最终转写JSON下载仍为原生`fetch()`，没有独立BL下载期限。
- Python整个识别进程上限仍为7500秒；该等待上限不是云端处理承诺。登录继续使用BL原生15分钟会话，Python不另设登录总时限。
- `--vocabulary`仍只收JSON文本，未提供即时词典文件参数；Windows完整命令长度限制仍需要在交接前检查。
- 完整模式未稳定提供可恢复的云端`task_id`；退出0仍须检查实际JSON。每任务一次尝试，失败或结果未知不自动重试；官方控制台凭据刷新中的一次原请求重放不扩展为ASR重试。

## 当前安装与验证边界

`scripts/bailian/package.json`及锁文件固定官方CLI、core、commands、runtime 2.5.1。工作目录检测到其他版本时停止并提示，仅重新准备其中的`.asr-transcription/.tools/bailian`；Python、Node、凭据、任务及结果位于独立位置，继续保留。具体操作见[使用指南](../skills/asr-transcription/references/usage.md)与[错误说明](../skills/asr-transcription/references/errors.md#常见问题处理)。

`NO_UPDATE_NOTIFIER=1`继续关闭官方后台版本查询，固定版本由项目更新维护。实际安装、命令及本机合约验证结果独立记录在[ACCEPTANCE](ACCEPTANCE.md)；源码比较不能代替真实用户桌面、浏览器本地网络权限、线上授权及云端录音识别验收。2.5.1对真实环境的改进效果仍须现场验证，不将2.4.0历史结果视为本次结果。
