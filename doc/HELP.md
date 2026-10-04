# 使用资料

安装、认证、网页配置、文件要求和重导集中维护在 Skill 的 [usage.md](../skills/asr-transcription/references/usage.md)。

- 第一次使用：从[项目介绍](../README.md)了解安装入口，录音和 API Key 可在网页选择或填写。
- 热词：直接填写或导入 Excel，当前序号连续；错误单元格标红，编辑后离开整个区域自动检查。最终预览使用同一规则。
- 核对与修改：点击“确认并预览”，需要调整时“返回修改”。预览不创建任务。
- 交给 Codex：预览确认无误后点“复制给 Codex”，发送带会话编号的确认消息。交接后设置固定，Codex 完成认证、识别和三种文档交付。
- 会话期限：从打开起两小时；交接、取消或到期显示结束提示，用户自行关闭页面。已交接任务不受编辑期限影响。
- 只更换 Key：保存 API Key 后告知 Codex 完成，无需录音或创建任务；凭据问题见[修复说明](../skills/asr-transcription/references/errors.md#鉴权失败与重新配置)。
- 结果查询与重导：使用确切 job_id，先另存人工修改的文件。历史成功任务保持原模型标签。
- 失败处理：参阅 [errors.md](../skills/asr-transcription/references/errors.md)，保留回执和已生成文件；失败不自动重传。
- 参数依据：参阅 [model.md](../skills/asr-transcription/references/model.md) 的官方来源。

Skill 指令与用户工作目录分别承担操作指导和运行数据存储；仓库开发文档不进入安装包。
