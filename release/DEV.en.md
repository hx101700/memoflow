[中文](https://github.com/hx101700/memoflow/blob/dev-runtime/release/DEV.md) | English

This development preview makes MemoFlow easier to set up. Python and Node.js are prepared inside your workspace, so you do not need to install them first or change the versions already on your computer. Recording transcription, browser settings, and document generation work as before.

### Choose a package

| Package | Which one to choose |
| --- | --- |
| **[asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/dev-runtime/asr-transcription.zip)** | Recommended. Includes the official Windows x64 Python and Node.js archives, avoiding separate runtime downloads during setup. |
| **[asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/dev-runtime/asr-transcription-lite.zip)** | A smaller initial download. Setup downloads the same runtimes from their official sources. |

Both packages contain the same Skill code and instructions. The full package still needs an internet connection to install Python dependencies and the BL CLI; it is not a fully offline installer. Setup verifies the official runtime checksums and uses executables in your workspace to avoid conflicts with system versions and PATH settings.

### Get started

Send either ZIP to Codex with this request:

> Install this ZIP as the asr-transcription Skill, read its SKILL.md, and prepare the runtime environment in the current task folder.

Once your Alibaba Cloud account and Model Studio service are ready, ask Codex to transcribe a recording and follow the page it opens. Windows 10/11 x64 is supported. See the [README](https://github.com/hx101700/memoflow/blob/dev-runtime/README.en.md) for instructions.

This is a development preview from `dev`. The formal v0.1.0 release and your installed Skill remain unchanged. Finish any running task before replacing the Skill. If an existing workspace still depends on a system Python installation, follow the setup message to recreate only its virtual environment, retaining credentials, tasks, and results.

Please share installation details, error messages, and reproduction steps through [Issues](https://github.com/hx101700/memoflow/issues). Remove API keys and private recording content before posting.
