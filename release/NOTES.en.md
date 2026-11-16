[中文](https://github.com/hx101700/memoflow/blob/v0.1.6/release/NOTES.md) | English

# MemoFlow v0.1.6

This release adds **Listen and review** after transcription. Replay the recording as you correct the text and speaker labels, then export reviewed documents.

### What's changed

- **Bailian CLI 2.10.1**: updates the official CLI and its dependencies while continuing to use Qwen-Audio-3.1-ASR-Flash-Filetrans.
- **Listen and review**: replay individual sentences, edit text and speaker labels, and save changes automatically. Reset a sentence or jump to the next change, then choose a folder for reviewed Word, Excel, and Markdown files.
- **Clearer Skill communication**: Codex uses more natural, concise messages when starting, waiting, and delivering results, with a clear explanation of the current state and next step.
- **Update retries**: after installing this release, future version checks and lite-package downloads share up to two additional network retries, reducing the need to restart updates after temporary connection problems.
- **Billing and quota guidance**: recognition failures caused by an exhausted free allowance, overdue payments, or budget limits include relevant explanations and next steps.
- Bug fixes and usability improvements.

### Downloads

| Package | Description |
| --- | --- |
| **Full package (recommended manual download for first-time installation) · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.6/asr-transcription.zip)** | Includes Python, Node.js, and the accompanying npm to prepare the initial runtime environment. |
| **Lite package (for updates, downloaded automatically by Codex) · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.6/asr-transcription-lite.zip)** | Reuses installed Python, Node.js, and npm for subsequent updates. |

### Installation and updates

For a first-time installation or an upgrade from [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0) or [v0.1.1](https://github.com/hx101700/memoflow/releases/tag/v0.1.1), give the new ZIP to Codex and follow the [Install section in the README](https://github.com/hx101700/memoflow/blob/v0.1.6/README.en.md#install).

If you have [v0.1.2](https://github.com/hx101700/memoflow/releases/tag/v0.1.2) or a later version installed, tell Codex “Check for updates to the asr-transcription Skill and update it if needed” to upgrade to v0.1.6 (this release). Future stable releases are available through the same command.

Manual updates are also supported: send the new ZIP to Codex together with the complete request in the [Install section](https://github.com/hx101700/memoflow/blob/v0.1.6/README.en.md#install).

Updates reuse your working folder and preserve its runtimes, credentials, jobs, and transcription results. Codex prepares Bailian CLI 2.10.1 as required by this release.

When updating from a network in mainland China, use a connection that can reliably reach GitHub so version checks and downloads can complete.

If you encounter a problem, please report it through [Issues](https://github.com/hx101700/memoflow/issues). If MemoFlow helps you, consider giving the project a [star](https://github.com/hx101700/memoflow).
