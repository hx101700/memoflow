# 百炼 CLI 2.7.2 适配与复用审查

核对日期：2026-11-01。比较官方 **2.5.1 → 2.7.2**，聚焦本项目实际消费的调用路径。本次适配用于MemoFlow v0.1.4，固定2.7.2；v0.1.3的2.5.1依赖及历史验收保留原有事实。上次比较见[4876193时的记录](https://github.com/hx101700/memoflow/blob/4876193/doc/BL_COMPATIBILITY.md)。

## 固定来源

| 版本 | 官方源码提交 | 用途 |
| --- | --- | --- |
| 2.5.1 | [3c8031f](https://github.com/modelstudioai/cli/tree/3c8031f4d994c30820eb4d145d9404ba4a0acd39) | 本次升级前版本 |
| 2.7.2 | [e66e686](https://github.com/modelstudioai/cli/tree/e66e686fa54ff7dbd948509c41312c638ea8d935) | 本次目标版本 |

[官方CHANGELOG](https://github.com/modelstudioai/cli/blob/e66e686fa54ff7dbd948509c41312c638ea8d935/CHANGELOG.zh.md)描述中间版本的新增功能；下面按固定源码与实际调用方判断是否影响MemoFlow。npm清单和锁通过原生npm更新，CLI/core/commands/runtime均固定官方2.7.2。

## 中间版本的适用范围

本次比较覆盖2.5.1→2.7.2的累计源码差异，不只阅读2.7.2的新增项。两个中间版本的范围明确如下：

| 版本 | 相关变化 | 对当前流程的判断 |
| --- | --- | --- |
| [2.7.0](https://github.com/modelstudioai/cli/releases/tag/v2.7.0) | ParseX解析/字段抽取、Key与Base URL来源诊断、MaaS工作空间Key登录及验证错误修复 | ParseX作为后续资料处理候选；来源诊断与现有固定北京配置不冲突。网页Key保存.env、控制台回调保存Key不经过auth login --api-key在线验证，不能把该修复称作当前网页的新校验能力 |
| [2.6.2](https://github.com/modelstudioai/cli/releases/tag/v2.6.2) | alert/monitor/log默认JSON的破坏性变更，以及这些命令的工作空间身份、日志解析/计数、过滤和dry-run修复 | 当前项目不调用这三组业务命令。已有识别、登录、状态查询显式使用--output json，转写交付读取--out文件；没有依赖受影响的文本输出或日志计数，因此不新增适配层 |

2.6.2的默认输出与工作空间逻辑集中在`commands/shared/telemetry.ts`的defineTelemetryCommand及关联命令中，属于百炼监控/日志业务，和CLI使用统计开关DO_NOT_TRACK、GitHub附件下载计数分别是不同机制。这里是源码适用范围核对；本机回归覆盖项目实际调用链，不声称验收了上游全部新增功能。

## 版本差异与处理

| 消费路径 | 源码差异 | 本项目处理 |
| --- | --- | --- |
| speech/recognize.ts | 新增auto/MCP分支；具体模型的原REST参数、轮询和转写JSON形状保持，最终下载改用httpTransport | 继续显式传固定Qwen模型，复用完整命令；不新增模型路由或轮询 |
| client/asr-routes.ts、speech/vocabulary-input.ts | 两版内容一致 | 热词、上下文、语言和说话人映射保持；本地表格诊断仍有独立消费者 |
| files/upload.ts、Client.uploadFile | 上传policy根据当前base URL选端点；支持北京/新加坡，官方Token Plan和不支持地域由CLI拒绝；policy失败透传HTTP/API码/request ID | 固定北京URL继续生效；直接使用官方上传及结构化错误，删除测试中的北京policy URL重写 |
| client/transport.ts、http.ts | Node使用包内undici.fetch；改进代理/dispatcher及Node26兼容；嵌套业务错误、非JSON错误正文和request ID透传更完整 | 无需本地HTTP客户端；测试改为拦截真实Undici入口，并限制网络到本机服务 |
| auth/login、login-console、status、store、refresh-token、shared/local-server | 两版内容一致 | 官方浏览器授权、回调、凭据保存和原登录进程等待保持 |
| auth/login-api-key.ts | 修正MaaS工作空间Key验证，保留网络和服务错误 | 当前网页仅保存.env；控制台回调直接persistApiKey，不经过这套在线Key校验，不能宣称该改动替代本机Key保存 |
| auth/resolver、config show及runtime middleware | 增加Key/base URL来源诊断；来源告警只在非quiet时输出 | 本项目显式北京URL配合env/config Key是预期组合，已有quiet即可；无需把Key移入参数 |
| runtime/args.ts与准备机制 | 新增--introspect及部分命令prepare机制；recognize没有prepare/risk声明 | 无需第二次业务确认；继续现有参数数组与会话交接 |
| errors/codes.ts、runtime/error-handler | 新增INTERRUPTED=130枚举，重构统一错误规范化；base/api错误类型不变 | 字典补130，保留现有末尾根JSON解析及脱敏；不把中断解释为云端取消 |
| 后台版本检查 | NO_UPDATE_NOTIFIER仍有效，DO_NOT_TRACK仍控制遥测 | 继续由项目锁维护版本，业务和开发探针共用原环境设置 |

逐文件对照覆盖20个当前消费文件；登录相关文件和基础错误类型的一致性通过内容比较核对，变化文件逐段阅读。源码缓存与比较清单在.runtime，发行包不包含它们；结果不以缓存存在替代官方提交身份。

## 新功能能否替代现有能力

- **auto模型路由**：识别命令仅在model精确为auto时进入MCP，现有显式固定模型已排除该分支。该分支拒绝语言、说话人数、热词、上下文等参数，仅接受公网HTTP(S)媒体URL，out保存string数组；与当前本地录音、固定模型、增强和转写JSON契约不同。无需新增本地禁止逻辑。
- **ParseX解析/抽取**：提供另一套文档/音视频解析及按Schema抽取接口，支持Markdown结果。它没有替代当前指定模型、即时词典和Word/Excel/Markdown校对稿契约；可作为第二阶段参考资料处理的候选，当前不接入。
- **--introspect**：提供命令元信息，可辅助开发核对参数；不执行模型专属词表规则，也不提供网页单元格错误定位。
- **临时上传与错误透传**：已经直接复用新版官方实现，是本轮实际获得的能力改进。生产代码没有需要删除的自写上传器、刷新器或浏览器适配；删除的是已被官方base URL行为取代的测试重写。
- **本机规则与交付**：CLI仍只校验词典基础形状和有限权重数值，没有本产品的行级诊断、词条/超级词上限、上下文长度、Windows完整命令预检或三格式排版。继续由现有用例负责。

主要源码：[recognize](https://github.com/modelstudioai/cli/blob/e66e686fa54ff7dbd948509c41312c638ea8d935/packages/commands/src/commands/speech/recognize.ts)、[auto约束](https://github.com/modelstudioai/cli/blob/e66e686fa54ff7dbd948509c41312c638ea8d935/packages/commands/src/commands/shared/aigc-mcp.ts)、[ParseX](https://github.com/modelstudioai/cli/blob/e66e686fa54ff7dbd948509c41312c638ea8d935/packages/commands/src/commands/parsex/parse-submit.ts)、[上传](https://github.com/modelstudioai/cli/blob/e66e686fa54ff7dbd948509c41312c638ea8d935/packages/core/src/files/upload.ts)、[HTTP](https://github.com/modelstudioai/cli/blob/e66e686fa54ff7dbd948509c41312c638ea8d935/packages/core/src/client/http.ts)、[transport](https://github.com/modelstudioai/cli/blob/e66e686fa54ff7dbd948509c41312c638ea8d935/packages/core/src/client/transport.ts)、[错误码](https://github.com/modelstudioai/cli/blob/e66e686fa54ff7dbd948509c41312c638ea8d935/packages/core/src/errors/codes.ts)。

## 仍保留的边界

固定模型、北京、临时OSS、每任务一次执行与三格式交付保持。上传policy仍为15秒，文件仍整份读入内存；上传及轮询各使用项目传入的3600秒，JSON请求期限覆盖响应头和正文。最终转写JSON改用httpTransport.fetch，仍未设置独立BL下载期限；这不等于底层传输完全没有期限。Python整体等待上限保持7500秒。

2.7.2的控制台登录仍使用BL原生15分钟会话；在线模型Key有效性由实际识别调用判断。130仅描述进程中断，固定识别路径没有新增可靠的云端取消/恢复入口。--vocabulary仍只接受JSON文本，Windows命令长度检查仍有消费者。

新工作目录实际安装、本机合约与完整回归结果见[ACCEPTANCE](ACCEPTANCE.md)。本机模拟不代表真实浏览器授权或云端识别验收。v0.1.4发布状态见STATUS；保留v0.1.3附件，用户已安装副本通过版本更新获取。
