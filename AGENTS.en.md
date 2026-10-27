# MemoFlow development rules

[中文](AGENTS.md) | English

This file governs source maintenance. Runtime guidance lives in [SKILL.md](skills/asr-transcription/SKILL.md); the current development checkpoint is in [doc/STATUS.md](doc/STATUS.md).

## Resume development

1. Read this file, the [documentation index](doc/README.md), and STATUS to establish the current objective, unfinished work, and authorization scope.
2. Check the branch, `git status`, relevant diff, and recent commits. Treat existing working-tree changes as user-owned.
3. Read the implementation, tests, [development guide](doc/DEVELOPMENT.md), and evidence relevant to the task. Historical test counts do not validate current changes.
4. Before interruption or compaction, record the objective, completed changes, unverified work, next step, and necessary non-sensitive paths in STATUS. Include reproducible commands and prerequisites rather than only “tests passed.”

Source, configuration, and observed behavior take precedence over prose. Correct conflicting documentation; do not reconstruct reasons from conversation memory. STATUS contains one current checkpoint; DEVLOG and ACCEPTANCE preserve facts from their recorded dates.

## Product and business boundaries

- Stage one delivers one `asr-transcription` Skill: configure and preview a single recorded audio file locally, let Codex call Bailian CLI (BL), and deliver original JSON plus Word, Excel, and Markdown transcript drafts. Personalized minutes and feedback-based learning are planned for a later stage.
- Support Windows 10/11 x64 with private Python, Node.js, and npm in the workspace. Initial installation uses the full package; normal updates use the lite package and reuse runtimes. Versions and sources come from `scripts/runtimes.json`, dependency locks, and source constants.
- Use `qwen-audio-3.1-asr-flash-filetrans`, Beijing, and temporary OSS. Hotwords and context can be combined; speaker diarization starts enabled. When multichannel audio needs mixing, show the requirement before creating a mono FLAC copy and preserve the original.
- BL owns authentication, browser authorization, upload, submission, polling, and original JSON writing. Python owns local interaction, media preparation, result parsing, and document generation. Check the pinned official implementation before changing this boundary and reuse its capabilities directly.
- The page has editing and preview steps. A user-sent confirmation containing `session_id` hands the session off to an immutable `job_id`; the confirmation ID comes from the current user's message. Cancellation uses the known active page ID: cancel, obtain the result, and wait for the original server to exit. Editing cancellation does not cancel a cloud task.
- Each job gets one execution attempt. Preserve records on failure or unknown cloud outcomes and do not automatically resubmit. Retain original login/transcription processes for subsequent waiting. Deliver from actual receipts; all three documents require `delivery.status=COMPLETE` and `documents_ready=true`.
- Read the original audio and parse Excel in memory. Validate hotwords and context on Confirm and preview. Language changes preserve inputs and diagnostics; disabling an enhancement clears that section, while credentials remain independent.

[DEVELOPMENT](doc/DEVELOPMENT.md) owns protocol details and design reasons; Skill references own operational and recovery procedures. Keep business constraints here without repeating the full workflow.

## Code and comments

- Keep the lightweight entry → application → utils structure. Entries dispatch commands, use cases organize order and state, and utilities perform independent I/O. Rules perform no I/O; utilities do not import use cases. Shared contracts live in `models.py` and frontend `types.ts`.
- A new check, state, abstraction, or dependency needs a current requirement and consumer. Reuse existing functions and public third-party capabilities. Avoid compatibility layers, generic frameworks, or retries for theoretical scenarios.
- Give Python explicit types. Use Vue 3, TypeScript, and Element Plus on the frontend, preferring public component props and default interaction. Style customization needs a concrete product requirement.
- Every named function or method gets a concise Chinese responsibility statement describing its action and result: Python docstrings and TypeScript function comments. Additional comments explain constraints, reasons, or non-obvious behavior instead of repeating code or narrating edits.
- Use consistent domain terms: editing session, transcription job, preview, handoff, transcription, transcript draft, and minutes. Distinguish `session_id` from `job_id`, and execution status from delivery status. Optional fields must genuinely allow absence.
- Use argument arrays and `shell=False`. Pass hotword JSON and context as individual values and treat file content as data.
- Keep changes focused. Avoid incidental full-file formatting, architectural rewrites, or component replacements. When removing unused code, check its types, tests, documentation, and distribution list.

## Files and permissions

- Modify only this repository and explicitly approved locations. Preserve existing changes, original recordings, and user outputs. Source maintenance does not automatically replace an installed Skill.
- Separate Skill resources from user workspaces. Business commands read Skill resources; environments, credentials, temporary files, jobs, and outputs belong in the workspace. Managed updater replacement and state files are explicit exceptions.
- The page saves API Keys to the workspace's fixed `.env`; execution reads them there. Keys, tokens, signed URLs, real recordings, transcript text, and runtime logs stay out of Git, release packages, and chat.
- Windows installation, login, and native dialogs require normal network/interactive-desktop permissions. Use the tool permission mechanism and report actual restrictions. Keep global environments unchanged, avoid enumerating or terminating unrelated processes, and keep cleanup within its defined scope.

## Changes and verification

- Read callers and callees; establish the trigger and impact before fixing a problem. Use the smallest reliable verification and relevant regression checks. Search locates code; complete implementation and behavior support conclusions.
- Commands and environment prerequisites live in [Development and verification](doc/DEVELOPMENT.md#开发与验证). Local fixtures do not establish real user authorization or cloud recognition acceptance. Record unverified scope explicitly.
- Update STATUS for current state; append important decisions to DEVLOG and actual checks to ACCEPTANCE; keep unresolved issues in ISSUES. Maintain user operations in `references/usage.md`, recovery in `references/errors.md`, and external specifications/evidence in `references/model.md`.
- Update affected UML sources and images when calls, objects, or states change. Use the tracked renderer and shared theme. Draw function modules as lifelines and real objects as classes; notes should support understanding the relationships.
- Keep Chinese/English README and AGENTS equivalent. Preserve the user's product narrative and existing screenshots; label illustrative images. Current guidance excludes replaced implementations, while historical records retain their original facts.

## Git and releases

- Develop on `dev`; accepted milestones enter `master`. Commits, pushes, merges, releases, and replacement of tags/assets need explicit intent. A completed publication authorization does not authorize new work. Stage exact paths and stop after two network push failures.
- Increment the project version only for an accepted release, using root `package.json` as the authority; synchronize locks, the tag, and Release notes. Preserve prior tags/assets in normal releases. Reissuing the same version needs explicit authorization and a clear manual-update boundary.
- `scripts/build_zip.py` owns the fixed distribution list. Both packages use the same runtime code and latest repository READMEs. The full package includes official runtime archives; the lite package serves updates. Exclude AGENTS, development docs, UML, tests, installed environments, and user data.
- Build frontend source in `frontend/` into the Skill's `scripts/asr_runtime/static/`. Update generated assets through that build. Add new runtime files to the distribution list and maintain dependency locks with their package managers.
- Follow the [Release conventions](release/NEXT.en.md): describe observable user benefits, downloads, and exact installation/update version boundaries. Keep installation tutorials, validation records, and digests in their respective documentation.
