[中文](https://github.com/hx101700/memoflow/blob/v0.1.2/release/NOTES.md) | English

# MemoFlow v0.1.2

MemoFlow v0.1.2 keeps the private runtime setup from v0.1.1 and connects “attach a recording and ask Codex to transcribe it” to the same browser configuration flow. When Codex can access the local attachment path, the recording is brought into the page for review before Codex calls Alibaba Cloud Model Studio.

### What changed

- **Conversation attachments enter the form**: When a local attachment path is available, Codex preselects the recording in the transcription page. If the path cannot be read, the page explains the problem in the audio section and lets you choose another file.
- **A clear handoff flow**: The page remains two steps: fill in the settings, then preview them. An immutable task is created only after the user copies the confirmation message containing `session_id` back to Codex.
- **A cleaner enhancement section**: Removed redundant explanatory text while keeping hotword and context input, the official Alibaba Cloud links, and the existing table validation.
- **Synchronized login guidance**: The fixed BL login entry point, Windows desktop permission requirement, and browser handoff now match the implementation and the documented upstream behavior.
- **Updated packages**: The full and lite packages contain this version of the static page, Skill instructions, bilingual README, and runtime code.

### Download and install

| Package | Which one to choose |
| --- | --- |
| **[asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.2/asr-transcription.zip)** | Recommended. Includes Python and Node.js, avoiding separate runtime downloads during setup. |
| **[asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.2/asr-transcription-lite.zip)** | A smaller initial download. Setup obtains the runtimes from their official sources. |

Both packages support Windows 10/11 x64. Initial installation of Python dependencies and the BL CLI still requires internet access; the full package is not fully offline.

Send either ZIP to Codex with this request:

> Install this ZIP as the asr-transcription Skill, read its SKILL.md, and prepare the required environment in the current task folder.

Prepare your Alibaba Cloud account and enable Model Studio before use. After installation, ask Codex to transcribe a recording, follow the page, review the preview, and copy the confirmation message back to the conversation. See the [README](https://github.com/hx101700/memoflow/blob/v0.1.2/README.en.md) for details.

The current version delivers the original JSON plus Word, Excel, and Markdown transcription documents. Personalized content generation and feedback learning remain planned for a later stage.

### Upgrading from an earlier version

Wait for running tasks to finish, replace the installed `asr-transcription` Skill with this ZIP, and run the Skill's `scripts/bootstrap.ps1 -Workspace` in the original workspace. The installer reuses valid private Python and Node runtimes, the virtual environment, the BL CLI, credentials, tasks, and results.

If setup reports that the virtual environment is bound to another Python installation, finish tasks using that environment, delete only `WORKSPACE/.asr-transcription/.venv`, and run bootstrap again. Keep `.env`, `.state`, `.tools`, and output folders. Do not delete the entire `.asr-transcription` directory.

Please report problems through [Issues](https://github.com/hx101700/memoflow/issues), including your environment, error messages, and reproduction steps. Remove API keys, login links, and private recordings before posting.
