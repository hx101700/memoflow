# MemoFlow 文档索引

## 接续当前工作

按 [AGENTS](../AGENTS.md) → [STATUS](STATUS.md) 恢复任务，再核对 Git 分支、工作区差异和近期提交。STATUS 负责当前检查点；需要验证时到 [DEVELOPMENT](DEVELOPMENT.md#开发与验证) 取得环境前提与命令。原对话或被忽略的本机日志不是接续开发的必要输入。

| 资料 | 唯一职责 | 何时阅读／更新 |
| --- | --- | --- |
| [AGENTS 中文](../AGENTS.md)／[English](../AGENTS.en.md) | 长期工程要求与用户已确定的边界 | 接续时读；约束变化才改 |
| [STATUS](STATUS.md) | 当前目标、完成项、下一步、授权与验证范围 | 每次实质进展更新当前检查点 |
| [DEVELOPMENT](DEVELOPMENT.md) | 架构、文件边界、协议、设计理由与开发命令 | 改实现前按主题读，机制变化时改 |
| [UML](UML.md) | 对象、时序、状态和可复现图稿 | 调用或协议变化时同步源码与图片 |
| [ISSUES](ISSUES.md) | 尚未解决的问题、证据与影响 | 发现问题或处理状态变化时改 |
| [REVIEW](REVIEW.md) | 最近一次审查的范围、发现与处理结果 | 审查时更新，不累积另一套长期规约 |
| [BL_COMPATIBILITY](BL_COMPATIBILITY.md) | 固定 BL 升级的源码差异和复用依据 | 调整 BL 版本或边界时读写 |
| [DEVLOG](DEVLOG.md) | 按日期保留重要变更及当时决定 | 重要进展追加，保留历史事实 |
| [ACCEPTANCE](ACCEPTANCE.md) | 按日期保留实际检查、前提及未覆盖范围 | 验证完成后追加；历史结果不代表本次通过 |

## 产品、操作与发行

| 资料 | 用途 |
| --- | --- |
| [README 中文](../README.md)／[English](../README.en.md) | 产品介绍、安装和使用；维护用户既有叙述与截图 |
| [HELP](HELP.md) | 用户帮助入口 |
| [SKILL](../skills/asr-transcription/SKILL.md) | Codex 的入口判断、执行顺序与跨回复衔接 |
| [usage](../skills/asr-transcription/references/usage.md) | 唯一的操作步骤与命令说明 |
| [errors](../skills/asr-transcription/references/errors.md) | 唯一的状态解释与故障恢复说明 |
| [model](../skills/asr-transcription/references/model.md) | 固定模型／CLI 能力、参数、限制及官方来源 |
| [CONTRIBUTING](../CONTRIBUTING.md)／[SUPPORT](../SUPPORT.md)／[CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md) | 贡献、反馈和社区参与规则 |
| [发布说明中文](../release/NOTES.md)／[English](../release/NOTES.en.md) | 当次发布的用户改进、下载、安装与更新 |
| [发布约定中文](../release/NEXT.md)／[English](../release/NEXT.en.md) | 后续发布说明的写法与版本边界 |

版本、依赖、文件列表以源码常量和相应清单为准。操作细节放 references，设计理由放 DEVELOPMENT，历史证据放 DEVLOG／ACCEPTANCE，通过链接引用，避免在多处复制。

发行包包含 Skill 运行资源、references 和从仓库根直接读取的最新版双语 README。开发文档、UML、测试、AGENTS、已安装环境及用户数据保留在包外，清单由 `scripts/build_zip.py` 管理。
