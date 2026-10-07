[中文](https://github.com/hx101700/memoflow/blob/v0.1.0/release/NOTES.md) | English

# MemoFlow v0.1.0

MemoFlow v0.1.0 is the first public release. It delivers the first stage of the project: turning a recording into a transcription that can be reviewed and continued. It connects Codex task orchestration, Alibaba Cloud Model Studio speech recognition, and a local configuration page so users can review the settings before handing the task back to Codex.

### Included in this release

- **Interactive transcription page**: choose a recording, adjust recognition settings, and review the configuration before submission.
- **Conversation attachment entry**: start with a recording attached to Codex and follow the same configuration and confirmation flow.
- **Recognition enhancements**: speaker diarization, hotwords, and context enhancement through Qwen-Audio-3.1-ASR-Flash-Filetrans for non-real-time file transcription.
- **Task handoff**: the confirmation message carries a `session_id`; settings become fixed when handed to Codex, so the full transcript does not have to travel through the conversation repeatedly.
- **Bilingual materials and two packages**: English and Chinese READMEs, plus a full package with runtimes and a smaller lite package.

### Downloads

| Package | Choose it when |
| --- | --- |
| **Full · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.0/asr-transcription.zip)** | You want Python and Node.js included to reduce the first-run downloads. |
| **Lite · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/v0.1.0/asr-transcription-lite.zip)** | You prefer a smaller initial download and can obtain the runtimes from their official sources during setup. |

Both packages contain the same Skill and runtime code. The only difference is whether the Python and Node.js runtime archives are included.

See the [README](https://github.com/hx101700/memoflow/blob/v0.1.0/README.en.md) for the project introduction and usage entry point. Please report problems through [Issues](https://github.com/hx101700/memoflow/issues).
