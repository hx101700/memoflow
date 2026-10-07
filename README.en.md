# MemoFlow

[中文](README.md) | English

> Attach a Chinese recording to Codex and get a timestamped, speaker-aware transcript in Word, Excel, and Markdown.

[![Latest release](https://img.shields.io/github/v/release/hx101700/memoflow?display_name=tag&sort=semver)](https://github.com/hx101700/memoflow/releases/latest) [![License](https://img.shields.io/github/license/hx101700/memoflow)](LICENSE) [![Windows](https://img.shields.io/badge/Windows-10%2F11%20x64-0078D4)](https://github.com/hx101700/memoflow/releases/latest)

MemoFlow is a Codex Skill for audio transcription. It uses Alibaba Cloud Model Studio's [Qwen-Audio-3.1-ASR-Flash-Filetrans](https://help.aliyun.com/en/model-studio/qwen-audio-3-1-asr-flash-filetrans). A local web page lets you review the recording, recognition settings, hotwords, context, and output folders before Codex runs the transcription and delivers the files.

Stage one is available now: **a reliable transcript for human review**. Personalized meeting minutes built from reviewed transcripts, examples, and feedback are planned for a later stage.

<!-- SCREENSHOT: hero
Add a real screenshot or 20–40 second GIF showing “add recording → preview → copy for Codex”.
Suggested file: doc/images/memoflow-demo.gif
Hide API keys, usernames, local paths, and real meeting content.
-->

## Start in 30 seconds

1. Download the [v0.1.2 package](https://github.com/hx101700/memoflow/releases/tag/v0.1.2).
2. Send the ZIP to Codex with:

   ```text
   Install this ZIP as the asr-transcription Skill. Read its SKILL.md and prepare the required environment in the current task folder.
   ```

3. After installation, tell Codex:

   ```text
   Please transcribe this recording.
   ```

4. Review the recording and settings in the web page, choose “Confirm and preview”, then choose “Copy for Codex” and send the confirmation message back to the conversation.

The full package is recommended for most users because it includes Python and Node.js runtimes. The lite package is smaller and downloads those runtimes from official sources during setup. Both packages support Windows 10/11 x64; Python dependencies and the BL CLI still require an internet connection.

Before using MemoFlow, [create an Alibaba Cloud account](https://help.aliyun.com/zh/account/step-1-register-an-alibaba-cloud-account) and follow the [Model Studio setup guide](https://help.aliyun.com/en/model-studio/first-api-call-to-qwen).

## What you get

| File | Contents |
| --- | --- |
| `transcription.json` | The original transcription result returned by Model Studio |
| `transcription.docx` | A readable Word document for review |
| `transcription.xlsx` | An Excel document for filtering and segment-by-segment review |
| `transcription.md` | A Markdown document for notes and archiving |

All three documents keep timestamps. Speaker numbers are included when speaker diarization is enabled. Output folders are selected in the page and default to `transcriptions` in the current workspace.

## Features

- **Codex Skill workflow**: Conversation attachments, local file selection, and existing recording paths use the same configuration page.
- **Chinese recognition enhancement**: Qwen-Audio 3.1 with hotwords and context sent together when enabled.
- **Speaker diarization**: Enabled by default; multichannel recordings are merged only when needed, with the original file preserved.
- **Visual preview**: Filling and preview are separate steps; a task is created only after you hand the confirmed settings to Codex.
- **Two Model Studio authentication modes**: Console login or a Beijing-region API Key stored in the workspace.
- **Local document delivery**: Original JSON, Word, Excel, and Markdown are generated together; successful tasks can be exported again locally.

## Who it is for

- Windows users who want Codex to process their recordings.
- Teams that need Chinese names, product terms, and domain vocabulary to be reviewed carefully.
- People who want the original text, timestamps, and speaker information kept in editable files.

## Current scope

- One recording at a time; real-time transcription is not included.
- Windows 10/11 x64 is the validated platform; macOS and Linux are not current acceptance platforms.
- The current Skill delivers a transcription for review. Automatic meeting minutes and feedback learning are planned for a later stage.
- Recognition sends the recording and enabled enhancement content to Alibaba Cloud Model Studio in China (Beijing) and may incur charges.

## Screenshots

<!-- SCREENSHOT: transcription-page
Show the recording, settings, hotwords/context, and output locations.
Suggested file: doc/images/01-transcription-overview.png
-->

<!-- SCREENSHOT: outputs
Show redacted Word, Excel, and Markdown output examples.
Suggested file: doc/images/02-transcription-outputs.png
-->

## Help and contribute

- [Usage guide](skills/asr-transcription/references/usage.md): installation, authentication, page workflow, and upgrades.
- [Troubleshooting](skills/asr-transcription/references/errors.md): installation, login, session, and transcription issues.
- [Report a problem](https://github.com/hx101700/memoflow/issues): include your OS, package, steps, and a redacted error.
- [Discuss a use case](https://github.com/hx101700/memoflow/discussions): share output formats, workflows, and stage-two ideas.
- [Support](SUPPORT.md): choose the right Issue, Discussion, or documentation entry point.
- [Contributing](CONTRIBUTING.md): read this before changing code, docs, or examples.

Never post API keys, login URLs, transcript content, or private local paths in an Issue, Discussion, or screenshot.

## Related links

| Resource | Links |
| --- | --- |
| Alibaba Cloud Model Studio | [Console](https://bailian.console.aliyun.com/) · [Documentation](https://help.aliyun.com/en/model-studio/) |
| BL CLI | [Official site](https://bailian.console.aliyun.com/cli) · [GitHub](https://github.com/modelstudioai/cli) |
| Recognition accuracy | [Hotwords and context](https://help.aliyun.com/en/model-studio/improve-asr-accuracy) |
| MemoFlow | [Releases](https://github.com/hx101700/memoflow/releases/latest) · [Development docs](doc/README.md) |

Licensed under [Apache-2.0](LICENSE).
