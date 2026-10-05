# MemoFlow 文档中心

## 使用 Skill

| 文档 | 用途 |
| --- | --- |
| [README 中文](../README.md) / [English](../README.en.md) | 功能介绍、安装与首次使用 |
| [HELP](HELP.md) | 使用资料入口 |
| [usage.md](../skills/asr-transcription/references/usage.md) | 环境准备、认证、网页操作与重导 |
| [errors.md](../skills/asr-transcription/references/errors.md) | 常见问题处理及状态含义 |
| [model.md](../skills/asr-transcription/references/model.md) | 固定 BL/API 版本与官方参数依据 |

## 开发与维护

接续时先读[协作规则](../AGENTS.md)和[STATUS](STATUS.md)，再检查 Git 工作区及相关源码。Skill 的使用指令在 [SKILL.md](../skills/asr-transcription/SKILL.md)，与仓库维护指令分开。

| 文档 | 用途 |
| --- | --- |
| [STATUS](STATUS.md) | 当前工作、验证与交付状态 |
| [DEVELOPMENT](DEVELOPMENT.md) | 资源边界、模块职责、任务协议与设计取舍 |
| [REVIEW](REVIEW.md) | 逐文件审查范围与职责、写入边界结论 |
| [UML](UML.md) | 与实现对应的对象、时序及状态视图 |
| [ACCEPTANCE](ACCEPTANCE.md) | 已执行的验证和未覆盖场景 |
| [ISSUES](ISSUES.md) | 当前不足、运行限制及处理方法 |
| [DEVLOG](DEVLOG.md) | 影响当前实现的重要决策 |
| [发布说明：中文](../release/NOTES.md) / [English](../release/NOTES.en.md) | 供发布时使用的用户说明 |
| [开发预览：中文](../release/DEV.md) / [English](../release/DEV.en.md) | 独立运行环境与完整／轻量包下载说明 |

详细使用资料随 Skill 放在 `references/`，最新版双语 README 从仓库根直接入包；开发文档、UML 和测试保留在仓库。每份资料维护一个职责，避免复制同一操作说明。实际实现和运行证据优先；未完成的验证明确标注。写作参考 [Google 开发者文档指南](https://developers.google.com/style/highlights)。
