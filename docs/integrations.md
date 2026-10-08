# Engine integration

Keep each engine independently deployable and communicate through HTTP. The main application owns job IDs, persistence, user-visible state, errors, and output validation. Upstream source modules must not be imported into `apps/api`.

Four narrow Protocol contracts live in `apps/api/adapters/interfaces.py`:

| Interface | Contract | Current implementation |
| --- | --- | --- |
| `VideoGenerator` | Generate a `VideoPlan` (script + search terms) from `VideoInput` | `LLMAdapter` |
| `AssetProvider` | Prepare local asset references from input + plan | No separate provider needed; MPT already searches/prepares assets |
| `Renderer` | Submit input + plan and query task status | `MoneyPrinterAdapter` |
| `Publisher` | Publish a validated local video with a caption and return its reference | Not implemented |

These are extension contracts, not a plugin registry or running placeholder services. A future renderer must provide task IDs and polling status mapped to the current internal engine states, or add a small typed status contract when a second real renderer requires it.

## Adding a renderer

1. Audit its official API, pin its version, and add an independent internal Compose service if needed. Preserve its standalone behavior.
2. Implement `Renderer` in a small HTTP adapter. Normalize processing/complete/failed states, progress, errors, and safe output references. Add explicit connectivity checks and a documented recovery path.
3. Wire it in `create_app`; keep scheduling and SQLite in the app. Avoid adding service selection/configuration abstractions until there are multiple real choices.
4. Reuse MP4 validation and app file serving. Never accept provider success alone as completion.
5. Add contract tests plus a real smoke test with credentials; never substitute mocked external success.

A remote renderer can download its final artifact into a task-specific output directory before using the existing media validation/export service. Enforce download limits/timeouts and safe references then; no unused generic download subsystem is included now.

## Planned engines

- **broll-search / SentrySearch:** implement `AssetProvider` only when adding them. Prepare actual local files/asset references and give them to the renderer as local materials, replacing MPT's stock search for that job.
- **Alibaba Wan API:** decide from its real API whether it creates source clips (`AssetProvider`) or final videos (`Renderer`). Use remote inference and task IDs; do not load a local model.
- **Postiz:** implement `Publisher` for completed validated MP4s. Publishing is a separate explicit user action with its own provider error handling.

None of these integrations, credentials, containers, or placeholder modules are implemented in this MVP.

## MoneyPrinterTurbo audit

Official source: https://github.com/harry0703/MoneyPrinterTurbo. Audited/pinned commit: `9887b459e754ee073c056d988499b91136af9662` (version 1.3.8).

| Source file | Integration finding |
| --- | --- |
| `Dockerfile`, `docker-compose.yml`, `main.py` | Python 3.11 Bullseye image; default image starts Streamlit; standalone API starts with `python main.py` on 8080. Factory runs only API. |
| `app/controllers/v1/video.py` | `POST /api/v1/videos`, `GET /api/v1/tasks`, `GET /api/v1/tasks/{id}`; JSON envelopes store task ID/state in `data`. |
| `app/models/schema.py` | `TaskVideoRequest`: `video_subject`, `video_script`, `video_terms`, `video_aspect`, `video_source`, `video_materials`, `voice_name`, subtitle/font/thread options. No target-seconds field. |
| `app/models/const.py` | Processing = 4, complete = 1, failed = -1. |
| `app/services/task.py` | Supplied script/terms skip LLM generation. Local source skips search terms entirely. Progress: voice/subtitles/materials below 50; render at 50+. Errors include `failed_stage` and `error`. |
| `app/services/video.py` | Local `MaterialInfo.url` resolves under `storage/local_videos`; MP4 clips used directly after dimensions/path checks. Portrait/landscape renders are 1080×1920 / 1920×1080. |
| `app/services/voice.py` | Supports Edge TTS voices with optional `-Female/-Male` display suffix; app uses `vi-VN-HoaiMyNeural-Female` for Vietnamese. |
| `app/services/task.py`, `app/services/subtitle.py` | Configured `subtitle_provider = edge` uses TTS timestamps; no implicit Whisper/model fallback. |
| `app/utils/utils.py`, `app/services/task.py` | Final video is `storage/tasks/<task-id>/final-1.mp4` for a single video. API rewrites output paths to `/tasks/<task-id>/...`. Combined clips are intermediate. |
| `app/services/state.py`, manager classes | Memory registry/queue by default. No durable engine state without Redis. App persists jobs and reconciles missing task IDs with final files. |
| `resource/fonts/BeVietnamPro-Medium.ttf` | Bundled Vietnamese-capable subtitle font, explicitly selected by adapter. |

No upstream source patches. Our separate Bookworm Dockerfile addresses observed Bullseye package HTTP 404s; the configuration launcher writes TOML only inside the container. Original upstream Docker/CLI/UI files are untouched.
