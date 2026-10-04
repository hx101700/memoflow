# UML 设计视图

本页描述第一阶段 asr-transcription Skill 的实际对象、调用和状态。第二阶段会议纪要与反馈学习尚未实现，不在图中虚构服务。

核对日期：2026-10-04。Python 图中 application、utils 等位置相对于 skills/asr-transcription/scripts/asr_runtime/；frontend 路径相对于仓库根。函数模块使用生命线，具有生命周期的 Session、Runtime、PathPicker 使用对象；状态图描述协议中的状态字符串。

当前协议区分编辑会话与执行任务：网页填写和预览不产生 job_id，用户发送含 session_id 的确认消息后才交接。预览展示登记、返回修改、两小时期限及一次结束通知见图 03、07；交接后的认证与执行见图 04、05。持久回执使相同会话恢复同一个任务，网页服务结束不影响执行。

图 01A、03、07 还描述关闭与下次开页回收：Session 结束后等请求线程，再清理磁盘；强制退出的旧会话按 PID 与原截止时间回收，保留任务和结果。图 01C 的连接记录给出归属依据，图 04 说明 Key 先在会话目录暂存再替换正式文件。

图 01B 区分数组中的热词单元格、前端稳定行键和显示序号；导入回执只含数组和读取说明，内容问题由预览校验产生。图 01C 区分预览设置、已授权配置、交接回执与执行结果。图 02 描述依赖安装，图 06、08 描述本地重导和执行记录失败，这些职责没有迁移到编辑会话。

源稿为 Mermaid，PNG 供直接阅读。图和文档保留在开发仓库；发行包只交付运行资源、参考资料和最新版双语 README。图稿及实际渲染验证见 [ACCEPTANCE](ACCEPTANCE.md)。

| 视图 | 图像 | 可编辑源稿 |
| --- | --- | --- |
| 01A 对象职责与依赖 | [查看](uml/01-classes.png) | [源码](uml/01-classes.mmd) |
| 01B 共享数据与进程契约 | [查看](uml/01b-data.png) | [源码](uml/01b-data.mmd) |
| 01C 确认配置与交付回执 | [查看](uml/01c-protocol.png) | [源码](uml/01c-protocol.mmd) |
| 02 准备工作目录 | [查看](uml/02-install.png) | [源码](uml/02-install.mmd) |
| 03 本机配置 | [查看](uml/03-configure.png) | [源码](uml/03-configure.mmd) |
| 04 凭据来源与登录 | [查看](uml/04-auth.png) | [源码](uml/04-auth.mmd) |
| 05 转写与交付 | [查看](uml/05-transcribe.png) | [源码](uml/05-transcribe.mmd) |
| 06 重新导出与状态查询 | [查看](uml/06-export.png) | [源码](uml/06-export.mmd) |
| 07 本地状态 | [查看](uml/07-state.png) | [源码](uml/07-state.mmd) |
| 08 记录保存失败 | [查看](uml/08-failure.png) | [源码](uml/08-failure.mmd) |

## 01A 对象职责与依赖

![对象职责与依赖](uml/01-classes.png)

## 01B 共享数据与进程契约

![共享数据与进程契约](uml/01b-data.png)

## 01C 确认配置与交付回执

![确认配置与交付回执](uml/01c-protocol.png)

## 02 准备工作目录

![Skill 与工作目录环境准备时序图](uml/02-install.png)

## 03 本机配置

![本机配置时序图](uml/03-configure.png)

## 04 凭据来源与登录

![凭据来源与登录时序图](uml/04-auth.png)

## 05 转写与交付

![转写与交付时序图](uml/05-transcribe.png)

## 06 重新导出与状态查询

![重新导出与状态查询时序图](uml/06-export.png)

## 07 本地状态

![本地状态图](uml/07-state.png)

## 08 记录保存失败

![记录保存失败时序图](uml/08-failure.png)
