[中文](https://github.com/hx101700/memoflow/blob/v0.1.5/release/NOTES.md) | English

# MemoFlow v0.1.5

This release improves support for proxy configurations, makes the confirmation message clearer, and adopts the official Bailian CLI 2.8.4. After an update, Codex explains what changed and continues your task.

### What's changed

- **Bailian CLI 2.8.4 support**: adapts browser sign-in and error handling to the new CLI, while continuing to use Qwen-Audio-3.1-ASR-Flash-Filetrans for transcription.
- **Preserve your network settings**: proxy and certificate settings now reach the CLI, fixing an issue where MemoFlow filtered them out when starting a child process.
- **Clearer confirmation messages**: the message copied from the preview includes the cloud service, Beijing region, model, and session ID so Codex can act on your transcription authorization.
- **See what changed after updating**: once the update and environment setup succeed, Codex summarizes that version's release notes and continues your original task.

### Downloads

| Package | Description |
| --- | --- |
| **Full package (recommended manual download for first-time installation) · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.5/asr-transcription.zip)** | Includes Python, Node.js, and the accompanying npm to prepare the initial runtime environment. |
| **Lite package (for updates, downloaded automatically by Codex) · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.5/asr-transcription-lite.zip)** | Reuses installed Python, Node.js, and npm for subsequent updates. |

### Installation and updates

For a first-time installation or an upgrade from [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0) or [v0.1.1](https://github.com/hx101700/memoflow/releases/tag/v0.1.1), give the new ZIP to Codex and follow the [Install section in the README](https://github.com/hx101700/memoflow/blob/v0.1.5/README.en.md#install).

If you have [v0.1.2](https://github.com/hx101700/memoflow/releases/tag/v0.1.2) or a later version installed, tell Codex “Check for updates to the asr-transcription Skill and update it if needed” to upgrade to v0.1.5 (this release). Future stable releases are available through the same command.

Manual updates are also supported: send the new ZIP to Codex together with the complete request in the [Install section](https://github.com/hx101700/memoflow/blob/v0.1.5/README.en.md#install).

Updates reuse your working folder and preserve its runtimes, credentials, jobs, and transcription results. Codex prepares Bailian CLI 2.8.4 as required by this release.

When updating from a network in mainland China, use a connection that can reliably reach GitHub so version checks and downloads can complete.

If you encounter a problem, please report it through [Issues](https://github.com/hx101700/memoflow/issues).
