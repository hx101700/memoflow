[中文](https://github.com/hx101700/memoflow/blob/v0.1.3/release/NOTES.md) | English

# MemoFlow v0.1.3

This release improves how transcription continues when update checks run into problems, adds the installed version to the page, and upgrades to the official Bailian CLI 2.5.1, making installation status and login issues easier to identify.

### What's new

- **Continue after update-check issues**: for recoverable problems such as GitHub HTTP 403, use the installed Skill and continue the current request by opening the recording configuration page.
- **See the installed version on the page**: the current Skill version appears beside MemoFlow in the top-left corner, making installation checks and issue reports easier. The label adapts to light and dark themes and aligns with the brand text.
- **Official Bailian CLI 2.5.1**: adopts the upstream fix for fast login callbacks and improves login timeout and failure messages to help diagnose authorization issues.
- **Clearer installation guidance**: distinguishes temporary update-check failures from installation states that need repair, with the corresponding steps to continue or fix the installation.
- **Smoother cancellation and updates**: asking to cancel or check for updates while filling in or previewing a form ends that editing session first. Its cancellation result remains available after the page service exits, and the next transcription starts with a new page.
- **Return to editing when a recording changes**: if the original recording is modified or moved after preview, the error keeps the preview available. You can return to the form, select the recording again, and review the updated settings.

### Downloads

| Package | Description |
| --- | --- |
| **Full package (recommended manual download for first installation) · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.3/asr-transcription.zip)** | Includes Python, Node.js, and the bundled npm to prepare the base environment during initial installation. |
| **Lite package (updates, downloaded automatically by Codex) · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.3/asr-transcription-lite.zip)** | Reuses the installed Python, Node.js, and npm for subsequent Skill updates. |

Installing Python dependencies and Bailian CLI still requires an internet connection.

### Installation and updates

For a first installation, or an upgrade from [v0.1.0](https://github.com/hx101700/memoflow/releases/tag/v0.1.0) or [v0.1.1](https://github.com/hx101700/memoflow/releases/tag/v0.1.1), give the new ZIP to Codex and follow the [Install section of the README](https://github.com/hx101700/memoflow/blob/v0.1.3/README.en.md#install).

If you have [v0.1.2](https://github.com/hx101700/memoflow/releases/tag/v0.1.2) installed, ask Codex to “check for updates to the transcription Skill and install them” to upgrade automatically to v0.1.3 (this release). Future formal releases higher than v0.1.3 can also be obtained this way.

You can also update an earlier version manually: give the new ZIP to Codex together with the complete request in the [Install section](https://github.com/hx101700/memoflow/blob/v0.1.3/README.en.md#install).

If you installed an earlier v0.1.3 package, download the ZIP from this page again and give it to Codex with the installation request above to install the reissued package.

Upgrades use the original workspace and preserve existing runtimes, credentials, jobs, and transcripts. Codex prepares the Bailian CLI dependencies required by the new version.

Please report problems through [Issues](https://github.com/hx101700/memoflow/issues).
