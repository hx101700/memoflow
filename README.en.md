# MemoFlow

[中文](README.md) | English

> Give Codex a recording in a supported language: first make it clear and accurate, then turn it into a transcript that can become your own meeting minutes.

[![Latest release](https://img.shields.io/github/v/release/hx101700/memoflow?display_name=tag&sort=semver)](https://github.com/hx101700/memoflow/releases/latest) [![License](https://img.shields.io/github/license/hx101700/memoflow)](LICENSE) [![Windows](https://img.shields.io/badge/Windows-10%2F11%20x64-0078D4)](https://github.com/hx101700/memoflow/releases/latest)

MemoFlow's long-term goal is to turn meeting audio, context, corrections, and formatting preferences into meeting minutes that follow each user's working style. It will learn from examples and confirmed edits so repeated work becomes more consistent.

Stage one is available now as the `asr-transcription` Skill. It uses Alibaba Cloud Model Studio's [Qwen-Audio-3.1-ASR-Flash-Filetrans](https://help.aliyun.com/en/model-studio/qwen-audio-3-1-asr-flash-filetrans), which supports the model's multilingual and dialect coverage. Chinese meetings, names, and specialized terms are the current primary use case. A local web page lets you review the recording, recognition settings, hotwords, context, and output locations before Codex runs one non-real-time transcription.

## Why MemoFlow

A recording does not become useful information by itself. People still need to:

- find important sections in a long recording without replaying everything;
- recognize names, product names, and domain vocabulary correctly;
- understand who said what in a multi-speaker discussion;
- review the text and continue working in a familiar document format;
- keep authentication, configuration, transcription, and file delivery in one understandable workflow.

[Tongyi Tingwu](https://help.aliyun.com/zh/tingwu/what-is-tingwu) describes a similar direction: record and “read” audio and video through transcription, speaker separation, summaries, and focused navigation. MemoFlow starts with the foundation of that experience: Codex helps configure the recording and deliver a reviewable transcript, while Qwen-Audio 3.1 performs the file recognition.

## Why Codex + Qwen-Audio 3.1

The two parts have different responsibilities.

- **Qwen-Audio-3.1-ASR-Flash-Filetrans** performs non-real-time file recognition across the model's supported languages and dialects. Alibaba Cloud documents it for long audio files with speaker diarization, hotword enhancement, and context enhancement; its model overview lists up to 12 hours and 2 GB per file, with shorter recordings recommended when diarization is enabled. See the [ASR model overview](https://help.aliyun.com/zh/model-studio/asr-model).
- **Codex** handles the local workflow: preparing the Skill, opening the configuration page, carrying a conversation attachment into the page, guiding authentication, waiting for Model Studio, and delivering files.
- **MemoFlow** connects the two: the full transcript stays in files, while the conversation carries actions, confirmation, and result locations. That leaves a clean foundation for the personalized meeting-minutes stage.

For specialized vocabulary, MemoFlow uses Alibaba Cloud's request-level hotwords and context enhancement. Hotwords fit temporary names, products, and terms; context supplies meeting background or domain text. Both can be sent in the same request. See the [official accuracy guide](https://help.aliyun.com/en/model-studio/improve-asr-accuracy).

## First use

The first run depends on network access, environment setup, and recording length, so MemoFlow does not promise a fixed “30-second” completion time:

1. Download the [v0.1.2 package](https://github.com/hx101700/memoflow/releases/tag/v0.1.2).
2. Send the ZIP to Codex with:

   ```text
   Install this ZIP as the asr-transcription Skill. Read its SKILL.md and prepare the required environment in the current task folder.
   ```

3. After setup, tell Codex:

   ```text
   Please transcribe this recording.
   ```

4. Review the recording, language, diarization, hotwords, context, and output locations in the page.
5. Choose “Confirm and preview”, then “Copy for Codex” and send the confirmation message back to the conversation.
6. Codex handles the selected authentication path, waits for transcription, and delivers the result.

The full package includes Python and Node.js runtimes. The lite package is smaller and downloads those runtimes from official sources during setup. Both packages support Windows 10/11 x64; Python dependencies and the BL CLI still require internet access.

Before using MemoFlow, [create an Alibaba Cloud account](https://help.aliyun.com/zh/account/step-1-register-an-alibaba-cloud-account) and follow the [Model Studio setup guide](https://help.aliyun.com/en/model-studio/first-api-call-to-qwen).

## After transcription

MemoFlow keeps the original JSON returned by Model Studio and creates three review documents from that same transcription, so you can read, filter, edit, and archive the result in the format that fits your work.

<!-- SCREENSHOT: hero
Add a real screenshot or 20–40 second GIF showing “add recording → preview → copy for Codex”.
Suggested file: doc/images/memoflow-demo.gif
Hide API keys, usernames, local paths, and real meeting content.
-->

<!-- SCREENSHOT: outputs
Add redacted Word, Excel, and Markdown screenshots showing different ways to review the same transcription.
Suggested file: doc/images/02-transcription-outputs.png
-->

## Current scope

- One recording at a time; real-time transcription is not included.
- Supported model languages and dialects, conversation attachments, local file selection, hotwords, context, and speaker diarization are supported.
- Windows 10/11 x64 is the validated platform; macOS and Linux are not current acceptance platforms.
- The current Skill delivers a reviewable transcript. Automatic meeting minutes, user-style learning, and a feedback loop belong to stage two.
- Recognition sends the recording and enabled enhancement content to Alibaba Cloud Model Studio in China (Beijing) and may incur charges.

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
| Tongyi Tingwu | [Product overview](https://help.aliyun.com/zh/tingwu/what-is-tingwu) |
| Recognition accuracy | [Hotwords and context](https://help.aliyun.com/en/model-studio/improve-asr-accuracy) |
| MemoFlow | [Releases](https://github.com/hx101700/memoflow/releases/latest) · [Development docs](doc/README.md) |

Licensed under [Apache-2.0](LICENSE).
