# 百炼 core 上传超时修订

本目录保存随 Skill 交付的 `bailian-cli-core@2.1.0-memoflow.1` 的源码差异。上游基线为 [BL v2.1.0](https://github.com/modelstudioai/cli/tree/v2.1.0)，提交 `fc080016469f33ce6726ae997d0ff6428c19aa49`。

官方 `Client.uploadFile()` 没有传入有效配置中的 `timeout`，`uploadToOSS()` 则固定使用 120 秒计时器。修订将秒数沿现有调用链传递至上传请求，保留原生认证、multipart、取消信号、错误处理及后续识别。获取上传凭证仍使用上游的 15 秒时限；直接调用 SDK 且未指定上传 timeout 时保留原有 120 秒默认值。

## 构建

在独立的上游源码副本内应用本目录的 patch。构建使用上游的 Node、pnpm 和 Vite Plus 工具链，基线声明的 pnpm 版本为 10.33.2：

```text
git checkout fc080016469f33ce6726ae997d0ff6428c19aa49
git apply <MemoFlow>/patches/bailian-cli-core-2.1.0-upload-timeout.patch
```

将上游根目录的 `LICENSE` 复制到 `packages/core/LICENSE`，将本目录的 `bailian-cli-core.NOTICE` 复制到 `packages/core/NOTICE`，再执行：

```text
pnpm install --filter bailian-cli-core... --frozen-lockfile --ignore-scripts
pnpm --filter bailian-cli-core build
pnpm --filter bailian-cli-core pack --pack-destination <MemoFlow>/skills/asr-transcription/scripts/bailian/archives
```

`scripts/bailian/package.json` 的根依赖与 npm override 使 CLI 和 commands 共用这一份 core。变更归档后，使用项目私有 Node/npm 重新生成 `scripts/bailian/package-lock.json`，由 npm 记录归档的完整性摘要；构建产物及锁文件需一同核对。

## 验证

[test_bl_upload.py](../tests/test_bl_upload.py) 用本机服务复现原版固定上传时限，并验证修订版的成功、超时及不重传行为；外部请求由测试夹具阻止。通过 `MEMOFLOW_BL_CONTRACT_WORKSPACE` 指定已安装修订版的测试工作目录，通过 `MEMOFLOW_BL_UPLOAD_ENTRY` 指定该目录的 `bailian.mjs`，再运行上传与现有 BL 合约测试。

修订归档包含 Apache-2.0 `LICENSE` 和修改 `NOTICE`。本目录的源码差异及构建说明属于开发资料，发行 ZIP 仅包含运行所需归档。
