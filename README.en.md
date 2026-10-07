# MemoFlow

[中文](README.md) | English

> MemoFlow is an interactive Codex Skill for audio transcription and personalized meeting minutes.

[![Latest release](https://img.shields.io/github/v/release/hx101700/memoflow?display_name=tag&sort=semver)](https://github.com/hx101700/memoflow/releases/latest) [![License](https://img.shields.io/github/license/hx101700/memoflow)](LICENSE) [![Windows](https://img.shields.io/badge/Windows-10%2F11%20x64-0078D4)](https://github.com/hx101700/memoflow/releases/latest)

MemoFlow is designed for meetings, interviews, training, and customer conversations. On the local web page, you choose a recording, recognition language, speaker diarization, hotwords, context, and output location. After you confirm the settings, Codex runs Alibaba Cloud Model Studio's [Qwen-Audio-3.1-ASR-Flash-Filetrans](https://help.aliyun.com/en/model-studio/qwen-audio-3-1-asr-flash-filetrans) and prepares reviewable documents in the formats you need.

Stage one is available now: recording setup, non-real-time transcription, accuracy enhancement, speaker diarization, and document delivery. In the next stage, MemoFlow will learn from reviewed transcripts, formatting examples, and confirmed feedback to produce meeting minutes that match each user's working style.

## Why MemoFlow

A recording does not become useful information by itself. People still need to:

- find important sections in a long recording without replaying everything;
- recognize names, product names, and domain vocabulary correctly;
- understand who said what in a multi-speaker discussion;
- review the text and continue working in a familiar format;
- keep authentication, configuration, transcription, and file delivery in one workflow.

MemoFlow turns recordings from meetings, interviews, training sessions, and customer conversations into text that can be revisited and reviewed. It keeps timestamps, speaker information, and important terminology so users can continue shaping the reviewed content into their own meeting minutes.

## Why Codex + Qwen-Audio 3.1

Codex is strong at understanding context, organizing multi-step work, reading files, and continuing a user-defined workflow. Speech recognition itself is not its core capability. Many general-purpose workflows start with [Whisper](https://github.com/openai/whisper). Whisper is a strong general multilingual model, and its official documentation notes that performance varies by language. For meetings with dialects, names, product terms, speaker labels, and context, a general transcript can still leave substantial review work.

MemoFlow gives recognition to Qwen-Audio 3.1 and workflow coordination and delivery to Codex. Within this project's scope, that combination addresses unclear speech, missed terminology, hard-to-follow multi-speaker content, and transcripts that are difficult to continue processing: Qwen handles file recognition, while Codex connects authentication, web review, file saving, and follow-up work.

- **Qwen-Audio-3.1-ASR-Flash-Filetrans** performs non-real-time recognition across the model's supported languages and dialects. Alibaba Cloud documents speaker diarization, hotword enhancement, and context enhancement for this model. See the [ASR model overview](https://help.aliyun.com/zh/model-studio/asr-model).
- **Codex** prepares the Skill environment, opens the configuration page, carries conversation attachments into the page, guides authentication, waits for Model Studio, and delivers the result.
- **MemoFlow** keeps the full transcript in files while the conversation carries actions, confirmation, and result locations, creating a foundation for personalized meeting minutes.

For specialized vocabulary, MemoFlow uses Alibaba Cloud's request-level hotwords and context enhancement. Hotwords fit temporary names, products, and terms; context supplies meeting background or domain text. Both can be sent in the same request. See the [official accuracy guide](https://help.aliyun.com/en/model-studio/improve-asr-accuracy).

## First use

The first run depends on network access, environment setup, and recording length. MemoFlow does not promise a fixed completion time:

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
6. Codex handles authentication, transcription, and document delivery for the same task.

The full package includes Python and Node.js runtimes. The lite package is smaller and downloads those runtimes from official sources during setup. Both packages support Windows 10/11 x64; Python dependencies and the BL CLI still require internet access.

Before using MemoFlow, [create an Alibaba Cloud account](https://help.aliyun.com/zh/account/step-1-register-an-alibaba-cloud-account) and follow the [Model Studio setup guide](https://help.aliyun.com/en/model-studio/first-api-call-to-qwen).

## After transcription

MemoFlow keeps the original result returned by Model Studio and creates three review documents from the same transcription, so you can read, filter, edit, and archive the result in the format that fits your work.

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
| Recognition accuracy | [Hotwords and context](https://help.aliyun.com/en/model-studio/improve-asr-accuracy) |
| MemoFlow | [Releases](https://github.com/hx101700/memoflow/releases/latest) · [Development docs](doc/README.md) |

Licensed under [Apache-2.0](LICENSE).
