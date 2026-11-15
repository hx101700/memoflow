# 百炼 CLI 2.10.1 适配与复用审查

核对日期：2026-11-15。当前在dev适配官方2.8.4→2.10.1，MemoFlow项目版本沿用0.1.5；尚未发布本轮改动。上次记录见[v0.1.5的审查](https://github.com/hx101700/memoflow/blob/v0.1.5/doc/BL_COMPATIBILITY.md)。

## 结论

未从官方完整发布记录及当前消费文件比对中发现要求 MemoFlow 改写 ASR 调用或登录流程的破坏性变化。当前显式 `--output json/text`、`--config default` 与固定模型/北京URL符合新版要求。主要共享变化是参数校验、错误恢复提示及遥测延迟初始化；ASR、上传、HTTP、轮询、浏览器登录、状态响应和凭据解析相关实现保持。没有发现可以删除的本地重复实现，也不需要接入新的应用管理、训练、部署或额度控制命令。

两个必须准确记载的边界：

1. 2.10.0 将2.9.0新增应用控制面移至 `flow-agent`，旧 `app call/list` 仅弃用；此为外部应用管理命令变化，当前文件识别不调用。
2. 2.9.0官方日志称遥测uid替代device_id，但目标源码和测试表明新增持久匿名uid、底层Tracker仍保留device_id。MemoFlow的 `DO_NOT_TRACK=1` 使事件和sink调用被跳过，且初始化延迟至首次远端上报，因此不会创建新uid。不能照抄“device_id完全移除”。

## 固定版本与来源

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

## 完整变化、关联能力与处理决定

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

## 当前消费源码比对

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

## 遥测文档与源码差异

官方2.9.0 Release/CHANGELOG写“以持久化的匿名uid替代匿名device_id”。目标[uid.ts](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/src/telemetry/uid.ts)注释却明确 `built-in Tracker device_id is unchanged`；[telemetry-send测试](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/tests/telemetry-send.test.ts)也叫 `constructor uid reaches send config without replacing built-in device_id`。底层 `packages/core/lib/remote-telemetry/tracker.cjs` 仍含device_id计算。因此按可执行源码记录“新增持久化uid、底层device_id保留”。

MemoFlow仍设置DO_NOT_TRACK=1；目标loader强制settings.telemetry=false，[tracker](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/src/telemetry/tracker.ts)在创建事件和sink前直接执行业务并返回。[sink](https://github.com/modelstudioai/cli/blob/98ceadc00e00bd5043f266ba3781268e6b83b12f/packages/core/src/telemetry/sink.ts)的Tracker和ensureUid改为首次remoteSink才初始化；flush不会主动初始化。对应官方测试包含“importing sink without reporting does not create the uid file”和“telemetry disabled does not create the uid file”，本报告只阅读，未将其记为本机已运行通过。

## 实现及验证范围

CLI、core、commands、runtime通过npm原生锁定官方2.10.1；MemoFlow运行代码仅修改固定版本常量，没有修改鉴权、参数、错误解析、上传、轮询、导出或更新流程。当前参考资料与错误字典指向目标固定提交；04/05 UML仅更新版本并按原主题渲染。模型保持Qwen-Audio-3.1-ASR-Flash-Filetrans。

独立工作目录重新解压运行时、创建venv及安装BL2.10.1，bootstrap与doctor通过。现有152项相关测试通过，覆盖当前ASR参数/输出、模拟上传、登录text与status JSON、JSONL错误、default Profile、环境继承、安装、更新和包边界。严格类型、Skill格式、文档及候选包检查通过，实际命令与证据见[ACCEPTANCE](ACCEPTANCE.md)。

未重复真实授权或云端识别，未运行未使用能力的上游测试；前端、本机文档排版及未变化算法沿用已有验证。上传policy、Undici连接、BL请求/轮询和外层进程时限保持各自原有边界，本次不宣称解决现场网络可达性。当前没有新的业务消费者要求增加流程、校验或重试。
