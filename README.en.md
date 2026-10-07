# MemoFlow

[中文](README.md) | English

MemoFlow aims to turn recordings into meeting minutes that follow your preferences and requested format, learning from the examples, requirements, and corrections you confirm.

Stage one is currently available as the `asr-transcription` Skill: transcribe one recording in Codex and receive Word, Excel, and Markdown documents to review. It uses the official [BL CLI](https://github.com/modelstudioai/cli) to access [Alibaba Cloud Model Studio](https://help.aliyun.com/en/model-studio/what-is-model-studio), with a local web page for transcription settings.

Clear transcription is the starting point for useful meeting minutes. MemoFlow uses [Qwen-Audio-3.1-ASR-Flash-Filetrans](https://help.aliyun.com/en/model-studio/qwen-audio-3-1-asr-flash-filetrans) for recognition across Chinese dialects, with hotwords and context to help recognize specialized terms. You review the recording and settings on the page; Codex handles execution and delivery. Results stay in files and tools handle document processing, so the conversation can focus on actions, confirmation, and results without repeatedly carrying processing details and the full transcript.

## Features

- **Recording transcription**: Process one audio file, with timestamps and optional speaker diarization.
- **Accuracy enhancement**: Enter hotwords directly or import and edit an Excel list, and add context text. Both can be used together.
- **Visual settings**: Add a recording, adjust options, and choose save locations in your browser, with Chinese and English interfaces and light or dark themes.
- **Document generation**: Create Word, Excel, and Markdown together, keep the original JSON, and export documents again locally.

## Install the Skill

Choose one package from the [v0.1.1 Release](https://github.com/hx101700/memoflow/releases/tag/v0.1.1):

- **asr-transcription.zip (recommended)** includes Python and Node.js runtimes to reduce downloads during initial setup.
- **asr-transcription-lite.zip** downloads the runtimes from official sources during initial setup.

Both packages provide the same features. Initial installation of Python dependencies and BL CLI still requires internet access.

First, [register an Alibaba Cloud account on the China site](https://help.aliyun.com/zh/account/step-1-register-an-alibaba-cloud-account) and follow the [official setup guide (in Chinese)](https://help.aliyun.com/zh/model-studio/first-api-call-to-qwen) to complete account verification and activate Model Studio.

Send the selected ZIP to Codex with this request:

```text
Install this ZIP as the asr-transcription Skill. Read its SKILL.md and prepare the required environment in the current task folder.
```

Windows 10/11 x64 is supported. The installer prepares private Python and Node.js runtimes and dependencies in your workspace without prior installations or system changes. The Skill location holds tools and instructions; your workspace holds the runtime environment, credentials, tasks, and results. It defaults to the current task folder, and you can ask Codex to use another location. See the [usage guide](https://github.com/hx101700/memoflow/blob/master/skills/asr-transcription/references/usage.md) for details.

## Quick start

After installation, tell Codex:

```text
Please transcribe this recording.
```

Attach the recording to your conversation, or choose a file after the page opens. Codex uses the Skill to open the local transcription page; the current development build includes an accessible attachment for you to review. Adjust the audio language and speaker diarization settings, and choose where to save the files. Use the controls at the top right to switch between Chinese and English, or select System, Light, or Dark appearance. For Model Studio authentication, choose:

- **Console login (recommended)**: Authorize access on the official Alibaba Cloud page. BL manages the credentials.
- **API Key**: Select “Use API key” on the transcription page, then enter or update your Model Studio Key for China (Beijing). The Key is saved in the current workspace and used directly for transcription.

<!-- SCREENSHOT: overview
Insert a real transcription-page screenshot showing audio selection, settings, and save locations.
Suggested file: doc/images/01-transcription-overview.png
Caption: Add a recording and adjust the transcription settings. Hide keys and private paths.
-->

To improve recognition of specialized terms, import a hotword list or enter context text. Hotwords identify terms to recognize; context supplies reference text containing those terms. You can use both together.

<!-- SCREENSHOT: enhancement
Insert a real screenshot with hotwords and context enabled together.
Suggested file: doc/images/02-accuracy-enhancement.png
Caption: Provide hotwords and context for recognition. Use public terms and publishable examples.
-->

Choose “Confirm and preview” to check the details; you can return to editing before handing them over. When ready, select “Copy for Codex” and send the copied confirmation message in your conversation. Codex accepts those settings and starts processing. If Console authorization is needed, complete it in your system default browser and reply “done.” Codex waits for recognition and document generation, then provides the files and their locations for your review. Transcription sends the recording and enabled enhancement content to Model Studio in China (Beijing) and may incur charges.

Audio is read from the original attachment or the file selected in the system dialog. Excel hotword lists are parsed in memory. Keep the recording available until transcription finishes; a processed audio file is created only when channel merging is needed.

**Stage two (planned)** will create meeting minutes from reviewed transcripts, document examples, and formatting requirements, then use corrections you confirm to improve later results. The current Skill delivers transcripts for review as a checkable foundation for that work.

## Contributing

[Issues](https://github.com/hx101700/memoflow/issues), feature suggestions, and pull requests are welcome. See the [development documentation](https://github.com/hx101700/memoflow/blob/dev/doc/README.md) for code structure, conventions, and verification. If you find this project helpful, please consider **starring and forking** it, thank you!

## Related links

| Resource | Links |
| --- | --- |
| Alibaba Cloud Model Studio | [Console](https://bailian.console.aliyun.com/) · [Documentation](https://help.aliyun.com/en/model-studio/) |
| BL CLI | [Official site](https://bailian.console.aliyun.com/cli) · [GitHub](https://github.com/modelstudioai/cli) |
| Accuracy enhancement | [Hotwords and context](https://help.aliyun.com/en/model-studio/improve-asr-accuracy) |
| MemoFlow | [Usage guide](https://github.com/hx101700/memoflow/blob/master/skills/asr-transcription/references/usage.md) · [Downloads](https://github.com/hx101700/memoflow/releases) |

Licensed under [Apache-2.0](LICENSE).
