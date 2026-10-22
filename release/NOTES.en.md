[中文](https://github.com/hx101700/memoflow/blob/v0.1.2/release/NOTES.md) | English

# MemoFlow v0.1.2

This update makes future upgrades easier: Codex can check for and install new Skill versions while reusing the existing environment, reducing repeated downloads and manual setup. It also adopts the official Bailian CLI 2.4.0 and improves upload, login, and environment checks.

### What's new

- **Easier future upgrades**: added automatic Skill updates, with at most one automatic release check per day. When a new version is available, Codex downloads the lite package, updates the Skill, and reports the result. You can also ask Codex to check for updates.
- **Smaller update downloads**: reuse the workspace's Python, Node.js, and npm while preparing any dependencies required by the new version. Credentials, jobs, and transcripts are preserved.
- **Official upload and login fixes**: upgraded to the official Bailian CLI 2.4.0, using its upload timeout and Windows authorization-link handling in place of the previous local revision and login adapter.
- **Clearer environment diagnostics**: corrected virtual-environment binding checks, distinguished missing dependencies from interpreter failures, and reduced repeated installation and diagnostic checks.
- **Less space used by old downloads**: after a successful environment upgrade, remove obsolete Python dependency downloads and npm cache entries from the workspace while retaining reusable content for the current versions.

### Downloads

| Package | Description |
| --- | --- |
| **Full package (first installation, manual download, recommended) · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.2/asr-transcription.zip)** | Includes Python, Node.js, and the bundled npm to prepare the base environment during initial installation. |
| **Lite package (updates, downloaded automatically by Codex) · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.2/asr-transcription-lite.zip)** | Reuses the installed Python, Node.js, and npm for subsequent Skill updates. |

Installing Python dependencies and Bailian CLI still requires an internet connection.

### Installation and updates

For a first installation, or your first upgrade from [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0) or [v0.1.1](https://github.com/hx101700/memoflow/releases/tag/v0.1.1) to v0.1.2 (this release), give the new ZIP to Codex and follow the [README](https://github.com/hx101700/memoflow/blob/v0.1.2/README.en.md#install).

After installing v0.1.2 (this release), you can let Codex obtain subsequent formal versions higher than v0.1.2 through automatic updates, or continue giving new ZIPs to Codex to update manually.

If the workspace has an older Bailian CLI installation, Codex follows the updated Skill instructions to prepare the required version while preserving existing runtimes, credentials, jobs, and results.

Please report problems through [Issues](https://github.com/hx101700/memoflow/issues).
