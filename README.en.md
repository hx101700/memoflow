# MemoFlow

[中文](README.md) | English

MemoFlow aims to turn recordings into meeting minutes that follow your preferences and requested format, learning from the examples, requirements, and corrections you confirm.

Stage one is currently available as the `asr-transcription` Skill: transcribe one recording in Codex and receive Word, Excel, and Markdown documents to review. It uses the official [BL CLI](https://github.com/modelstudioai/cli) to access [Alibaba Cloud Model Studio](https://help.aliyun.com/zh/model-studio/what-is-model-studio), with a local web page for transcription settings.

## Features

- **Recording transcription**: Process one audio file, with timestamps and optional speaker diarization.
- **Accuracy enhancement**: Enter hotwords directly or import and edit an Excel list, and add context text. Both can be used together.
- **Visual settings**: Add a recording, adjust options, and choose save locations in your browser, with Chinese and English interfaces and light or dark themes.
- **Document generation**: Create Word, Excel, and Markdown together, keep the original JSON, and export documents again locally.

## Install the Skill

Download the stage-one development preview, `asr-transcription.zip`, from [Releases](https://github.com/hx101700/memoflow/releases).

First, [register an Alibaba Cloud account](https://help.aliyun.com/zh/account/step-1-register-an-alibaba-cloud-account) and follow the [official setup guide](https://help.aliyun.com/zh/model-studio/first-api-call-to-qwen) to complete account verification and activate Model Studio.

Send the distribution package `asr-transcription.zip` to Codex with this request:

```text
Install this ZIP as the asr-transcription Skill. Read its SKILL.md and prepare the required environment in the current task folder.
```

The Skill location holds tools and instructions. Your workspace holds the runtime environment, credentials, tasks, and results. It defaults to the current task folder; you can ask Codex to use another location. Windows 10/11 x64, Python 3.12 x64, and Node.js 18.17+ with npm are required. Initial setup needs internet access. See the [usage guide](https://github.com/hx101700/memoflow/blob/dev/skills/asr-transcription/references/usage.md) for details.

## Quick start

After installation, tell Codex:

```text
Please transcribe this recording.
```

Codex uses the Skill to open the local transcription page. Add a recording, adjust the audio language and speaker diarization settings, and choose where to save the files. Use the controls at the top right to switch between Chinese and English, or select System, Light, or Dark appearance. For Model Studio authentication, choose:

- **Console login (recommended)**: Authorize access on the official Alibaba Cloud page. BL manages the credentials.
- **API Key**: Select “Use a standard API Key” on the transcription page, then enter or update your Model Studio Key for China (Beijing). Your API Key is saved in the current workspace.

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

Audio is selected in the system file dialog and read from its original path. Excel hotword lists are parsed in memory. Keep the recording available until transcription finishes; a processed audio file is created only when channel merging is needed.

**Stage two (planned)** will create meeting minutes from reviewed transcripts, document examples, and formatting requirements, then use corrections you confirm to improve later results. Preference storage and feedback adoption will be designed in that stage. The current Skill delivers transcripts for review.

## Contributing

[Issues](https://github.com/hx101700/memoflow/issues), feature suggestions, and pull requests are welcome. See the [development documentation](https://github.com/hx101700/memoflow/blob/dev/doc/README.md) for code structure, conventions, and verification. If you find this project helpful, please consider **starring and forking** it, thank you!

## Related links

| Resource | Links |
| --- | --- |
| Alibaba Cloud Model Studio | [Console](https://bailian.console.aliyun.com/) · [Documentation](https://help.aliyun.com/zh/model-studio/) |
| BL CLI | [Official site](https://bailian.console.aliyun.com/cli) · [GitHub](https://github.com/modelstudioai/cli) |
| Accuracy enhancement | [Hotwords and context](https://help.aliyun.com/zh/model-studio/improve-asr-accuracy) |
| MemoFlow | [Usage guide](https://github.com/hx101700/memoflow/blob/dev/skills/asr-transcription/references/usage.md) · [Downloads](https://github.com/hx101700/memoflow/releases) |

Licensed under [Apache-2.0](LICENSE).
