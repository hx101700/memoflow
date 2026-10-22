# 百炼 CLI 2.4.0 适配说明

核对日期：2026-10-19。本文比较官方 **v2.1.0 → v2.4.0**，聚焦 MemoFlow 实际使用的安装、认证、文件上传和语音识别能力。当前运行依赖固定为官方2.4.0；2.1.0仅作为差异对照。

## 官方版本与源码

| 版本 | 官方源码 | 对照用途 |
| --- | --- | --- |
| v2.1.0 | [fc080016469f33ce6726ae997d0ff6428c19aa49](https://github.com/modelstudioai/cli/tree/fc080016469f33ce6726ae997d0ff6428c19aa49) | 原始固定上传时限与Windows打开方式 |
| v2.4.0 | [3638180f48b8fb1c7f99d5db91d3882d021710e5](https://github.com/modelstudioai/cli/tree/3638180f48b8fb1c7f99d5db91d3882d021710e5) | 当前实现与依赖依据 |

变更范围依据官方[发布记录](https://github.com/modelstudioai/cli/blob/3638180f48b8fb1c7f99d5db91d3882d021710e5/CHANGELOG.md)，细节以对应源码为准。

## 与转写直接相关的变化

| 能力 | 官方2.1.0 | 官方2.4.0 | MemoFlow处理 |
| --- | --- | --- | --- |
| 临时OSS上传期限 | `Client.uploadFile()`未传有效timeout，上传独立固定120秒 | `Client.uploadFile()`经`resolveFileUrl()`、`UploadOptions`将`settings.timeout`传入`uploadToOSS()`，计时器使用秒数×1000 | 直接使用官方`--timeout 3600`，删除本地core修订归档、override和构建patch |
| Windows授权页打开 | `cmd/start`没有完整保护URL，`&needapikey=true`可能被命令解释器拆开 | `buildOpenInvocation()`引用完整目标，使用`cmd /d /v:off /s /c`及`windowsVerbatimArguments` | 直接由官方BL打开默认浏览器，删除Node预加载和Python链接转交线程 |
| core请求期限 | CLI等待较长时，底层传输期限仍可能先结束请求 | JSON请求以配置期限覆盖响应头及JSON正文；Node请求关闭更短的undici headers/body期限。原始/流式响应采用正文空闲计时并释放连接 | 提交和查询继续使用官方客户端，不增加Python超时拦截 |
| 参数解析 | 旧解析器未统一拒绝全部未知参数 | 只接受声明参数，拒绝未知、重复标量和无效数值；全局参数可位于完整命令路径前后 | 沿用已声明参数；上下文继续作为单个`--context=原文`参数传递 |
| 登录与状态提示 | 本机状态显示凭据类型 | 缺少模型API Key时，状态或仅保存控制台会话的登录结果会附配置提示 | 继续读取`api_key`判断模型凭据是否存在，`authenticated=true`不作为模型Key可用证明 |

对应源码：上传[client.ts](https://github.com/modelstudioai/cli/blob/3638180f48b8fb1c7f99d5db91d3882d021710e5/packages/core/src/client/client.ts)与[upload.ts](https://github.com/modelstudioai/cli/blob/3638180f48b8fb1c7f99d5db91d3882d021710e5/packages/core/src/files/upload.ts)、[Windows打开请求](https://github.com/modelstudioai/cli/blob/3638180f48b8fb1c7f99d5db91d3882d021710e5/packages/commands/src/commands/shared/local-server.ts)、[HTTP请求](https://github.com/modelstudioai/cli/blob/3638180f48b8fb1c7f99d5db91d3882d021710e5/packages/core/src/client/http.ts)、[参数解析](https://github.com/modelstudioai/cli/blob/3638180f48b8fb1c7f99d5db91d3882d021710e5/packages/runtime/src/args.ts)、[auth status](https://github.com/modelstudioai/cli/blob/3638180f48b8fb1c7f99d5db91d3882d021710e5/packages/commands/src/commands/auth/status.ts)。

官方变更记录在2.2.2及2.3.0均列出上传使用`--timeout`；2.3.1列出较长请求被300秒响应头期限提前中断的修复，2.3.3进一步列出请求期限、Windows登录URL及缺少模型Key的提示修复。这里按最终2.4.0源码核对行为，不仅按发布说明推断。

## 保持不变的调用边界

两版本的`speech/recognize.ts`一致，当前继续使用同一公开转写入口：本地文件上传、异步识别提交、轮询、结果下载和`--out`保存由BL完成。固定模型、北京地域、即时热词、上下文增强、说话人区分和文件输出映射保持原样。

- `--vocabulary`仍接收JSON文本，`--context`仍接收文本，未提供即时词典文件入口。Windows完整命令长度检查仍有实际消费者。
- 语音命令的增强帮助仍提到Qwen 3.0；当前Qwen 3.1能力依据模型官方API，而非据帮助文字限制模型。
- 取得上传凭证仍固定15秒；临时OSS上传仍将整个文件读入内存。2.4.0没有把此处改为流式上传。
- 识别提交和查询使用core JSON请求封装；最终转写JSON下载仍是独立原生`fetch()`，没有BL单独配置的下载期限。
- `auth status`仍读取本机凭据状态，不能证明模型权限或在线有效性。两种认证方式均使用模型API Key执行ASR。
- 完整模式仍未稳定提供可用于恢复的云端`task_id`。退出0仍须检查原始JSON，失败不自动重新上传。

源码：[recognize.ts](https://github.com/modelstudioai/cli/blob/3638180f48b8fb1c7f99d5db91d3882d021710e5/packages/commands/src/commands/speech/recognize.ts)、[login-console.ts](https://github.com/modelstudioai/cli/blob/3638180f48b8fb1c7f99d5db91d3882d021710e5/packages/commands/src/commands/auth/login-console.ts)、[凭据解析](https://github.com/modelstudioai/cli/blob/3638180f48b8fb1c7f99d5db91d3882d021710e5/packages/core/src/auth/resolver.ts)。

2.4.0新增的Managed Agent记忆、Workspace Webhooks、Agent资源绑定和运行环境变量属于其它命令域，不进入当前转写Skill。当前业务无需因此引入记忆服务或Agent编排。

## 当前安装与验证边界

`scripts/bailian/package.json`及锁文件只安装官方2.4.0。现有工作目录检测到其他版本时停止并提示，仅重新准备其中的`.asr-transcription/.tools/bailian`；Python、Node、凭据、任务及结果位于独立位置，继续保留。具体操作见[使用指南](../skills/asr-transcription/references/usage.md)与[错误说明](../skills/asr-transcription/references/errors.md#常见问题处理)。

依赖环境通过`NO_UPDATE_NOTIFIER=1`关闭官方后台版本查询，当前固定版本由项目更新维护。授权页、上传和请求期限均直接使用官方实现。

官方2.4.0适配随MemoFlow v0.1.2发布，已发布v0.1.0/v0.1.1的标签、附件与说明保留。实际验证结果独立记录在[ACCEPTANCE](ACCEPTANCE.md)；源码比较不替代真实用户桌面、网络或云端识别验收。
