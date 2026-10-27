# UML 设计视图

图稿描述第一阶段 asr-transcription 的实际对象、调用与状态。第二阶段个性化纪要生成及反馈学习尚未实现，不在图中预设服务。

源码是实现与完整字段的权威。类图摘录关键字段；TypedDict 和 TypeScript interface 表示数据协议，函数模块使用生命线，Session、Runtime、PathPicker 表示实际对象。Python 路径相对于 `skills/asr-transcription/scripts/asr_runtime/`，前端路径相对于仓库根。

## 按问题选择图稿

| 视图 | 关注边界与对应实现 | 图像 / 源稿 |
| --- | --- | --- |
| 01A 对象职责与依赖 | `web.py`、`application/session.py`、Runtime、PathPicker 的生命周期 | [PNG](uml/01-classes.png) / [Mermaid](uml/01-classes.mmd) |
| 01B 共享数据与进程契约 | `models.py`、`frontend/types.ts`；音频、热词、双语诊断与转写结果 | [PNG](uml/01b-data.png) / [Mermaid](uml/01b-data.mmd) |
| 01C 确认配置与交付回执 | `models.py`、`session_files.py`、`job_files.py`；配置、交接、取消与执行结果 | [PNG](uml/01c-protocol.png) / [Mermaid](uml/01c-protocol.mmd) |
| 02 准备工作目录 | `bootstrap.ps1`、`asr.py`、`application/bootstrap.py`、`utils/installation.py` | [PNG](uml/02-install.png) / [Mermaid](uml/02-install.mmd) |
| 03 本机配置 | `web.py`、Session、recovery、前端用例；填写、预览、交接与退出 | [PNG](uml/03-configure.png) / [Mermaid](uml/03-configure.mmd) |
| 04 凭据来源与登录 | KeyDisplay、`utils/auth.py`、`utils/bailian.py`；本机Key与官方BL登录 | [PNG](uml/04-auth.png) / [Mermaid](uml/04-auth.mmd) |
| 05 转写与交付 | `application/transcription.py`、delivery、BL与文档writer | [PNG](uml/05-transcribe.png) / [Mermaid](uml/05-transcribe.mmd) |
| 06 重新导出与状态查询 | `export_job()`、`job_status()`与本机记录，不调用云端 | [PNG](uml/06-export.png) / [Mermaid](uml/06-export.mmd) |
| 07 本地状态 | 编辑会话、一次执行与交付结果的状态关系 | [PNG](uml/07-state.png) / [Mermaid](uml/07-state.mmd) |
| 08 记录保存失败 | `_save_status()`失败时的当次回执、磁盘状态与停止位置 | [PNG](uml/08-failure.png) / [Mermaid](uml/08-failure.mmd) |
| 09 Skill 自动更新 | `scripts/update.py`、共享读取保护及Codex后续分派 | [PNG](uml/09-update.png) / [Mermaid](uml/09-update.mmd) |

`session_id` 定位编辑会话，`job_id` 定位已交接任务。图03/07中的预览不是执行授权；交接失败发现原录音变化或命令过长时保留预览，经既有“返回修改”退出后重新检查。成功交接以原子发布的 `config.json` 为完成标记。

HTTP控制回执与SSE由不同请求线程发送，没有固定先后。显式取消先保存 `cancelled.json`，再设置终态事件；Codex取得结果后等待原serve退出。图04省略了HTTP分派生命线，事件发送仍由web完成。会话结束与任务执行是两个生命周期，编辑取消不表示云端取消。

状态字段、恢复操作和运行限制分别维护在 [errors.md](../skills/asr-transcription/references/errors.md)、[DEVELOPMENT](DEVELOPMENT.md) 与 [ISSUES](ISSUES.md)，不在此复制完整说明。已执行验证见 [ACCEPTANCE](ACCEPTANCE.md)。

## 统一渲染

受管入口为 [scripts/render_uml.ts](../scripts/render_uml.ts)，唯一主题为 [uml/theme.json](uml/theme.json)。全部图沿用已有浅蓝灰风格、微软雅黑、白色背景与1.5倍像素密度；主题只使用Mermaid公开参数，不在单张图里覆盖。Mermaid固定为开发依赖11.12.0，tsx和Playwright使用根锁文件版本，浏览器为本机Microsoft Edge。

在已有开发环境的仓库根运行：

```powershell
npm ci
npm run check:uml
npm run render:uml
# 仅重建受影响图稿，图名也可带.mmd后缀：
npm run render:uml -- 03-configure 07-state
```

入口只从本项目依赖和共享主题读取，不回退 `.runtime`、其他缓存或另一套配色。依赖、主题或Edge缺失，以及Mermaid解析失败时，命令明确失败。未知图名也会报错。

每张图保存PNG前检查全部SVG文字与foreignObject边界；输出该图PNG的实际尺寸和文字节点数。边界检查不代表没有重叠或足够易读，修改后仍需查看整图与相关局部。PNG是由对应 `.mmd` 和共享主题生成的阅读产物；修改图稿或主题后重新运行入口，连同PNG一起审阅。

## 图像

### 01A 对象职责与依赖

![对象职责与依赖](uml/01-classes.png)

### 01B 共享数据与进程契约

![共享数据与进程契约](uml/01b-data.png)

### 01C 确认配置与交付回执

![确认配置与交付回执](uml/01c-protocol.png)

### 02 准备工作目录

![工作目录环境准备](uml/02-install.png)

### 03 本机配置

![填写、预览与交接](uml/03-configure.png)

### 04 凭据来源与登录

![凭据与官方登录](uml/04-auth.png)

### 05 转写与交付

![一次转写与文件交付](uml/05-transcribe.png)

### 06 重新导出与状态查询

![本地重导与状态查询](uml/06-export.png)

### 07 本地状态

![编辑会话与转写任务状态](uml/07-state.png)

### 08 记录保存失败

![执行记录保存失败](uml/08-failure.png)

### 09 Skill 自动更新

![版本检查、更新与业务衔接](uml/09-update.png)
