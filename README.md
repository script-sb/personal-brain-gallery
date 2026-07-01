# GitHub-First Local Brain

This workspace is a first runnable scaffold for a GitHub-driven local brain. It does not blindly install every hot AI project. Instead, it records candidates, ranks them by role, mirrors source only when useful, and exposes a small local control plane for memory, context search, GitHub registry review, and future tool integrations.

## What Is Implemented

- `registry/projects.json`: GitHub registry for the original hot AI/Agent projects plus a personal assistant framework collection.
- `registry/priority-matrix.md`: integration priority and rationale.
- `docs/index.html`: public Personal Brain Gallery entry for GitHub Pages.
- `docs/personal-brain-exhibits.json` and `docs/brain-dashboard-data.json`: read-only public gallery data.
- `docs/product-spec.md`: product positioning, current state, roadmap, risks, and update process.
- `docs/中文产品使用说明.md`: Chinese user guide for day-to-day operation and future iteration.
- `brain_core`: a standard-library CLI for the local brain control plane.
- `data/brain.sqlite`: created on first use for memories and run logs.
- `third_party/`: intended location for GitHub mirrors.
- `brain-memory`, `brain-context`, `brain-tools`, `brain-skills`, `brain-core`: subsystem folders matching the plan.
- `video` CLI commands: parse video links into structured local notes.

## Quick Start

```bash
python3 -m brain_core status
python3 -m brain_core registry list
python3 -m brain_core registry matrix
python3 -m brain_core memory add "I prefer confirm-before-write automation." --tags preference,safety
python3 -m brain_core memory search confirm
python3 -m brain_core douyin inspect "https://v.douyin.com/..."
python3 -m brain_core douyin cookie-status
python3 -m brain_core github mirror-plan --status integrate
python3 -m brain_core workflow local-task "Summarize the current local brain state" --query "Local Brain"
python3 -m brain_core runs list
python3 -m brain_core funds profile --years 10 --risk 3
python3 -m brain_core video analyze "https://v.douyin.com/..." --memory
python3 -m brain_core video list
python3 -m brain_core video show 1
python3 -m brain_core video report 1 --target "local-brain"
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

## Publish The Gallery With GitHub + Tencent COS

The public gallery is intentionally kept as a static site under `docs/`. GitHub stores the source and runs the deploy workflow; Tencent Cloud COS serves the China-friendly public site:

- source page for local iteration: `workspace/personal-brain-gallery.html`
- public page for Tencent COS: `docs/index.html`
- public data snapshots: `docs/personal-brain-exhibits.json`, `docs/brain-dashboard-data.json`

After editing the workspace version, refresh the public snapshot:

```bash
cp workspace/personal-brain-gallery.html docs/index.html
cp workspace/personal-brain-exhibits.json docs/personal-brain-exhibits.json
cp workspace/brain-dashboard-data.json docs/brain-dashboard-data.json
```

Then commit and push to GitHub. In the repository settings, enable GitHub Pages with:

- add GitHub Actions secrets `TENCENT_CLOUD_SECRET_ID` and `TENCENT_CLOUD_SECRET_KEY`;
- push to `main`;
- GitHub Actions will upload `docs/` to COS bucket `personal-brain-gallery-1441292354` in `ap-guangzhou`.

Deployment details are tracked in `docs/tencent-cos-github-deploy.md`.

## Video Reading MVP

Turn a video link into a structured note:

```bash
python3 -m brain_core video analyze "https://v.douyin.com/..." --memory
```

What it does:

- uses `yt-dlp` to fetch video metadata and download the source video when available;
- uses `ffmpeg`/`ffprobe` to extract media facts, audio, and a contact sheet of key frames;
- optionally uses a transcription command via `--transcribe-command`, or the `whisper` CLI if installed;
- defaults Whisper to `base` with Chinese language hints; override with `LOCAL_BRAIN_WHISPER_MODEL` and `LOCAL_BRAIN_WHISPER_LANGUAGE`;
- writes artifacts under `workspace/videos/<video>/`;
- stores the structured note in SQLite `video_notes`, and with `--memory` also writes a compact summary to memories.

Useful variants:

```bash
python3 -m brain_core video analyze "https://v.douyin.com/..." --no-download
LOCAL_BRAIN_WHISPER_MODEL=tiny python3 -m brain_core video analyze "https://v.douyin.com/..."
python3 -m brain_core video analyze "https://example.com/video" --transcribe-command "your-transcriber {audio}"
python3 -m brain_core video show 1 --json
python3 -m brain_core video report 1 --output workspace/videos/report.md
```

## Video/Project Report Workflow

After a video note is stored, generate a landing-oriented report:

```bash
python3 -m brain_core video report 1 --target "efoot-bool prediction module"
```

The report turns a short video or image-note into:

- source summary and confidence;
- detected tool/project clues such as Codex, PPT Master, or Codex PPT Skill;
- GitHub/official-doc follow-up targets when a known project is recognized;
- risks from missing transcript, missing visual OCR, or platform blocking;
- concrete landing actions for the chosen target project.

This is designed as the default second step after `video analyze`: first capture the source, then convert it into an executable project-research brief.

## Douyin Adapter MVP

Inspect a Douyin link before running heavier video analysis:

```bash
python3 -m brain_core douyin inspect "https://v.douyin.com/..."
python3 -m brain_core douyin inspect "https://www.douyin.com/note/7654131052999627456" --json
```

If you have an `aweme_detail` JSON payload from a trusted adapter, pass it in to extract image-note candidates:

```bash
python3 -m brain_core douyin inspect "https://www.douyin.com/note/7654131052999627456" --aweme-json aweme.json
```

The adapter currently provides:

- Douyin URL detection and shortlink-ready inspection;
- `/note/`, `/gallery/`, and `/video/` ID parsing;
- `aweme_detail.images` URL extraction for image-note/gallery content;
- private Cookie configuration status via `LOCAL_BRAIN_DOUYIN_COOKIE`, `LOCAL_BRAIN_DOUYIN_COOKIE_FILE`, or `data/private/douyin_cookie.txt`;
- a fallback plan that prefers browser-session capture and OCR when WAF blocks direct HTTP access.

Cookies are local-only configuration and should never be committed.

## Safety Model

The default policy is confirm-before-risk:

- reads and local registry inspection are automatic;
- writing files, running commands, browser actions, desktop actions, and network pushes require explicit confirmation;
- GitHub projects are integrated through wrappers, MCP, CLI, or APIs before considering source modifications.

## Candidate Collections

The registry has two collections:

- `hot-ai-agent`: the ten projects from the current GitHub-first plan.
- `personal-assistant-framework`: additional GitHub projects searched as personal AI assistant, local brain, second brain, local agent, or assistant framework candidates.

Use the registry status values this way:

- `watch`: track only.
- `mirror`: clone locally for source reading/testing.
- `integrate`: build wrappers or local adapters around it.
