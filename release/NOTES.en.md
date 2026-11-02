[中文](https://github.com/hx101700/memoflow/blob/v0.1.4/release/NOTES.md) | English

# MemoFlow v0.1.4

This release upgrades to the official Bailian CLI 2.7.2, adopts its upload and network compatibility fixes, and adds clearer explanations for upload failures and interrupted execution to help identify problems during transcription.

### What's new

- **Bailian CLI 2.7.2**: updates the official dependencies while continuing to use Qwen-Audio-3.1-ASR-Flash-Filetrans for recording transcription.
- **Clearer upload errors**: when obtaining upload authorization fails, the HTTP status, error code, and request ID returned by the service are preserved, helping Codex provide more specific troubleshooting guidance.
- **Interrupted execution explained**: recognizes Bailian CLI's interrupted exit status to help distinguish local execution status from the cloud task outcome.

### Downloads

| Package | Description |
| --- | --- |
| **Full package (recommended manual download for first installation) · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.4/asr-transcription.zip)** | Includes Python, Node.js, and the bundled npm to prepare the base environment during initial installation. |
| **Lite package (updates, downloaded automatically by Codex) · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.4/asr-transcription-lite.zip)** | Reuses the installed Python, Node.js, and npm for subsequent Skill updates. |

### Installation and updates

For a first installation, or an upgrade from [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0) or [v0.1.1](https://github.com/hx101700/memoflow/releases/tag/v0.1.1), give the new ZIP to Codex and follow the [Install section of the README](https://github.com/hx101700/memoflow/blob/v0.1.4/README.en.md#install).

If you have [v0.1.2](https://github.com/hx101700/memoflow/releases/tag/v0.1.2) or a later version installed, ask Codex to “check for updates to the transcription Skill and install them” to upgrade automatically to v0.1.4 (this release). Future formal releases can also be obtained this way.

You can also update an earlier version manually: give the new ZIP to Codex together with the complete request in the [Install section](https://github.com/hx101700/memoflow/blob/v0.1.4/README.en.md#install).

Upgrades use the original workspace and preserve existing runtimes, credentials, jobs, and transcripts. Codex prepares Bailian CLI 2.7.2 as required by this release.

When using MemoFlow on a network in mainland China, we recommend configuring reliable GitHub access so updates can be checked and downloaded smoothly.

Please report problems through [Issues](https://github.com/hx101700/memoflow/issues).
