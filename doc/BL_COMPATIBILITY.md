# 百炼 CLI 2.8.4 适配与复用审查

核对日期：2026-11-08。本轮比较官方2.7.2→2.8.4，在dev适配，项目版本仍为0.1.4，正式Release保持。上次审查与11月3日网络环境修复见[7034dc0时的记录](https://github.com/hx101700/memoflow/blob/7034dc0/doc/BL_COMPATIBILITY.md)。

## 固定来源及完整性

`git ls-remote --tags https://github.com/modelstudioai/cli.git 'v2.7.*' 'v2.8.*'` 取得以下 tag 身份。区间 `(2.7.2, 2.8.4]` 只有五个版本，官方中英 CHANGELOG 与逐版 Release 正文一致，共22条：12 + 4 + 1 + 3 + 2。

| 版本 | 日期 | 官方提交 |
| --- | --- | --- |
| 2.7.2（基线） | 2026-10-30 | `e66e686fa54ff7dbd948509c41312c638ea8d935` |
| 2.8.0 | 2026-11-03 | `5b81e93bdfa38669483361decd4a79b1799bf1e2` |
| 2.8.1 | 2026-11-04 | `e40504f071a9045efc2461637fbc1550672f4fc1` |
| 2.8.2 | 2026-11-04 | `21a17ab9f09e1153c47211ee040f27332a444463` |
| 2.8.3 | 2026-11-06 | `2285dc10906aa54ef51845c986e5daf42498f57d` |
| 2.8.4 | 2026-11-06 | `cadc301d078f0fd1f2c56f7bf94f32c55bbb055d` |

官方资料：[固定提交中文CHANGELOG](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/CHANGELOG.zh.md)、[英文CHANGELOG](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/CHANGELOG.md)、[2.8.0](https://github.com/modelstudioai/cli/releases/tag/v2.8.0)、[2.8.1](https://github.com/modelstudioai/cli/releases/tag/v2.8.1)、[2.8.2](https://github.com/modelstudioai/cli/releases/tag/v2.8.2)、[2.8.3](https://github.com/modelstudioai/cli/releases/tag/v2.8.3)、[2.8.4](https://github.com/modelstudioai/cli/releases/tag/v2.8.4)。

官方Release、CHANGELOG和源码证据缓存在被忽略的.runtime目录。源码归档已取得；23个消费文件逐字匹配归档成员，原始提交身份由tag核对。

## 完整变化及 MemoFlow 影响

| # | 版本 | 官方变化 | 影响、关联功能与处理决定 |
| --- | --- | --- | --- |
| 1 | 2.8.0 | 支持 `aliyun bl`；帮助、示例、恢复指引和结构化命令适配入口 | **当前无影响**。MemoFlow 直接启动私有 Node 与 `bailian-cli` 入口；不依赖 Aliyun CLI、入口重写或其输出前缀，继续原入口。|
| 2 | 2.8.0 | 新增 `BAILIAN_ACCESS_KEY_ID`、`BAILIAN_ACCESS_KEY_SECRET`、可选 `BAILIAN_SECURITY_TOKEN`，Console token缺失/过期时可用AK/SK自动获取 | **直接影响凭据隔离，后续鉴权候选**。MemoFlow已将新增三变量加入现有隔离集合，维持当前工作区模型Key与官方浏览器授权方式；不自动接入新的AK/SK授权。|
| 3 | 2.8.0 | `cmodel base-models/import/get/list/watch/delete`；OSS导入自定义模型、基础模型查询、导入任务跟踪及模型查询/删除；导入API仅北京 | **后续能力候选，当前不接入**。它管理模型资产及训练部署前置资源，不能替代当前固定公共ASR模型、本地录音临时上传或三格式交付；不因同为OSS或北京而混用。|
| 4 | 2.8.0 | JSON输出完整业务结果，warning/debug/error以JSONL单独写stderr | **直接影响**。识别继续读取 `--out` 原始JSON，状态查询继续解析stdout JSON。末尾错误仍为单行根 `error` 对象；需验证前序warning/debug不会遮蔽错误。继续复用官方输出分离，stdout新封装与原始结果文件分别处理。|
| 5 | 2.8.0 | quiet只隐藏进度和过程信息，保留结果、warning/error；支持 `DASHSCOPE_QUIET=1` | **直接影响**。保留显式quiet与输出格式；固定北京URL配合env/config Key的来源warning现在即使quiet也写stderr，旧文档“quiet即可隐藏来源告警”已失效。现有流程不依赖quiet截取ID/路径，无需新解析层。|
| 6 | 2.8.0 | AK/SK优先级为参数→百炼环境变量→百炼配置→阿里云环境变量 | **直接影响隔离依据**。与第2项一并清理新增环境凭据。当前模型API Key仍按原模型鉴权链解析，不能把AK/SK优先级变化误写成模型Key优先级变化。|
| 7 | 2.8.0 | 模型推荐关闭思考模式，保留 `--no-thinking` 兼容 | **当前无影响，后续选型候选**。固定ASR模型来自项目约束，不经过advisor；无需添加推荐或更改模型。|
| 8 | 2.8.0 | 输出格式校验：交互式浏览器登录、本地UI及Pipeline事件流要求text；流式语音合成JSON须 `--out` | **直接影响浏览器登录**。现有 `auth login --console --output json` 在请求前必然报USAGE，已改为text；后续 `auth status` 保持JSON。登录text错误不再是JSON，文本登录按官方退出码解释，原始stderr保留在进程内。其余UI/Pipeline/流式TTS不在本地表单→单次文件识别链路，当前不接入。|
| 9 | 2.8.0 | ASR JSON保留完整响应、转写结果，空结果仍返回任务信息 | **直接影响，但文件交付契约保持**。异步stdout为 `{...result, transcriptions: allTransData}`；`--out`仍保存单个转写对象或数组。`results.length===0`分支仍提前return且不写out，不得将任务成功或stdout回执视为 `documents_ready`。维持实际文件/文档交付检查。|
| 10 | 2.8.0 | Managed Agent SDK警告在quiet与JSON中保留 | **当前无影响**。MemoFlow在Codex里调用文件识别命令，不创建或调用BL Managed Agent会话；SDK警告处理不能替代本机网页诊断，当前不新增SDK。|
| 11 | 2.8.0 | 使用版本检查缓存时仍显示更新通知 | **当前无影响**。MemoFlow显式 `NO_UPDATE_NOTIFIER=1`，目标middleware仍在检查前直接跳过；版本继续由项目锁与更新流程管理，无需额外抑制器。|
| 12 | 2.8.0 | 避免重复错误；完善模型推荐、精调费用查询请求诊断 | **共享错误输出直接影响，特定业务当前无影响**。复用统一reporter与已有脱敏逻辑；JSON错误结构和登录text错误须分别验证。Advisor/费用查询不参与当前任务，不引入本地请求诊断替代实现。|
| 13 | 2.8.1 | 新增Linux ARM64 glibc二进制安装包及更新支持 | **当前无影响**。MemoFlow只支持Windows x64，随包提供官方Windows私有运行时并使用npm包，不扩大平台或修改运行时归档清单。|
| 14 | 2.8.1 | 异步并发图片生成/编辑保留全部图片，兼容异构任务响应格式 | **当前无影响**。MemoFlow处理单个录音的ASR结果，不解析图片任务或并发图片集合；该修复不能证明ASR多结果行为有变化，不添加图片功能。|
| 15 | 2.8.1 | Chat Completions流提前结束不再误报成功；结构化输出保留完整tool_calls及finish_reason | **后续纪要能力候选，当前无影响**。当前文件ASR使用上传/异步轮询/下载链路，不消费Chat流；后续模型纪要接入时可复用，不能替代当前文件交付完成判定。|
| 16 | 2.8.1 | 遥测请求不再拖延退出，遥测初始化失败保留排队事件 | **共享运行层已获得修复，当前遥测关闭**。目标loader仍以 `DO_NOT_TRACK=1` 强制telemetry=false，tracker先判断后直接执行命令。保留关闭开关与已有进程等待，不新增退出补丁或宣称真实网络速度提升。|
| 17 | 2.8.2 | 完善CLI使用统计 | **当前无新采集影响**。同第16项，遥测关闭。源码累计变化包含命令前缀等事件身份；这些不构成ASR功能，也不能将其等同于监控/日志业务命令或GitHub下载数。|
| 18 | 2.8.3 | `search web`新增模型搜索且默认使用 `--mode model` | **后续参考资料检索候选**。当前仅转写用户录音，未请求联网补充。新默认以Chat Completions+enable_search返回单个content.text，MCP模式返回pages；若未来使用需明确结果契约，不直接当网页列表或ASR上下文。|
| 19 | 2.8.3 | `text chat`新增 `enable_search` 内置联网搜索 | **后续纪要核实能力候选**。它可能为后续纪要引入外部资料，不替代录音转写或用户确认上下文；本轮不启用。|
| 20 | 2.8.3 | Profile按搜索 `model` / `mcp` 模式选对应凭据 | **鉴权共享路径已核对，当前无变化**。`search web`动态authCapability选择 `text.chat` 或 `search.web`。MemoFlow显式 `--config default`，识别还显式 `--base-url`，目标loader该分支不触发Profile fallback；保持既有工作区隔离，不加Profile兼容层。|
| 21 | 2.8.4 | `finetune params`查询训练超参，支持training-type/param-type/mtu-spec-code筛选与modality/reasoning-mode动态训练选项 | **后续训练能力候选，当前无影响**。当前使用公共ASR模型，无训练任务或超参消费者；不能替代词表/上下文校验。未来如做模型训练应直接复用官方查询。|
| 22 | 2.8.4 | `finetune metrics`查询训练指标，支持page/page-size显式分页 | **后续训练评估候选，当前无影响**。当前交付的是转写文档，未创建微调任务；该指标不是ASR置信度、转写质量验证或产品反馈学习，不新增指标采集。|

## 关键源码核对

- [auth/login.ts](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/packages/commands/src/commands/auth/login.ts)：浏览器分支在 `settings.output === "json" && !flags.tokenStdin` 时抛USAGE。dry-run先return，因此仅跑dry-run不能证明实际浏览器参数兼容。
- [auth/resolver.ts](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/packages/core/src/auth/resolver.ts)：新增百炼AK/SK环境变量优先于配置；模型Key仍为flag→DASHSCOPE_API_KEY→config。
- [output/reporter.ts](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/packages/runtime/src/output/reporter.ts)：结果仅stdout，warning/error始终保留，JSON错误单行，text错误含Error/Hint/Status/Code/Request ID/Caused by/Exit code（可本地化）。
- [speech/recognize.ts](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/packages/commands/src/commands/speech/recognize.ts)：异步stdout封装扩展，out结构与无结果提前返回保持。直接复用CLI上传、提交、轮询和下载；不新增补写结果或重试。
- [config/loader.ts](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/packages/core/src/config/loader.ts)：`DO_NOT_TRACK=1`强制telemetry=false；API连接显式覆盖或default Profile不走凭据fallback。
- [search/web.ts](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/packages/commands/src/commands/search/web.ts)：mode不同对应不同authCapability；model模式不是pages列表。
- [middleware.ts](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/packages/runtime/src/middleware.ts)：来源不一致warning不再受quiet限制；NO_UPDATE_NOTIFIER仍在版本检查之前跳过。
- [telemetry/tracker.ts](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/packages/core/src/telemetry/tracker.ts)、[sink.ts](https://github.com/modelstudioai/cli/blob/cadc301d078f0fd1f2c56f7bf94f32c55bbb055d/packages/core/src/telemetry/sink.ts)：关闭遥测直接执行fn，不调用localSink/remoteSink；目标发送有AbortController及1秒预算。

MemoFlow调用方为 `utils/bailian.py`、`utils/environment.py`；验证入口与实际结果见[ACCEPTANCE](ACCEPTANCE.md)。

## 实现取舍与保留边界

- 浏览器登录使用原生text输出；成功后auth status继续JSON。text失败按官方退出码解释，JSON命令继续读取末尾JSONL错误并脱敏；没有新增文本格式解析器或转发授权链接。
- 识别stdout由BL输出完整任务信息，但MemoFlow继续丢弃识别stdout并读取`--out`原始JSON。输出数据未进入对话，任务恢复入口保持既有范围。
- 新增三项BAILIAN环境凭据与ALIBABA_CLOUD凭据同属工作区隔离范围；代理、证书仍继承，交给官方网络栈。没有恢复宽泛白名单。
- upload、transport、asr-routes、vocabulary-input、local-server、proxy与2.7.2逐字一致；HTTP和轮询的变化是诊断输出接入，上传及等待预算保持。原生连接时限10秒、上传policy15秒、上传和轮询各3600秒、Python总等待7500秒分别约束不同阶段。
- 新版未替代本机热词行级诊断、上下文规则、Windows命令长度检查、声道准备或三种校对稿排版。复用既有用例，保持一次执行、失败不重传；没有增加模型路由、网络客户端或重复轮询。
- config set清空当前Profile模型Key仍为原生公开命令，只是quiet也输出操作结果。bootstrap检查实际安装，doctor用于主动诊断，更新器只替换Skill文件；版本升级复用现有依赖准备方式。

实际新目录安装、测试和未覆盖范围见[ACCEPTANCE](ACCEPTANCE.md)，当前工作检查点见[STATUS](STATUS.md)。
