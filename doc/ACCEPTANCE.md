# 验证记录

更新：2026-10-05。本页记录 v0.1.1 的最终发布检查。v0.1.0 与开发预览的历史记录保存在各自 Git 标签中。

## 最终检查

| 范围 | 实际结果 |
| --- | --- |
| Python 完整回归 | 446 项通过，0 跳过，140.569 秒；包含业务、HTTP、真实本机 BL/npm/pip、媒体、文档、安装与包边界 |
| 安装编码修正 | 34 项定向检查通过，18.925 秒；全新中文空格 venv 的实际 ensurepip 日志保真，pip 正常加载 |
| Python 类型 | 严格 mypy 31 个源文件通过 |
| 前端 | 55 项测试通过；Vue 类型检查、登录适配及 Vite 构建通过 |
| Edge 网页 | 现有完整回归通过，40.255 秒，覆盖表格、预览交接、语言、主题与终态 |
| 官方运行时 | Python 完整 ZIP、Node Windows x64 ZIP 的 SHA-256 与官方索引／SHASUMS 匹配 |
| 全新目录安装 | 候选完整包在中文空格工作目录完成安装，PATH 无系统 Python/Node；8 个 Python 包和 BL 正常，运行时下载缓存为空 |
| 最终完整 ZIP | 环境复用、doctor、Tk、HTTP 启动/取消全部通过，4.781 秒；52 个资源文件保持只读 |
| 最终轻量 ZIP | 在同一已准备工作目录执行相同检查，通过，4.594 秒；50 个资源文件保持只读 |
| 发行清单 | 两包 CRC、文件集合和当前源码逐字对照通过，共同的 50 个文件一致 |
| 文档与 UML | 19 份 Markdown、120 个本地链接有效；重新阅读 Skill、安装说明及 UML 01A/02，与实际调用一致，无需重绘 |

定向检查包含在最终完整回归中，不将数字相加。测试只使用本机合成凭据／数据和隔离目录，没有上传真实录音或调用云端识别。

## 发布前发现并修正的问题

**ensurepip 输出编码。** 全新中文目录安装发现，Python 3.12 的 ensurepip 内部重新启动 pip 时只继承 `-I`，未继承外层 `-X utf8`。默认 UTF-8 读取能稳定复现中文路径乱码。当前只在 ensurepip 调用使用 `locale.getencoding()` 解码，其余 pip 仍显式输出 UTF-8；日志统一保存为 UTF-8。真实新建 venv、ensurepip 安装、日志与 pip 加载均已验证，没有修改标准库或系统设置。

**Windows HTML 换行。** 本轮重新构建发现 CRLF 源 HTML 经 Vite 生成混合换行。通过 `.gitattributes` 将 HTML 固定为 LF，并重新生成产物。最终 HTML 内容与已有实现一致，没有增加前端逻辑；Git 空白检查通过。

**正式发行入口。** README、usage、维护规则与发布说明统一指向 0.1.1，移除当前目录中的开发预览说明副本；旧资料仍可通过原标签查阅。根 package.json 与 package-lock.json 由 npm version 同步，依赖版本未改变。

## 安装与最终包核对

候选包从全新工作目录完成运行时解压及依赖联网安装，随后发现并修正 ensurepip 的显示问题。修正后的最终完整、轻量 ZIP 分别解压到独立 Skill 目录，再在该工作目录验证 bootstrap 复用、doctor、Tk 和服务启动。两包的全部文件与最终源码逐字一致。

实际环境为 Python 3.12.10、Tcl/Tk 8.6.15、Node 24.21.0、BL 2.1.0；依赖为 av 18.1.0、python-dotenv 1.2.3、openpyxl 3.1.5、et-xmlfile 2.0.0、defusedxml 0.7.1、python-docx 1.2.0、lxml 6.1.3、typing-extensions 4.16.0。doctor 的 issues 均为空，复用返回 already_installed。Tk 创建隐藏窗口、更新并销毁成功，此项不代替人工文件选择验收。

最终两包均使用仅含 Windows 系统目录的 PATH；首页、app.js、app.css、api/session 返回 200，cancel 后服务退出码为 0。逐文件对照 ZIP，Skill 无新增文件或字节变化。轻量版的首次官方联网下载路径已在开发预览阶段实测，本轮验证其最终代码和环境复用，没有重复下载两个运行时。

## 0.1.1 发行文件

| 文件 | 文件数 | 字节数 | SHA-256 |
| --- | --- | --- | --- |
| dist/v0.1.1/asr-transcription.zip | 52 | 70366194 | `8d59be95cb628df03ea12e0d0b64a3618f7a3dad93936199474d6d208f72ec1d` |
| dist/v0.1.1/asr-transcription-lite.zip | 50 | 347600 | `7a78ad146413503a338d662607b00650ef6a5d81888aea96a23f3c6cb4995e5f` |

两包包含运行代码、静态页面、依赖锁、参考资料及最新版双语 README；完整包另外附带两个原始官方运行时 ZIP。开发 doc、AGENTS、UML、测试、已安装依赖、凭据、录音和结果不入包。

| 官方运行时归档 | SHA-256 |
| --- | --- |
| python-3.12.10-amd64.zip | `8649692de846c56a7189d6dae5c322ab20deb1b5908b6f39426b62a36f39415d` |
| node-v24.21.0-win-x64.zip | `158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541` |

## 复现与边界

在 `.runtime/skill-contract-workspace` 通过 Skill 的 PowerShell 入口准备依赖，使真实 BL/npm/pip 合约参与；开发环境另安装 requirements-dev.txt。

```powershell
.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -t . -q
.venv\Scripts\python.exe -B -X utf8 -m mypy --config-file mypy.ini --no-incremental
npm run test:web
npm run build:login
npm run build:web
npm run test:browser
```

本轮验证在当前 Windows 主机执行。没有在多台全新 Windows 10/11 上测试，也没有重跑新 Codex 对话、人工原生窗口、真实登录／识别及 Office 逐页验收。环境隔离减少版本冲突，不能保证任意网络、权限或组织策略下都成功。用户已安装 Skill、旧目录和私人数据保持原样。
