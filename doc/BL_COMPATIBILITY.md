# 百炼 CLI 2.10.5 适配与复用审查

核对日期：2026-11-23。当前本地适配2.10.1→2.10.5，MemoFlow版本保持0.1.6；尚未提交或发布。下方逐项记录官方变化及当前调用边界，历史审查保留在文末。

## 结论

没有发现要求 MemoFlow 修改 ASR、浏览器登录、上传、超时、轮询或原始 JSON 保存协议的破坏性变化。共享入口的直接变化是 2.10.4 支持小写代理变量作为兜底，以及网络拒绝错误的恢复提示；可直接使用官方代理行为，无需本地增加代理转换。MemoFlow 当前回执有意不透传 BL `hint`，因此新版网络指引不会自动成为 MemoFlow 用户可见改进，不能宣传为现场网络故障已解决。

2.10.4 的 CPython/dashscope 运行时仅服务 RL/OPD 沙箱提交，支持 macOS/Linux，不能替换 MemoFlow Windows 私有 Python/Node 或 bootstrap/doctor。新增训练、蒸馏、路由及容量计费操作没有当前业务消费者；不接入现有单录音流程。不需要修改固定 ASR 模型或北京地域，也未发现可删除的本地补丁或重复实现。

## 固定版本与完整来源

实际执行 `git ls-remote --tags https://github.com/modelstudioai/cli.git 'v2.10.*'`；随后将五个明确标签 fetch 到 `.runtime/bl-2.10.5-upstream/cli`，检出目标固定提交。

