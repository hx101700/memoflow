# Release 文案约定

每版保留“更新内容”“下载”“安装与更新”，中英文通过该版本标签下的NOTES.md/NOTES.en.md切换。

- 从用户视角说明具体收益，例如减少重复下载、便于定位环境问题或减少旧缓存占用；提速和稳定性结论须有对应改动或证据。
- “安装与更新”同时覆盖首次安装、旧版ZIP升级与自动更新。明确旧版本及链接、当前版本，以及可以获取的后续更高正式版本。
- 自动更新入口从v0.1.2起提供。v0.1.0/v0.1.1先用ZIP更新；后续版本须保留此边界，并说明v0.1.2及以上用户可通过Codex更新到当次正式版。
- 只有本次发布的版本可标注“即当前版本”。说明用户可选择Codex自动更新或提供新ZIP；不把发布文案写成开发验收记录。

发布时将下方链接中的 `__RELEASE_TAG__` 替换为本次正式版本标签。

| 安装包 | 说明 |
| --- | --- |
| **完整包（首次安装推荐手动下载该发行包） · [asr-transcription.zip](https://github.com/hx101700/memoflow/releases/download/__RELEASE_TAG__/asr-transcription.zip)** | 附带 Python、Node.js 和配套 npm，用于首次安装时准备基础运行环境。 |
| **轻量包（更新时使用，由 Codex 自动下载） · [asr-transcription-lite.zip](https://github.com/hx101700/memoflow/releases/download/__RELEASE_TAG__/asr-transcription-lite.zip)** | 复用已安装的 Python、Node.js 和 npm，适合后续更新。 |
