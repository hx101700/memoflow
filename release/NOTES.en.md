[中文](https://github.com/hx101700/memoflow/blob/v0.1.1/release/NOTES.md) | English

# MemoFlow v0.1.1

This update fixes an issue where Bailian CLI did not apply the configured timeout when uploading recordings. Uploads previously used a fixed two-minute timeout; they now respect the configured limit, allowing more time for larger recordings and slower connections.

### What's new

- **Recording upload timeout fix**: updated Bailian CLI's upload path to use the configured timeout. The fix is included in both packages, and installation checks the required revision.
- **Improved upgrade instructions**: give the new ZIP to Codex to update the existing Skill and Bailian CLI while preserving the runtimes, credentials, tasks, and transcription results in your workspace.

### Bailian CLI source changes

MemoFlow builds `bailian-cli-core@2.1.0-memoflow.1` from the official BL v2.1.0 source. The changes are in two source files:

- `packages/core/src/client/client.ts`: `Client.uploadFile()` passes the effective `settings.timeout` into the file upload call chain.
- `packages/core/src/files/upload.ts`: `resolveFileUrl()` and `uploadFile()` forward the timeout in seconds to `uploadToOSS()`, replacing the fixed `120_000` ms OSS upload timer with `timeout * 1000`.

Upload-policy requests retain the official 15-second timeout. The CLI, commands, and runtime packages remain at the official 2.1.0 version. Both ZIPs include the revised core as a local npm archive, installed through the dependency lock and npm override, with the Apache-2.0 license and modification notice included. [Source patch and build instructions](https://github.com/hx101700/memoflow/blob/v0.1.1/patches/README.md)

Upstream report: [modelstudioai/cli#243](https://github.com/modelstudioai/cli/issues/243).

### Downloads

| Package | Description |
| --- | --- |
| **Full (recommended) · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.1/asr-transcription.zip)** | Includes Python and Node.js runtimes to reduce first-time installation downloads. |
| **Lite · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.1/asr-transcription-lite.zip)** | A smaller download; setup obtains the runtimes from their official sources. |

Both packages still require an internet connection to install Python dependencies and Bailian CLI.

### Upgrading

Wait for any running transcription task to finish. Then give the new ZIP to Codex with the installation request from the README. If the Skill is already installed, Codex overwrites its files with the new version, using the same workspace and preserving existing credentials, tasks, and results.

See the [README](https://github.com/hx101700/memoflow/blob/v0.1.1/README.en.md) for usage instructions. Please report problems through [Issues](https://github.com/hx101700/memoflow/issues).
