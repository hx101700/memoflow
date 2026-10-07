# Contributing to MemoFlow

MemoFlow is currently focused on one workflow: a Windows Codex Skill that turns one recording into reviewable Word, Excel, Markdown, and JSON files.

## Before opening an issue

- Search existing Issues and Discussions.
- Use a short title that describes the user-visible problem.
- Include Windows version, package (`asr-transcription` or `asr-transcription-lite`), and the exact step that failed.
- Remove API keys, login URLs, recording content, local usernames, and private paths.

## Good first contributions

- Improve a user-facing explanation or translation.
- Add a redacted screenshot or a reproducible UI test.
- Clarify an installation or troubleshooting step.
- Add a focused issue with a small, testable proposal.

## Pull requests

1. Explain the user problem and the resulting behavior.
2. Keep the change focused; avoid speculative compatibility layers and unrelated refactors.
3. Update the relevant README, Skill reference, or development document when behavior changes.
4. Run the narrowest relevant checks and report exactly what was run.
5. Do not commit credentials, recordings, generated results, private logs, or local runtime directories.

The `dev` branch is for development. Formal releases are made from `master` after review. See [doc/README.md](doc/README.md) for repository maintenance guidance.
