[中文](https://github.com/hx101700/memoflow/blob/v0.1.1/release/NOTES.md) | English

MemoFlow v0.1.1 makes first-time setup simpler. You no longer need to configure Python and Node.js beforehand: Codex follows the Skill instructions to prepare a private environment in your workspace. Existing Python and Node installations and other projects remain unchanged.

### What changed

- **Private runtimes**: Python, Node.js, the BL CLI, and dependencies are installed inside the workspace to reduce version and PATH conflicts.
- **Two package options**: The full package includes official Python and Node archives verified against their published checksums. The lite package downloads the same runtimes during setup. Both contain the same Skill code and instructions.
- **Recovery and diagnostics**: The lite installer keeps partial runtime downloads for resumption. Existing environments are checked for the correct base Python; outdated bindings or moved paths produce actionable instructions while preserving data.
- **Chinese paths**: Fixed garbled Chinese text in pip setup logs, including workspace paths containing spaces.

The transcription workflow stays the same: add a recording and configure hotwords and context in the browser, preview the settings, then send the confirmation message to Codex. Codex calls Model Studio and delivers Word, Excel, Markdown, and the original JSON.

### Download and install

| Package | Which one to choose |
| --- | --- |
| **[asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.1/asr-transcription.zip)** | Recommended. Includes Python and Node.js, avoiding separate runtime downloads during setup. |
| **[asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.1/asr-transcription-lite.zip)** | A smaller initial download. Setup obtains the runtimes from their official sources. |

Both packages support Windows 10/11 x64 and still need an internet connection to install Python dependencies and the BL CLI. The full package is not a fully offline installer.

Send either ZIP to Codex with this request:

> Install this ZIP as the asr-transcription Skill, read its SKILL.md, and prepare the runtime environment in the current task folder.

Prepare your Alibaba Cloud account and enable Model Studio before use. After installation, ask Codex to transcribe a recording and follow the page it opens. See the [README](https://github.com/hx101700/memoflow/blob/v0.1.1/README.en.md) for details.

### Upgrading

Wait for any running task to finish before replacing the Skill. If the workspace virtual environment still depends on system Python, follow the setup message to recreate only `.asr-transcription/.venv`. Keep credentials, tasks, and transcription results; do not delete the entire workspace.

Please report problems through [Issues](https://github.com/hx101700/memoflow/issues), including your environment, error messages, and reproduction steps. Remove API keys and private recording content before posting.
