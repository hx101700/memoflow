[中文](https://github.com/hx101700/memoflow/blob/v0.1.0/release/NOTES.md) | English

MemoFlow aims to turn recordings into meeting minutes that follow your preferred style and format. This v0.1.0 development preview delivers the first step: transcribe a recording in Codex and receive timestamped Word, Excel, and Markdown documents to review and correct.

### Features

- **Edit and review in your browser**: Add a recording and choose its language, speaker diarization, and save locations. Return to editing as needed before handing the settings to Codex.
- **Hotwords and context**: Enter hotwords directly or import an Excel list and edit it in place. Hotwords and context are checked when you select “Confirm and preview,” with problems shown next to the relevant input. Editing does not trigger content checks.
- **Model Studio recognition**: Call Qwen-Audio-3.1-ASR-Flash-Filetrans through the official BL CLI, using Console authorization or your Beijing-region API Key.
- **Three document formats**: Generate Word, Excel, and Markdown together and retain the original JSON. Successful tasks can be re-exported locally.
- **Language and appearance**: Choose Chinese or English and light or dark themes.

Audio is selected in the system file dialog and read from its original path. Excel hotword lists are parsed in memory. Keep the recording available until transcription finishes; a processed audio file is created only when channel merging is needed.

### From settings to delivery

Select “Confirm and preview” on the page, check the details, then use “Copy for Codex” to send the confirmation message back to your conversation. Codex accepts those settings, guides a login if needed, and waits for transcription and document generation to finish. Handed-off settings are fixed; follow the results in Codex.

The editing page is valid for two hours after opening and shows a final message after handoff or expiry. This deadline does not affect tasks already handed to Codex.

If the service closes unexpectedly, opening the transcription page again in the same workspace checks for temporary files belonging to completed operations and reclaims those it can safely identify. Handed-off tasks, saved credentials, and results remain intact. Files without clear ownership remain untouched, and incomplete cleanup is reported. Recognition is never resubmitted automatically.

### Get started

Create an Alibaba Cloud account and complete the platform's identity verification and Model Studio setup. Download [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.0/asr-transcription.zip) and send it to Codex with this request:

> Extract the ZIP, read its SKILL.md, and help me install and configure asr-transcription.

After installation, ask Codex to transcribe a recording and follow the page it opens. The package also includes the latest Chinese and English README files.

This preview supports Windows 10/11 x64 and requires Python 3.12 x64, Node.js 18.17+, and npm. Recognition uses Model Studio in China (Beijing) and may incur charges. Personalized meeting minutes and learning from feedback are planned for a later stage.

See the [README](https://github.com/hx101700/memoflow/blob/v0.1.0/README.en.md) for details, or share problems and suggestions through [Issues](https://github.com/hx101700/memoflow/issues).
