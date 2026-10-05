# 验证记录

更新：2026-10-05。本页记录 `dev` 独立运行环境及完整／轻量包的验证。正式 v0.1.0 的记录保存在[对应标签](https://github.com/hx101700/memoflow/blob/v0.1.0/doc/ACCEPTANCE.md)，不作为本轮新安装器的测试结果。

## 已执行检查

| 范围 | 实际结果 |
| --- | --- |
| Python 完整回归 | 独立 CPython 3.12.10、Node 24.21.0、BL 2.1.0 环境下 440 项通过，无跳过，131.541 秒；包含真实本机 BL/npm/pip 合约 |
| 完整／轻量包及 PowerShell | 随后的 24 项定向检查通过，27.867 秒；包含包内归档、损坏摘要拒绝、旧安装保留、中文路径、目录边界和两包同源 |
| 安装日志 UTF-8 | 20 项 bootstrap 与真实 pip 合约通过，5.217 秒；生产参数下载到中文空格路径，日志完整；临时剥去 -X utf8 的反证按预期复现乱码 |
| Python 类型 | 最终运行及开发入口严格 mypy 31 个源文件通过，无增量缓存 |
| 前端 | 55 项测试及 Vue 类型检查通过 |
| Edge 网页 | 完整现有回归通过，49.781 秒，包含配置、表格、主题/语言、预览交接及终态；未改前端源码与静态构建产物 |
| 官方运行时 | Python 完整 ZIP 和 Node Windows x64 ZIP 的 SHA-256 与官方索引／SHASUMS 匹配 |
| 联网安装 | PATH 仅含 Windows 系统命令，从零准备两个独立运行时、8 个 Python 包及 BL；doctor issues 为空 |
| 包内运行时安装 | 中文空格工作目录无既有环境；从完整候选包解压 Python/Node，再联网安装业务依赖与 BL；运行时下载缓存为空 |
| 最终完整 ZIP | 用最终包在上述环境复核安装复用、doctor、Tk、HTTP 页面与取消，5.093 秒；52 个 Skill 文件逐字保持不变 |
| UML | 01A、02 使用 Mermaid 11.12.0 和 Edge 渲染并目视检查；分别 60、157 个文字节点，越界数均为 0 |

完整回归之后增加的双包与中文日志场景单独检查；表内不同批次存在重复用例，不将数字相加宣称一次完整运行。首次受限令牌测试因临时目录 ACL 拒绝访问失败，已在正常 Windows 权限重跑；没有把权限错误转化成业务补丁或跳过用例。

## 安装验证

首次联网路径没有系统 Python/Node 搜索入口。Python 官方完整 ZIP 下载并通过摘要检查；Node 下载曾在 25,886,720 字节处停止传输，保留部分文件后使用原生 curl 续接剩余数据，最终摘要匹配。生产下载增加连续 120 秒几乎无数据时的原生断连与有限重试，未设整个安装总时限。

完整包在独立的中文空格路径安装，两运行时直接从包内归档解压。系统环境没有被安装器修改，运行时下载缓存为空。该候选安装发现旧 pip 子进程日志中文乱码，修正为 `-I -X utf8 -m pip/ensurepip` 后，以真实 pip 合约验证；最终 ZIP 使用修正后的代码。

最终 ZIP 的复核确认 Python 3.12.10、Tcl/Tk 8.6.15、Node 24.21.0、BL 2.1.0，以及 av 18.1.0、python-dotenv 1.2.3、openpyxl 3.1.5、et-xmlfile 2.0.0、defusedxml 0.7.1、python-docx 1.2.0、lxml 6.1.3、typing-extensions 4.16.0。`doctor` 无问题，重复安装回执为 `already_installed`。Tk 成功创建隐藏窗口、更新并销毁；这不是人工文件选择验收。

同一环境通过最终包 `serve --no-browser` 启动服务，首页、app.js、app.css、api/session 均返回 200；`cancel` 后服务退出码为 0。逐文件对照最终 ZIP，Skill 无新文件、字节变化或运行缓存。未登录 BL、上传音频或调用云端识别。

## 发行文件

| 文件 | 文件数 | 字节数 | SHA-256 |
| --- | --- | --- | --- |
| dist/asr-transcription.zip | 52 | 70366402 | `08a8c055a9e4c5678e3c2427e84b95847ba01d44a6c295ff68eb074f5cf7f02b` |
| dist/asr-transcription-lite.zip | 50 | 347808 | `501398f1095c6e519c276112d49435df2c39846c79b6c8af3d5e765f04fee122` |

两包共同的 50 个文件是同一份源码、静态页面、依赖锁、参考资料及最新版双语 README。完整包额外附带两个未经修改的官方运行时 ZIP；不包含开发 doc、AGENTS、UML、测试、node_modules、venv、凭据、音频和结果。

最终对照 21 份 Markdown 的 122 个本地链接全部有效；两包 CRC、固定清单与当前源文件逐字比较通过。代码提交 `8f7704d207538bda6cab0f30a27c926d5032b582` 已推送，`dev-runtime` 预发布的两个附件已由 GitHub 返回的大小与摘要再次确认匹配；正式 v0.1.0 原 Skill 附件摘要保持不变。

运行时来源与摘要：

| 官方文件 | SHA-256 |
| --- | --- |
| python-3.12.10-amd64.zip | `8649692de846c56a7189d6dae5c322ab20deb1b5908b6f39426b62a36f39415d` |
| node-v24.21.0-win-x64.zip | `158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541` |

## 复现与边界

运行单元及合约前先在 `.runtime/skill-contract-workspace` 通过 Skill 的 PowerShell 入口准备环境，确保真实 BL/npm/pip 合约参与；开发虚拟环境另外安装 `requirements-dev.txt`。

```powershell
.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -t . -q
.venv\Scripts\python.exe -B -X utf8 -m mypy --config-file mypy.ini --no-incremental
npm run test:web
npm run check:web
npm run test:browser
```

本轮在当前 Windows 主机验证了不依赖系统 Python/Node 的安装路径，没有在多台全新 Windows 10/11 机器上测试，也没有重新完成新 Codex 对话、人工原生窗口、真实授权/识别及 Office 逐页验收。环境隔离改善版本一致性，不能证明任意网络、权限或组织策略下都能成功。用户已安装 Skill、旧项目目录和私人数据保持原样。
