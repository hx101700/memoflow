中文 | [English](https://github.com/hx101700/memoflow/blob/v0.1.1/release/NOTES.en.md)

# MemoFlow v0.1.1

本次更新修复了百炼 CLI 上传录音时未使用指定等待时间的问题。此前，文件上传会受到固定两分钟时限的影响；现在上传会使用配置的等待时间，为较大录音和较慢网络留出更充足的时间。

### 更新内容

- **修复录音上传超时**：修订百炼 CLI 的上传调用链，使上传使用指定的等待时间。修复随安装包交付，安装时会检查对应版本。
- **完善旧版升级说明**：可以将新版 ZIP 交给 Codex，更新已有 Skill 和百炼 CLI，同时保留原工作目录中的运行环境、凭据、任务及转写结果。

### 百炼 CLI 源码修订

本项目基于官方 BL v2.1.0 构建 `bailian-cli-core@2.1.0-memoflow.1`，具体修改了两个源码文件：

- `packages/core/src/client/client.ts`：`Client.uploadFile()` 将有效配置中的 `settings.timeout` 传给文件上传调用链。
- `packages/core/src/files/upload.ts`：经 `resolveFileUrl()`、`uploadFile()` 将等待秒数传至 `uploadToOSS()`，OSS 上传计时器由固定的 `120_000` 毫秒改为 `timeout * 1000`。

上传凭证请求保留官方15秒时限。CLI、commands、runtime 沿用官方2.1.0；修订 core 以本地 npm 归档随两个 ZIP 交付，通过依赖锁及 npm override 安装，并保留 Apache-2.0 许可与修改说明。[源码差异与构建方法](https://github.com/hx101700/memoflow/blob/v0.1.1/patches/README.md)

上游问题反馈：[modelstudioai/cli#243](https://github.com/modelstudioai/cli/issues/243)。

### 下载

| 安装包 | 说明 |
| --- | --- |
| **完整包（推荐） · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.1/asr-transcription.zip)** | 附带 Python 和 Node.js 运行时，减少首次安装的下载内容。 |
| **轻量包 · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.1/asr-transcription-lite.zip)** | 下载体积更小，首次安装时从官方来源下载运行时。 |

两种包的 Python 依赖和百炼 CLI 安装仍需联网。

### 从旧版升级

先等待正在执行的转写任务结束，再将新版 ZIP 和 README 中的统一安装请求发给 Codex。已安装时直接覆盖更新Skill文件，沿用原工作目录并保留已有凭据、任务和结果。

详细使用说明见 [README](https://github.com/hx101700/memoflow/blob/v0.1.1/README.md)。遇到问题，欢迎通过 [Issues](https://github.com/hx101700/memoflow/issues) 反馈。
