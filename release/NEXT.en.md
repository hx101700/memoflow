# Release writing conventions

Keep “What's new”, “Downloads”, and “Installation and updates” in each release. Link between languages through NOTES.md/NOTES.en.md under that version tag.

- Explain concrete user benefits, such as fewer repeated downloads, clearer diagnosis, or less space used by old caches. Support speed and stability claims with a relevant change or evidence.
- Cover first installation, ZIP upgrades, and automatic updates. Identify earlier versions with links, the current version, and which subsequent higher formal versions users can obtain.
- The update entry point starts with v0.1.2. Users of v0.1.0/v0.1.1 first update using a ZIP. Future notes must retain this boundary and explain that v0.1.2 and later users can update through Codex to the release being published.
- Use “this release” only for the version being published. Explain the choice of Codex updates or a new ZIP, and keep development acceptance records out of release notes.

Replace `__RELEASE_TAG__` in the download links below with the formal version tag when publishing.

| Package | Description |
| --- | --- |
| **Full package (recommended manual download for first installation) · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/__RELEASE_TAG__/asr-transcription.zip)** | Includes Python, Node.js, and the bundled npm to prepare the base environment during initial installation. |
| **Lite package (updates, downloaded automatically by Codex) · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/__RELEASE_TAG__/asr-transcription-lite.zip)** | Reuses the installed Python, Node.js, and npm for subsequent Skill updates. |