| 版本 | CHANGELOG 日期 | 标签提交 | Release |
| --- | --- | --- | --- |
| 2.10.1（基线） | 2026-11-13 | `98ceadc00e00bd5043f266ba3781268e6b83b12f` | [基线发布](https://github.com/modelstudioai/cli/releases/tag/v2.10.1) |
| 2.10.2 | 2026-11-17 | `4f562d087362ec457dc4d7dbd9dbc2069b0d7113` | [2.10.2 发布](https://github.com/modelstudioai/cli/releases/tag/v2.10.2) |
| 2.10.3 | 2026-11-18 | `55a5eec03af31018294b339c032173c649bb31ab` | [2.10.3 发布](https://github.com/modelstudioai/cli/releases/tag/v2.10.3) |
| 2.10.4 | 2026-11-20 | `50e66d2bde6935ae32d2ed4f7b3d512a2ef88a6b` | [2.10.4 发布](https://github.com/modelstudioai/cli/releases/tag/v2.10.4) |
| 2.10.5 | 2026-11-23 | `84e54dc3497c1576bce51a6977c61847e0d5450f` | [2.10.5 发布](https://github.com/modelstudioai/cli/releases/tag/v2.10.5) |

固定 [中文 CHANGELOG](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/CHANGELOG.zh.md)、[英文 CHANGELOG](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/CHANGELOG.md)、[完整比较](https://github.com/modelstudioai/cli/compare/v2.10.1...v2.10.5)。四版共 **12 个顶层日志条目（1+1+5+5）**，为完整呈现子能力，下面展开 **20 行**，不是 20 个独立 Release 条目。2.10.2 Release 只有简短的 PR #324 链接，细节取固定 CHANGELOG 与 [PR #324](https://github.com/modelstudioai/cli/pull/324) 对应提交；不能称四份 Release 正文全部与 CHANGELOG 一致。

官方 GitHub API Release JSON 已保存 `release-2.10.{2,3,4,5}.json`，目标两份 CHANGELOG 保存于审查目录。GitHub API 匿名读取成功；浏览器 web 工具对这些 URL 返回 DisabledError，已用官方 API/raw/git 正常取得证据，没有读取或打印认证凭据。

## 完整变化、关联能力与处理决定

| # | 版本 | 官方变化（包含全部子项） | MemoFlow 影响、复用机会与处理 |
| --- | --- | --- | --- |
| 1 | 2.10.2 | `monitor delivery enable`、`log audit enable`、`log inference enable` 不再自动创建服务关联角色；先查角色状态，缺失时中止并给出双语手工授权及模型可观测文档指引。 | **当前无调用，权限语义变化已记录。** 这是云端监控/日志投递的 SLR，不是 CLI 匿名遥测、API Key 校验或浏览器授权。当前不初始化 SLS 或授予跨服务角色；未来若增加云端可观测能力应直接复用官方检查，不恢复自动创建。 |
| 2 | 2.10.3 | `workspace list` 不再只读网关默认首 10 条；分页列出可访问空间。遥测、告警、日志、数据集、文件、部署命令的 Console 空间解析也覆盖后续页。 | **共享 Console 能力改善，当前 ASR 路径不依赖空间清单。** 当前凭据固定工作目录/default，清理外部 BAILIAN_WORKSPACE_ID，不动态选择 Console 空间。浏览器回调仍直接持久化凭据，auth status 仍读本地；不新增业务空间发现或迁移。未来查询可复用原生分页。 |
| 3 | 2.10.4 | 新 `finetune rl authorize` 检查白名单、SLR、业务开通；缺角色给手工授权指导，绝不自动创建。`--authorize` 开通 RL 训练模式，高风险需 `--yes`。 | **后续训练候选，当前无影响。** 热词、上下文及纪要偏好不是云端 RL 授权；不在录音确认中顺带开通训练或授权资源。 |
| 4 | 2.10.4 | 新 `finetune rl run` 可用 flag/YAML 提交并打包 Rollout/Reward 代码，在托管 OS 沙箱 Python 运行时执行，仅 macOS/Linux；消耗计费 MTU，经过 dry-run→明确确认→yes；watch 到终态，超时不取消云任务。 | **后续训练候选，当前 Windows 产品不适用该提交运行时。** 不用它替换 ASR 提交/轮询、一次执行边界或会话确认；当前不创建训练任务。 |
| 5 | 2.10.4 | 新 RL `get/list/watch/logs/cancel/delete` 通过共享 fine-tunes 后端管理任务；get 保留完整 OpenAPI 响应，包括数据集和 MTU 规格/容量。 | **后续训练管理候选。** fine-tunes 任务不是 ASR task_id/job_id；这些取消/删除操作不能用于恢复或取消现有转写。原始转写 JSON 保存保持 recognize 原生实现。 |
| 6 | 2.10.4 | 新 `finetune opd authorize/run/params/get/watch/logs/cancel/delete`，以平台注册教师模型执行纯模型在线蒸馏 `pg_opd`；run 支持计费提交前 dry-run，params 查学生基座支持的训练超参数。 | **后续模型蒸馏候选。** 当前使用公共固定 ASR，无教师/学生模型、训练数据或 MTU 消费者；不把偏好反馈学习提前实现为 OPD，不替换热词校验。 |
| 7 | 2.10.4 | 新 `finetune runtime prepare` 从审查后的多源清单下载固定 CPython+dashscope，SHA256 校验、镜像回退、缓存复用；支持 BAILIAN_RL_PYTHON_MIRROR、BAILIAN_RL_PIP_INDEX_URL、BAILIAN_RL_RUNTIME 开发运行时覆盖。 | **原生运行时能力，但不能替换现有安装器。** 它服务 RL/OPD，清单仅 darwin/linux，Python 3.11.9、dashscope 1.25.23；MemoFlow 用 Windows Python 3.12.10、Node 24.21.0 及文档/媒体依赖。保留既有 runtimes.json、bootstrap 和锁依赖，不引入第二套运行时。 |
| 8 | 2.10.4 | 新 runtime doctor 验证凭据禁读、home 重定向、SDK 导入、代理出口管控；宿主出站可达性是增强检查，网络被 agent 沙箱阻断时给指导。 | **不能替换 MemoFlow doctor。** 检查对象是 RL/OPD 执行沙箱，不是安装、BL 版本和文件转写前提；不为 ASR 增加网络探测、训练 SDK 或权限流程。 |
| 9 | 2.10.4 | 新 runtime clean 回收孤儿任务目录和旧运行时，支持 dry-run，当前基线运行时不删。 | **当前无影响。** 其目录不属于 MemoFlow 原录音、任务和结果管理；不调用它清理用户工作区，也不增设清理器。 |
| 10 | 2.10.4 | EPERM/EACCES/ENETUNREACH/EHOSTUNREACH 连接级拒绝增加双语执行环境/出站网络指引，建议放行网络、普通终端或 HTTPS_PROXY；运行时下载错误保留底层 errno。 | **直接涉及共享错误提示，实际传播边界已核对。** BL 的网络分类/退出码/JSON 字段未改，只改 hint；MemoFlow explain_cli_error 读取 message/api_code/request_id/http_status，不透传 hint/cause。沿用脱敏回执和人工按证据恢复，不自行诊断所有拒绝都是沙箱，不声称网页获得该 hint。RL 下载 errno 不进入现有安装链。 |
| 11 | 2.10.4 | 大写 HTTP_PROXY/HTTPS_PROXY/NO_PROXY 未设置时，小写 http_proxy/https_proxy/no_proxy 作为兜底，大写优先。 | **直接相关，可直接复用。** MemoFlow child_environment 原样继承网络设置，BL 自己安装 EnvHttpProxyAgent；不新增代理规范化、全局设置或重试。源码用 nullish coalescing：已存在的空白大写值不会触发小写兜底；Windows 环境本身大小写不敏感，不能凭此宣称 Windows 新增两套独立变量优先级。建议执行现有代理继承回归，必要时纯对象验证 pick 规则。 |
| 12 | 2.10.5 | 新 `deploy router versions` 分页返回后付费模型路由 plan=mr 的版本、支持策略、候选模型。 | **后续模型路由候选。** 当前显式固定 ASR 模型，不选择候选模型或路由版本；不修改模型来源。 |
| 13 | 2.10.5 | `deploy router create` 接收 name/route-version/strategy（EFFECT_FIRST/COST_FIRST）/candidates；创建即 RUNNING，dry-run→确认→yes。 | **后续部署候选，当前无影响。** 现有 ASR 使用公共模型不创建部署，不引入计费路由或动态模型选择。 |
| 14 | 2.10.5 | `deploy router list/get` 查询路由，get 验证目标 plan=mr。 | **后续资源管理候选。** 本地任务列表和识别回执不是模型部署，不替换本地查询。 |
| 15 | 2.10.5 | `deploy router update` 更新 RUNNING 路由的指定项，保留省略字段；candidates 整体替换候选列表。 | **当前无影响。** 无路由配置消费者，不能将可变路由更新引入已冻结转写任务；未来使用时注意整表替换语义。 |
| 16 | 2.10.5 | `deploy router delete` 确认后永久删除路由，RUNNING 不必先停止。 | **当前无影响。** 当前不创建或删除部署，不能用于删除 MemoFlow 转写记录。 |
| 17 | 2.10.5 | 新 `deploy capacity auto-renew enable/disable` 对单个预付费容量实例控制自动续费，cycle Day/auto-renewal-duration；两者均高风险计费，支持 dry-run 和实例能力预检；不支持 8 小时闲时实例。 | **当前无影响。** 当前公共 ASR 不购买预付费容量，不接入自动续费或与免费额度错误恢复混用。 |
| 18 | 2.10.5 | `deploy capacity create`、`deploy text create --plan ptu` 可用 pricing-cycle Hour/duration 8/auto-renewal false 买预付费 8 小时闲时容量；PTU 还需 service-tier ptu_default；服务端验证北京 22:00–24:00 售卖窗口和模型支持；不许变配、续订、自动续费、释放、退订，到期自动失效。 | **当前无影响。** 这是模型部署计费窗口，不是 ASR 音频时长、上传有效期或等待超时；不改当前录音限制和 PROCESS_SECONDS。 |
| 19 | 2.10.5 | PTU `deploy text create --thinking-output-tpm` 不再被本地一概拒绝，由服务端依模型校验。 | **后续文本模型部署候选。** 当前文件识别无 thinking-output-tpm，后续纪要也不因此需要 PTU；不加思考容量选项。 |
| 20 | 2.10.5 | 通用 `deploy delete` 识别 plan=mr，允许 RUNNING 模型路由不经停机直接删除。 | **当前无影响，删除语义单独记录。** 当前无 deploy delete 调用，既有任务取消边界不变；未来路由删除复用官方能力，不自写绕过停机。 |

## 当前消费路径与源码补充

对旧审查的 29 路径逐项比较标签 Git blob，**26 相同、3 变化**。证据文件 `consumer-comparison.json` 同时记录基线与目标 blob；额外 15 路径在 `extra-comparison.json`（6 变化、9 相同）。两者路径没有重复，共 44 个核对路径，35 相同、9 变化。生产包版本文件只是版本字符串变化。

- 完全相同：speech/recognize.ts、client/asr-routes.ts、speech/vocabulary-input.ts、files/upload.ts、client/client.ts、client/http.ts、client/transport.ts、utils/polling.ts；固定 filetrans 路由、即时热词、context、说话人、提交、上传和结果下载保持。
- 完全相同：auth/login.ts、login-console.ts、login-api-key.ts、status.ts、core auth/resolver.ts、refresh-token.ts、store.ts、shared/local-server.ts、config/loader.ts、paths.ts；浏览器授权/本地状态与模型凭据解析保持。
- 完全相同：runtime args.ts、create-cli.ts、middleware.ts、output/reporter.ts、types/command.ts、errors/base.ts、codes.ts、api.ts、config/schema.ts；全局参数、错误码、JSON 字段及 stdout/stderr 边界保持。
- 完全相同：telemetry/tracker.ts、sink.ts、utils/update-checker.ts、packages/cli/postinstall.js、pnpm-lock.yaml、pnpm-workspace.yaml；现有 DO_NOT_TRACK=1、NO_UPDATE_NOTIFIER=1 和跳过 Wiki 预取的处理仍适用，未引入新的外部运行依赖。
- `runtime/proxy.ts`、`runtime/error-handler.ts` 的全部改动对应第 10/11 行；错误分类保持 NETWORK=6、TIMEOUT=5，BailianError 直通逻辑和 hint 与 message 分离保持。网络提示不是新增连接超时、重试或代理自动发现。
- `core/console/gateway.ts` 仅把 cornerstoneParam 构造与 HTTP/业务响应解释提取为函数；字段顺序/覆盖规则、请求时限及错误透传行为保持。额外检查 `client/console-session.ts`：request 通过新 dispatch 闭包共享惰性凭据签发与过期刷新；先执行请求、成功后提交凭据的顺序保持。不能笼统写所有共享鉴权文件字节未变。
- `client/endpoints.ts` 只新增部署自动续费和路由版本路径，不改变 ASR 路径。
- 2.10.3 工作空间“全量”有实现边界：每页 100，最多 100 页；无法识别新响应或缺 total 时回退旧单页读取，服务端错误继续抛出。正常网关可跨页，不能承诺任意旧网关都全量。此点来自 shared/workspace.ts。
- 除日志顶层条目外，2.10.4 源码伴随训练功能增加 `supports: {fineTune:true}` 的训练目录查询，训练/数据集 API 可选 X-DashScope-WorkSpace，finetune get 加 teacher_model、training_datasets、validation_datasets、MTU 字段，提取 dataset-input 供复用；这些在训练消费者内，不替换临时 OSS 上传或固定 ASR 模型解析。新增官方 `skills/bailian-opd` 的 preflight/submit/wait 资料和脚本也属于 OPD，MemoFlow 不随包附带或执行。

## 关键固定源码链接

- [recognize](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/commands/src/commands/speech/recognize.ts)：上传 L281、提交/轮询 L455 起、转写地址读取 L530、out 写入 L569 起；对单结果仍直接保存对象，多结果保存数组。
- [upload](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/core/src/files/upload.ts)、[http](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/core/src/client/http.ts)、[polling](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/runtime/src/utils/polling.ts)：时限实现均与基线一致。
- [proxy](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/runtime/src/proxy.ts)、[代理单测](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/runtime/tests/proxy.test.ts)：nullish 小写兜底和大写优先。
- [error-handler](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/runtime/src/error-handler.ts)、[network-diagnostics](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/core/src/client/network-diagnostics.ts)：四种拒绝码和 hint；后者的多层 cause 提取用于 RL 运行时，不等于既有所有命令错误都新增多层提取。
- [workspace](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/commands/src/commands/shared/workspace.ts)、[SLR 检查](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/commands/src/commands/shared/telemetry.ts)：分页及角色检查语义。
- [gateway](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/core/src/console/gateway.ts)、[console-session](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/core/src/client/console-session.ts)：等价提取。
- [Windows 隔离占位](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/core/src/isolation/os-isolation/windows.ts)、[RL 清单](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/core/src/rl-runtime/manifest.ts)：Windows RL 提交 fail-closed，不能据此说整个 BL 不支持 Windows。
- [CLI package.json](https://github.com/modelstudioai/cli/blob/84e54dc3497c1576bce51a6977c61847e0d5450f/packages/cli/package.json)：发布包 Node engines 仍 >=18.17.0；core/commands/runtime 同样保持。官方源码 monorepo package.json 的开发要求 ^22.18.0 || >=24.11.0 也未变；MemoFlow 私有 Node 24.21.0 满足，不能将 monorepo 开发要求误写成新运行要求。

## 适配与验证范围

最小适配是四个官方包锁定 2.10.5、同步固定版本常量和固定来源文档；现有 ASR、凭据、进程、网络、轮询、导出调用保持。正式项目版本是否递增属于发布任务，不由本次审查决定。

本轮采用隔离安装/doctor 及现有 BL 合约用例：模拟上传→提交→轮询→out，固定模型/热词/context/说话人；auth login 的 text 参数及 auth status JSON；default Profile/环境隔离；代理继承；错误 JSONL、退出码与脱敏字段；包内文件边界。新增小写代理行为可用官方 readProxyEnv 的纯对象 case 检查，不需要云识别；若只按现有 Windows 环境验证，应准确说明没有验证 POSIX 大小写并存环境。

无需为未调用的训练、路由、计费能力执行会产生资源的验证，也无需为相同 ASR 算法重跑真实录音。不能将源码一致性/模拟结果称为真实网络、用户授权、云端识别或 Windows RL 训练验收。保持上传 policy 的 15 秒、BL 请求/轮询、结果下载和外层进程时限各自边界；本轮没有“统一延长超时”的变化。



### 已执行检查

本项目npm锁由包管理器更新：除四个BL包外，原有间接依赖bare-buffer 3.7.2→3.7.3、bare-fs 4.8.4→4.8.5、bare-url 2.5.7→2.5.8按既有版本范围重新解析，没有新增包名。下述安装与合约测试使用这份实际锁；“官方pnpm锁未变”不等同于本项目npm锁的间接版本完全不变。

独立工作目录 `.runtime/bl-2.10.5-workspace` 通过官方归档准备Python3.12.10/Node24.21.0，创建新venv并联网安装BL2.10.5；复用已核对的运行时ZIP及wheel缓存，未复用旧BL安装。bootstrap成功，doctor的issues为空。`test_bl_contract/test_bl_upload/test_bailian/test_environment/test_bootstrap/test_installation/test_npm_install_contract/test_runtime_bootstrap/test_package` 共158项通过（240.037秒、无跳过）。覆盖实际新版BL与本机模拟服务、代理继承、凭据和输出/错误合约；没有真实云端识别或未使用训练能力调用。

BL版本适配只改固定版本、npm锁和官方来源元数据；额外项目审查及后续获准的业务修正记录在[REVIEW](REVIEW.md)。

## 历史审查记录

## 百炼 CLI 2.10.1 适配与复用审查

核对日期：2026-11-15。当前在dev适配官方2.8.4→2.10.1，MemoFlow项目版本沿用0.1.5；尚未发布本轮改动。上次记录见[v0.1.5的审查](https://github.com/hx101700/memoflow/blob/v0.1.5/doc/BL_COMPATIBILITY.md)。

### 结论

未从官方完整发布记录及当前消费文件比对中发现要求 MemoFlow 改写 ASR 调用或登录流程的破坏性变化。当前显式 `--output json/text`、`--config default` 与固定模型/北京URL符合新版要求。主要共享变化是参数校验、错误恢复提示及遥测延迟初始化；ASR、上传、HTTP、轮询、浏览器登录、状态响应和凭据解析相关实现保持。没有发现可以删除的本地重复实现，也不需要接入新的应用管理、训练、部署或额度控制命令。

两个必须准确记载的边界：

1. 2.10.0 将2.9.0新增应用控制面移至 `flow-agent`，旧 `app call/list` 仅弃用；此为外部应用管理命令变化，当前文件识别不调用。
2. 2.9.0官方日志称遥测uid替代device_id，但目标源码和测试表明新增持久匿名uid、底层Tracker仍保留device_id。MemoFlow的 `DO_NOT_TRACK=1` 使事件和sink调用被跳过，且初始化延迟至首次远端上报，因此不会创建新uid。不能照抄“device_id完全移除”。

### 固定版本与来源

`git ls-remote --tags https://github.com/modelstudioai/cli.git 'v2.8.*' 'v2.9.*' 'v2.10.*'` 已执行。区间 `(2.8.4,2.10.1]` 只有以下五个版本；目标中英 CHANGELOG 与五个 Release 正文一致，共 **21个顶层条目**（5+5+6+2+3）。为了完整覆盖应用管理的子项，下面展开为 **26行**，并非26条独立Release条目。

| 版本 | 日期 | 官方提交 |
| --- | --- | --- |
| 2.8.4（基线） | 2026-11-06 | `cadc301d078f0fd1f2c56f7bf94f32c55bbb055d` |
| 2.8.5 | 2026-11-10 | `fa8330c27862635f7d769c5488c33a06a47063d5` |
| 2.8.6 | 2026-11-12 | `0f870ab9053023844b410ae53ee11ffda7fba1df` |
| 2.9.0 | 2026-11-12 | `971a1cc91004c2cf7d92626c28af0f7c8c4a25da` |
| 2.10.0 | 2026-11-13 | `eef8336f608ef1681570f07c1d98096b01f2b6ea` |
| 2.10.1 | 2026-11-13 | `98ceadc00e00bd5043f266ba3781268e6b83b12f` |

官方资料：[固定中文CHANGELOG](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/CHANGELOG.zh.md)、[固定英文CHANGELOG](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/CHANGELOG.md)、[2.8.5 Release](https://github.com/modelstudioai/cli/releases/tag/v2.8.5)、[2.8.6 Release](https://github.com/modelstudioai/cli/releases/tag/v2.8.6)、[2.9.0 Release](https://github.com/modelstudioai/cli/releases/tag/v2.9.0)、[2.10.0 Release](https://github.com/modelstudioai/cli/releases/tag/v2.10.0)、[2.10.1 Release](https://github.com/modelstudioai/cli/releases/tag/v2.10.1)。

中英日志、逐版Release与源码归档均保存在被忽略的.runtime目录。目标提交由Git标签和官方API核对；29个主流程消费文件与tar.gz归档成员逐字一致，中文日志也与归档相同。

### 完整变化、关联能力与处理决定

| # | 版本 | 官方变化（含所有子项） | MemoFlow影响、复用机会与处理 |
| --- | --- | --- | --- |
| 1 | 2.8.5 | 精调创建先查询权威训练超参配置，仅校验用户显式覆盖且有约束的值；查询/校验失败不上传/提交，未指定参数不再本地补值或裁剪 | **后续训练候选，当前无影响。** 当前调用公共固定ASR模型，不提交精调任务，热词/上下文也不是训练超参。后续若训练模型可直接复用官方前检，当前不新增训练配置或替换本地热词规则。 |
| 2 | 2.8.5 | 部署删除优先显式计划，忽略残留PTU形状字段；计划不明确时拒绝删除 | **当前无影响。** 当前录音识别不创建或删除模型部署，不依赖PTU/部署计划推断；后续若增加部署管理应复用该原生安全判断，不自写删除逻辑。 |
| 3 | 2.8.5 | `text chat --enable-thinking=false` 可显式关闭思考，省略和裸参数行为保持；关闭时不发送thinking_budget | **后续纪要生成候选，共享参数解析已核对。** 当前不调用Chat/思考参数。runtime布尔隐式值支持不改变当前ASR的switch/string/number参数；不为当前转写新增思考开关。 |
| 4 | 2.8.5 | 模型示例代码必须精确匹配型号，不再回退到同系列其他型号 | **开发资料能力改善，当前无运行影响。** MemoFlow模型参数由固定官方源码和模型规格核对，不动态使用sample-code生成调用；后续查示例可复用精确匹配，不能因此替换本机已核实规则。 |
| 5 | 2.8.5 | 数据集上传帮助移除不支持的evaluation purpose，默认仍fine-tune | **当前无影响。** 当前临时OSS上传由 `speech recognize` 触发，不调用训练数据集上传，无evaluation purpose参数；不更改录音上传器或用途。 |
| 6 | 2.8.6 | `dataset groups` 支持分页/名称筛选；`dataset version` 通过dataset-group-id列组内版本或dataset-id查单版本，include-status可补状态 | **后续训练资料管理候选。** 此为Console数据集资源查询，与当前本机录音、热词Excel和转写JSON不同；API Key域dataset list/get保留，不需要现有数据迁移。 |
| 7 | 2.8.6 | `file url --file-key` 将Console文件键解析为下载URL，不自动下载 | **后续Console资料读取候选，不能替代当前下载。** 当前识别结果地址来自ASR任务，录音上传使用临时OSS；两者均不是Console file key。继续直接复用recognize的结果下载，不增加第二次地址解析。 |
| 8 | 2.8.6 | `deploy instances` 查询Console部署，支持分页、关键词和模型服务ID筛选；原API Key域deploy list保持 | **后续部署管理候选，当前无影响。** 当前固定公共ASR模型没有部署实例消费者，地域和模型来源保持既有约束，不新增实例发现。 |
| 9 | 2.8.6 | Console嵌套成功/失败响应解析改进，保留服务消息、错误码、请求ID，修复有效工作空间列表被读成空 | **共享依赖路径已核对，当前常规ASR/浏览器回调不触发新增解析。** 新unwrapConsoleResponse用于Console类型化查询及工作空间/应用读取；gateway改进其业务失败透传。正常浏览器回调直接persistApiKey，auth status读本地状态，ASR走模型HTTP。保留官方能力，不把它称为转写HTTP或网页Key校验新功能。 |
| 10 | 2.8.6 | 显式空白 `--workspace-id` 被拒绝，不再回退到已配置空间 | **共享入口直接相关，当前参数符合。** MemoFlow不传该flag，且清理外部BAILIAN_WORKSPACE_ID；本地 `--workspace` 是另一入口的文件目录。无需新增重复空值校验，也不删除工作区绑定。 |
| 11 | 2.9.0 | 新应用控制面 `app create/get/update/publish/delete/copy/versions`，通过Console网关管理app-control 2.0智能体及工作流；delete高风险需yes | **后续云端应用编排候选。** 当前本机两步表单和单任务执行不是百炼应用控制面，不能替代session_id/job_id或用户上传确认。本轮不创建云端资源；目标版本对应flow-agent，见19/23。 |
| 12 | 2.9.0 | `app workflow get/save/publish/export` 管理画布；save整幅替换草稿并带乐观锁，publish按控制台逻辑规范化触发器 | **后续工作流候选，当前无影响。** MemoFlow既有UML和执行记录不是云端画布，没有草稿版本消费者；不将工作流发布接入当前一次识别。目标命令位置见20/23。 |
| 13 | 2.9.0 | 更新应用智能体时先读取当前草稿，再合并model/instructions/config-json/config-file | **后续应用配置候选。** 当前转写交接冻结的是本机任务，不能借用“合并草稿”改动已授权配置；不新增云端Agent配置或改写固定模型。 |
| 14 | 2.9.0 | `app list --type workflow` 按控制台排除法列出工作流 | **后续工作流发现候选。** 当前不查询应用清单，已有本地任务查询语义不同，不替代job-status；目标位置见22/23。 |
| 15 | 2.9.0 | Omni默认模型从qwen3.5-omni-plus改为qwen3.8-omni-flash | **当前无影响。** MemoFlow显式固定qwen-audio-3.1-asr-flash-filetrans，使用文件识别，既不调用omni也不依赖其默认模型；不跟随更换产品ASR模型。 |
| 16 | 2.9.0 | 免费额度模型操作收紧确认闸门和错误处理，恢复操作在闸门之后 | **额度管理当前无调用；共享错误提示已核对。** 新FreeTierOnly hint给出usage free及停用自动停止的指引，后者不带yes、仍需确认。MemoFlow不消费/执行hint，不自动改为付费、不自动重试，继续解释原错误码与保留任务。不能将新增提示称为已实施额度恢复。 |
| 17 | 2.9.0 | API Key回退后的恢复提示保留显式config，命名Profile提示附config | **直接涉及共享错误呈现，当前无需兼容层。** MemoFlow固定 `--config default`，新版recoveryConfigName会让提示保留default而非意外选择活动Profile；实际凭据解析链不变。本地回执不透传hint，模型Key隔离和现有错误JSON字段保持。 |
| 18 | 2.9.0 | 官方日志概述匿名uid替代device_id并原子发布，避免短写/陈旧锁竞争 | **共享遥测实现变化，当前关闭。** 源码是新增持久uid及延迟初始化，底层device_id仍存在；DO_NOT_TRACK=1在事件/sink之前返回，不创建telemetry-uid。继续原禁用配置，不新增清理器或身份管理层。详见下方差异记录。 |
| 19 | 2.10.0 | 新flow-agent组：create/get/update/publish/delete/copy/versions管理智能体/工作流，delete需yes | **2.9控制面的目标命令迁移，后续候选。** 当前不调用旧app控制面，无需改ASR；未来应用管理应使用flow-agent，不在本轮引入原生SDK或应用生命周期。 |
| 20 | 2.10.0 | `flow-agent workflow get/save/publish/export`；保留整幅草稿替换、乐观锁和触发器规范化 | **迁移后的工作流候选。** 与12相同业务边界，当前不接入；避免用此云端工作流替代本机上传确认/单次任务状态。 |
| 21 | 2.10.0 | flow-agent智能体更新先读当前草稿，再合并model/instructions/config-json/config-file | **迁移后的配置候选。** 与13相同边界，当前没有草稿消费者，不添加可变云端配置。 |
| 22 | 2.10.0 | `flow-agent list --type workflow` 使用控制台排除法 | **迁移后的发现候选。** 与14相同边界，不改变本地任务记录和查询。 |
| 23 | 2.10.0 | `app call/list`弃用，建议flow-agent call/list，未来移除；2.9新增控制面仅保留在flow-agent | **外部命令破坏性迁移已记录，当前无调用方。** MemoFlow只调用speech recognize/auth及必要config恢复，不需要应用兼容别名；未来调用新路径，不把“弃用call/list”错误表述为本版已移除全部app组。 |
| 24 | 2.10.1 | `--output`仅接受text或json，其余执行前拒绝 | **直接涉及所有BL命令参数，当前满足。** MemoFlow浏览器登录text、识别/状态json，固定值不受拒绝；版本探针无output。保留现有参数，不新增本机输出格式校验层。 |
| 25 | 2.10.1 | usage free/freetier对全部模型且清单未解析时，dry-run明确all/unresolved范围 | **当前无影响。** 当前产品不操作免费额度配置或消费其预览，不可把未解析范围当实际模型清单；未来额度诊断可复用官方准确预览，当前不增加此命令。 |
| 26 | 2.10.1 | API Key登录校验遵循配置的请求超时，不再被固定短期限提前中断 | **共享登录模块已核对，当前路径不经过校验函数。** 旧上限为min(settings.timeout,5s)，现在settings.timeout。网页仅保存.env，浏览器回调直接persistApiKey，不能宣传为当前网页登录超时修复，更不等于延长Undici连接或ASR下载时限。 |

### 当前消费源码比对

独立复核的26个路径中19个相同、7个不同；主流程扩大到29个消费路径并核对官方归档成员。各清单在.runtime保存，范围不同分别计数。相同的核心范围包括：

- `speech/recognize.ts`、`client/asr-routes.ts`、`speech/vocabulary-input.ts`；固定模型映射、即时热词、上下文及说话人参数保持。
- `files/upload.ts`、`client/client.ts`、`client/http.ts`、`client/transport.ts`、`runtime/utils/polling.ts`；上传、请求、轮询和下载机制保持。
- `auth/login.ts`、`login-console.ts`、`status.ts`、core的`auth/resolver.ts`、`store.ts`、`refresh-token.ts`；浏览器登录和本地状态/凭据结构保持。
- `shared/local-server.ts`、runtime的`proxy.ts`、`utils/update-checker.ts`、core的`errors/base.ts`及`codes.ts`。

不同的7个消费文件：`login-api-key.ts`、`config/loader.ts`、runtime的`args.ts`、`create-cli.ts`、`middleware.ts`、`error-handler.ts`、`output/reporter.ts`。已阅读对应完整变化，分别落在上表布尔参数、输出/工作空间校验、Profile恢复提示和Key校验超时范围。JSON error序列化和stdout/stderr分离仍保持；错误代码/字段未变。不把源码比对说成真实云端验收。

主要固定源码依据：

- [recognize](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/commands/src/commands/speech/recognize.ts)：识别入口和out契约。
- [login-api-key](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/commands/src/commands/auth/login-api-key.ts)、[login-console](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/commands/src/commands/auth/login-console.ts)：校验超时与浏览器回调分别处理。
- [Console response](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/src/console/response.ts)、[Console gateway](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/src/console/gateway.ts)：类型化读取解包及业务错误透传。
- [create-cli](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/runtime/src/create-cli.ts)、[global flag定义](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/src/types/command.ts)：空workspace-id及output枚举校验。
- [error-handler](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/runtime/src/error-handler.ts)、[reporter](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/runtime/src/output/reporter.ts)、[loader](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/src/config/loader.ts)：FreeTierOnly提示、Profile固定及输出合同。

### 遥测文档与源码差异

官方2.9.0 Release/CHANGELOG写“以持久化的匿名uid替代匿名device_id”。目标[uid.ts](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/src/telemetry/uid.ts)注释却明确 `built-in Tracker device_id is unchanged`；[telemetry-send测试](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/tests/telemetry-send.test.ts)也叫 `constructor uid reaches send config without replacing built-in device_id`。底层 `packages/core/lib/remote-telemetry/tracker.cjs` 仍含device_id计算。因此按可执行源码记录“新增持久化uid、底层device_id保留”。

MemoFlow仍设置DO_NOT_TRACK=1；目标loader强制settings.telemetry=false，[tracker](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/src/telemetry/tracker.ts)在创建事件和sink前直接执行业务并返回。[sink](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/src/telemetry/sink.ts)的Tracker和ensureUid改为首次remoteSink才初始化；flush不会主动初始化。对应官方测试包含“importing sink without reporting does not create the uid file”和“telemetry disabled does not create the uid file”，本报告只阅读，未将其记为本机已运行通过。

### 实现及验证范围

CLI、core、commands、runtime通过npm原生锁定官方2.10.1；MemoFlow运行代码仅修改固定版本常量，没有修改鉴权、参数、错误解析、上传、轮询、导出或更新流程。当前参考资料与错误字典指向目标固定提交；04/05 UML仅更新版本并按原主题渲染。模型保持Qwen-Audio-3.1-ASR-Flash-Filetrans。

独立工作目录重新解压运行时、创建venv及安装BL2.10.1，bootstrap与doctor通过。现有152项相关测试通过，覆盖当前ASR参数/输出、模拟上传、登录text与status JSON、JSONL错误、default Profile、环境继承、安装、更新和包边界。严格类型、Skill格式、文档及候选包检查通过，实际命令与证据见[ACCEPTANCE](ACCEPTANCE.md)。

未重复真实授权或云端识别，未运行未使用能力的上游测试；前端、本机文档排版及未变化算法沿用已有验证。上传policy、Undici连接、BL请求/轮询和外层进程时限保持各自原有边界，本次不宣称解决现场网络可达性。当前没有新的业务消费者要求增加流程、校验或重试。
