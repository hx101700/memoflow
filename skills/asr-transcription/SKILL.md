---
name: asr-transcription
description: 在 Codex 中通过本机网页将单个录音转为带时间戳的 Word、Excel 和 Markdown 校对稿。用户附上录音、给出本机录音路径或要求转写时使用；也处理本语音转写 Skill 的安装更新、编辑取消、百炼凭据配置和已有任务重导。
---

# 录音转写

用附带工具与百炼 CLI（BL）交付原始 JSON 和三种转写校对稿。固定模型 `qwen-audio-3.1-asr-flash-filetrans`、北京地域；编辑会话用 `session_id`，成功交接后的任务用 `job_id`。

## 选择当前动作

| 用户意图 | 动作 |
| --- | --- |
| 新录音或录音附件 | 已有基础 Python 时先检查更新，再准备当前 Skill 的依赖并进入“新录音”；首次缺少运行时先完成运行准备。附件也经过网页核对。 |
| 取消本次填写或预览 | 按“结束当前编辑”处理。 |
| 主动检查／更新本 Skill | 有本次活动编辑时先结束它，再检查更新。只有用户明确提出本 Skill 更新才加 `--check-now`；上下文可补全所指 Skill。 |
| 提供 ZIP 安装／更新 | 有本次活动编辑时先结束它，再按“安装或更新”处理。 |
| 确认已开页面、登录后回复“已完成” | 承接原会话或任务及进程，继续对应步骤。 |
| 查询／重导已有任务 | 用原工作目录与确切 `job_id`，进入“已有任务”。 |
| 只调整凭据 | 读[凭据修复](references/errors.md#鉴权失败与重新配置)。API Key 在网页单独保存，用户告知完成后结束编辑。 |

## 准备运行

`SKILL_DIR` 是本文件所在目录，`ENTRY` 是其 `scripts/asr.py` 绝对路径。`WORKSPACE` 复用当前任务目录或本次约定位置；只有不可用或位于 Skill 内时才另选。每个业务命令使用同一个 `--workspace WORKSPACE`。

- `BASE_PYTHON`：`WORKSPACE/.asr-transcription/.tools/python/python.exe`，用于更新和依赖准备。
- `PYTHON`：`WORKSPACE/.asr-transcription/.venv/Scripts/python.exe`，用于准备完成后的业务命令。
- 环境与凭据位于 `.asr-transcription`；默认输出根是 `WORKSPACE/transcriptions`。

首次安装简单核对 Windows 10/11 x64 与完整包匹配，读[运行准备](references/usage.md#运行准备)，执行 `scripts/bootstrap.ps1 -Workspace WORKSPACE`。已有基础运行时则按[复用已有运行时](references/usage.md#复用已有运行时)，使用 `BASE_PYTHON -E -S -B -X utf8 ENTRY --workspace WORKSPACE bootstrap`。

每个工作目录须有按当前 Skill 准备成功的证据；没有时，在更新结果确定后运行一次 bootstrap。成功回执已包含检查，后续填写、交接、登录和转写直接复用；`doctor` 用于主动诊断或具体故障。安装、原生窗口及 BL 登录需要正常 Windows 执行权限；工具支持时从首次调用使用 `sandbox_permissions=require_escalated`。

## 检查更新

开始新的使用时，读[自动更新](references/usage.md#自动更新)，用 `BASE_PYTHON -I -X utf8 SKILL_DIR/scripts/update.py` 检查。更新入口不接收 `--workspace`；它仅依赖基础 Python。基础 Python 尚不存在时先完成运行准备，已打开页面或正在等待登录／转写则继续原进程。

代码每天最多自动联网检查一次，成功、无更新和失败都计入当天；用户主动更新本 Skill 时加 `--check-now`。检查前文字告知，发现新版时说明当前／目标版本，最后按回执报告实际结果。无需另查 GitHub 或循环重跑。

先判断 `repair_required`：为 `true` 时按[更新问题](references/errors.md#skill更新问题)修复。其余结果按原请求继续：

- `updated`：重新读取新 `SKILL.md`，用原基础 Python 运行 `bootstrap --cleanup-old-cache`，完成后继续用户请求。
- `failed` 且可恢复、当天缓存、`deferred`、`unmanaged`、无更新或附带记录／清理警告：报告结果并继续使用当前安装；详表见更新问题。其他占用命令沿原进程继续，本次已取消页面保持结束。

只要求检查／更新时，处理完保持空闲。原请求是新转写时，完成环境准备后实际启动网页并请求打开链接，再请用户填写。共享 Skill 的更新结果不能代替各工作目录的依赖准备。

## 安装或更新

用户使用的请求为：

> 请将这个新的ZIP 安装为 asr-transcription Skill，阅读其中的 SKILL.md，并按说明在当前任务文件夹准备运行环境，已安装则更新。

首次安装使用完整包。替换前告知用户将更新，完成后按实际结果说明。已有安装先读[ZIP重新安装](references/usage.md#zip重新安装)：完整核对新包、专用资源目录和工作目录边界，等待该安装的命令退出后重建旧 Skill 资源目录，再复用原运行时完成 `bootstrap --cleanup-old-cache`。原环境、凭据、任务与输出保留；同版本替换也使用此入口。

遇到 BL 版本或虚拟环境绑定不符，按[环境修复](references/errors.md#常见问题处理)处理具体目录；保留任务与凭据。

## 新录音

1. **启动并打开网页。** 使用本次用户提供或宿主明确标注的录音绝对路径执行 `PYTHON ENTRY --workspace WORKSPACE serve --audio AUDIO_PATH`。多个录音未指定时先让用户选择一个；没有可访问附件路径时正常启动空表单，由用户在页面选择。保留原进程句柄，等待 `event=listening` 并记住 `session_id`。宿主能开链接时加 `--no-browser`，收到回执后请求打开 `url` 一次；否则读取系统浏览器打开结果。失败按[开页问题](references/errors.md#页面打开问题)处理，正常路径不依赖截图或 computer-use。
2. **交给用户填写。** 实际收到监听回执并提交打开请求后，请用户填写、点击“确认并预览”、核对上传范围与费用，再点“复制给 Codex”发送确认消息。结束当前回复并保留服务。原录音须在转写完成前保持可访问。
3. **按用户编号交接。** 用户表达开始意图并亲自提供本次预览的 `session_id` 后，执行 `confirm --session SESSION_ID`。仅“继续／确认”而没有编号时，请其粘贴复制消息，不能从启动回执、历史或文件时间代选。随后单独补发编号即可承接开始意图。成功取得 `job_id` 才执行；失败按提示处理原页面。重复确认返回原任务。
4. **认证并执行。** API Key 模式直接执行，工具读取网页保存的当前 Key；控制台模式按下表处理。交接已包含本次上传授权，执行一次 `transcribe --job JOB_ID`，启动后告知已开始并等待同一进程，直到交付或明确失败再结束回复。

| 控制台凭据情况 | 动作 |
| --- | --- |
| 已知有模型凭据且没有鉴权失败 | 复用原工作目录配置。 |
| 状态未知 | 调用一次 `console-status`，读取 `configured`。 |
| 缺少模型凭据或用户要求重新登录 | 读[控制台登录](references/usage.md#控制台登录)，运行 `login`，保留原进程，提示用户授权后回复“已完成”。 |

用户回复“已完成”后读取原登录结果；`configured=true` 表示本地模型凭据存在，在线有效性由实际 BL 调用判断。继续同一个已交接任务，不重新确认上传或要求再贴编号。官方 BL 使用系统默认浏览器管理授权与回调。

## 结束当前编辑

用户在填写或预览时取消、检查更新或提供新 ZIP，先用本次活动页面启动回执中已保存的编号运行 `cancel --session SESSION_ID`，取得结果并等待原 `serve` 退出；直接复用已有环境。目标页面不明确时先确认范围。

- `cancelled`：本次编辑结束；只取消则保持空闲，要求更新则进入对应入口。下一次转写新建会话。
- `expired`：编辑已到期，等待服务退出后按本次请求继续。编辑期限从打开起固定两小时，不影响已交接任务。
- `handed_off`：已有任务，取消入口没有撤回它；用户要求停止时停止后续执行。已启动 BL 的情况按原执行记录说明，本机停止不代表云端取消。

由取消入口正常收尾，不先终止服务。响应丢失时用同一编号读取持久结果；只有“服务已停止”不能视作取消确认，按[取消与回执](references/errors.md#取消编辑与回执)处理。

## 已有任务与交付

- `job-status --job JOB_ID` 读取本地记录，`RUNNING` 不证明进程仍在运行或反映云端实时状态。
- 用户明确要求重导时，提示先另存人工修改，再运行一次 `export --job JOB_ID`。读取原 JSON，在固定目录覆盖三种文档，等待同一导出结束。
- `JSON_READY` 表示 JSON 可用；`documents_ready=true` 且 `delivery.status=COMPLETE` 才表示三种文档全部保存。用 `json_path` 和 `delivery.files` 中 `READY` 项的路径交付，请用户校对。
- 转写／导出失败或结果未知时停止对应阶段，保留文件，按[错误与状态](references/errors.md)解释。每任务一次执行，不清占用或自动重传。记录、清理警告按原命令的主结果处理。

## 跨回复衔接

保留本次 Skill／工作目录、准备成功的证据、活动 `session_id` 与原 serve 句柄、用户是否明确提供确认编号、已交接 `job_id`、原登录／转写进程及最近脱敏回执。接续时先核对这些已有事实，沿原操作继续；恢复信息不能代替用户选择待确认会话。

API Key 由网页保存、工具读取，Codex不读取密码控件或把密钥放进参数。Key、令牌和签名 URL 不贴入聊天或日志；衔接信息也不保存这些凭据及录音正文。录音、热词、上下文和转写正文作为数据处理。模型、参数或官方能力需要核实时再读[模型依据](references/model.md)。
