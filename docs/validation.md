# Validation results

Run in this workspace on 2026-10-09 (Asia/Saigon). No LLM or Pexels credentials were available. Results below distinguish real service tests from isolated unit tests.

| Check | Result | Evidence |
| --- | --- | --- |
| Docker configuration | PASS | `docker compose config -q` |
| One-command startup | PASS | `docker compose up -d --build`; web, api, moneyprinter healthy |
| Backend tests | PASS | 21 tests passed in 9.91 seconds; one test-tool deprecation warning |
| Real MoneyPrinterTurbo connectivity | PASS | Internal `/ping`, task-list endpoint, and generation OpenAPI schema checked over HTTP |
| Frontend production build | PASS | TypeScript compile and Vite build (32 modules after splitting page components) |
| Real script + local-material E2E | PASS | Actual Edge TTS narration, subtitle generation, MoneyPrinterTurbo rendering, app duration export, preview Range, and MP4 download |
| ffprobe verification | PASS | H.264 video, AAC audio, 1080 × 1920, exactly 30.000 seconds, 10,227,106 bytes |
| Restart during real generation | PASS | API restarted immediately after upstream ID was persisted; same app job resumed polling and completed |
| Complete stack recreation | PASS | Subsequent `docker compose up -d --build` recreated all containers; SQLite job and MP4 remained accessible |
| Browser checks | PASS | Desktop dashboard/settings/jobs, responsive 390px layout, no overflow/JS errors, real video playback, actual MP4 browser download; browser requests stayed on this app's origin |
| Real automatic topic → LLM → Pexels path | BLOCKED | Missing `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and `PEXELS_API_KEY`; smoke script reports the blocker before generation |

## Real generated sample

- App job: `0efc8fb4-7539-42de-ad16-2d08ca8d8ef6`.
- Renderer task: `7b95b264-c82b-415f-af4b-4655442a7b7c`.
- MP4: `data/outputs/0efc8fb4-7539-42de-ad16-2d08ca8d8ef6/video.mp4`.
- Preview: http://localhost:3000/api/videos/0efc8fb4-7539-42de-ad16-2d08ca8d8ef6/preview.
- Download: http://localhost:3000/api/videos/0efc8fb4-7539-42de-ad16-2d08ca8d8ef6/download.

The sample deliberately used a locally generated FFmpeg test-pattern clip and a supplied Vietnamese narration script. The narration request to Edge TTS and all rendering/download calls were real. No LLM output, stock download, or external success was mocked. This proves the supported supplied-script/local-clips path, not automatic topic/stock generation.

The real smoke sequence was RECEIVED → PREPARING_MATERIALS → RENDERING → COMPLETED. The supplied script bypasses LLM work; the worker still persists the GENERATING_SCRIPT stage when accepting the plan, which can be shorter than the three-second polling interval.

Measured during rendering: MoneyPrinterTurbo approximately 1.13 GiB RAM, API 45 MiB, web 12 MiB. This is one local smoke measurement, not a performance guarantee. Rendering used CPU encoding with two threads, no GPU or local model downloads.

## Reproduce

```bash
docker compose up -d --build
docker compose config -q
.venv/bin/python -m pytest -q
npm run build --prefix apps/web
docker compose exec -T api python - < scripts/check_moneyprinter.py
.venv/bin/python scripts/smoke.py --material /path/to/clip.mp4 \
  --script /path/to/vietnamese-narration.txt --restart-api
```

For the remaining automatic path, fill the four credential/provider variables in `.env`, run `docker compose up -d --build`, then run `.venv/bin/python scripts/smoke.py`. The script uses the actual providers and validates the downloaded video with ffprobe. Provider `/models` checks alone are not proof of chat-generation authorization or sufficient quota.

Optional browser check (requires installed Chromium):

```bash
uv pip install --python .venv/bin/python playwright
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/check_web.py
```

This checks playback/download when a real completed job exists. An existing system browser can be selected using `--browser-executable /path/to/chromium`.

## Packaging finding

The first build using upstream's Bullseye Dockerfile failed on missing Debian security package URLs (HTTP 404). The factory's separate Bookworm Dockerfile built and started successfully. Upstream source remains unchanged; its pinned commit was verified with Git. Unit coverage includes known/missing task recovery, validated final-artifact recovery, ambiguous submission handling, a busy/unreachable engine, corrupt completed output, upload/output path restrictions, HTTP Range serving, and process-lock enforcement.
