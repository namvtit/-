# AI Video Factory

A minimal React + FastAPI video workspace with SQLite jobs and an independent, pinned MoneyPrinterTurbo renderer. All interaction happens in this app.

## Start

Requires Docker Engine/Desktop with Compose, Internet access, and enough disk space for the upstream Python/video dependencies. No GPU, local inference model, Redis, or Celery is required. CPU rendering uses two encoding threads and one job at a time.

When cloning this project, include the engine:

```bash
git clone --recurse-submodules <this-repository-url> ai-video-factory
cd ai-video-factory
# For an existing clone:
git submodule update --init --recursive
```

The engine is already checked out in the delivered workspace. Its Git submodule and `vendors/MoneyPrinterTurbo.commit` pin commit `9887b459e754ee073c056d988499b91136af9662`.

Configure remote services:

```bash
cp .env.example .env
# Edit .env with your actual provider values.
```

| Variable | Required for | Example |
| --- | --- | --- |
| `LLM_BASE_URL` | Automatic narration and stock-search terms when script is empty | `https://api.deepseek.com/v1` |
| `LLM_API_KEY` | Provider authentication | Your key |
| `LLM_MODEL` | Model accessible to your account | Your provider’s model ID |
| `PIXABAY_API_KEY` | Stock footage with Pixabay selected | Your Pixabay API key |
| `PEXELS_API_KEY` | Stock footage with Pexels selected | Your Pexels API key |
| `COVERR_API_KEY` | Stock footage with Coverr selected | Your Coverr API key |
| `JOB_TIMEOUT_SECONDS` | Optional processing deadline | `1800` |
| `POLL_INTERVAL_SECONDS` | Optional engine polling interval | `3` |

Any compatible chat-completions provider can be used. A bare gateway URL such as `https://hhtechapi.com` is normalized to `/v1`; explicit API paths are preserved. For GLM, use your gateway's OpenAI-compatible base URL and supported model; the public BigModel base is `https://open.bigmodel.cn/api/paas/v4`. Use a base URL without `/chat/completions`. Check the [DeepSeek API docs](https://api-docs.deepseek.com/en/) or your GLM gateway documentation for current model IDs. Do not commit `.env`.

Start the entire app with one command:

```bash
docker compose up -d --build
```

Open **http://localhost:3000**. Debug API docs: http://localhost:8000/docs. MoneyPrinterTurbo has no published host port. Initial builds install upstream dependencies and can take several minutes.

The app also starts without API keys. The form and Settings name missing configuration; generation returns an explicit setup error. There is no fake generation fallback. Edge TTS requires outbound Internet access but no API key. A **supplied Narration Script** skips the LLM. **Uploaded local clips** skip stock search and need no stock API key. With both, neither an LLM nor a stock key is needed.

## Use

1. Enter the required **Topic/Prompt**. Leave **Narration Script** empty to generate it through the configured LLM, or supply the exact narration. Choose language (Vietnamese by default), 30/45/60 seconds, and portrait or landscape.
2. Select **Pixabay**, **Pexels**, **Coverr**, or **Local** footage. A configured stock provider is selected initially. With no uploaded clips, the selected stock provider is used. Local requires at least one uploaded clip; uploaded clips always take precedence over stock. MP4 clips must be at least 480 pixels in both dimensions, at most 100 MB each, and no more than 12 per job. Uploads are checked with ffprobe; arbitrary host paths are not accepted.
3. Click **Generate video**. Follow the current job or open **Your videos**. Jobs persist while the page is closed.
4. Preview the completed video and download its MP4. Playback supports seeking using HTTP Range requests.

The app's LLM creates the narration and search terms together when narration is empty. A supplied script is preserved, bypasses the LLM, and uses the topic (up to 100 characters) as the stock search phrase; a concrete visual topic works best. MoneyPrinterTurbo receives these directly and handles footage search, Edge TTS, subtitles, and rendering without another script-generation call. The target length guides script writing. Since upstream renders to narration length, the app adjusts video timing and audio tempo to the requested exact duration, then produces an H.264/AAC MP4 with fast-start metadata. A script far from the requested length will cause a noticeable tempo change; write a suitable-length narration.

Provider/model and live connection checks appear in the form and **Settings**. The LLM `/models` endpoint is checked without incurring a generation request. Providers without that endpoint show “not checked”; authenticated generation is validated per job. Configured stock providers receive a small real video-search check, with connection results cached for 60 seconds. Missing keys are named without exposing their values. Generate is disabled for missing configuration needed by the current request and during submission/upload; connection warnings allow submission and job errors remain visible. Edge TTS is checked during actual generation. Changing `.env` requires `docker compose up -d --build` to recreate affected containers.

## Persistence and recovery

`data/inputs` stores uploaded clips, `data/outputs/engine` stores engine task artifacts, `data/outputs/<job-id>/video.mp4` stores validated final exports, and `data/jobs/jobs.sqlite3` stores jobs. These bind mounts survive container rebuilds and `docker compose down`. The stock cache uses a named volume. Back up `data/` while the stack is stopped to get a consistent SQLite backup.

One API process owns the dispatcher, enforced with a file lock. It processes jobs FIFO. After an API restart, jobs with an engine task ID resume polling without resubmission; earlier stages resume from saved script data. After an engine restart, a lost task recovers from `final-1.mp4` only when that file passes ffprobe and final export checks. Otherwise it becomes FAILED with an explicit interruption error.

Upstream POST is not idempotent: a crash or lost response between task acceptance and ID persistence is ambiguous. The app records the submission before sending it and does **not** automatically repeat it. Check renderer logs before creating a replacement. Timed-out or ambiguous upstream tasks must become idle before the next submission. A network outage never permits a second active render. Intermediate/combined video files never qualify as a successful job.

Useful commands:

```bash
docker compose ps
docker compose logs -f api moneyprinter
docker compose restart api
docker compose down
```

## Validation

Host development/testing requires Python 3.11+, Node 22, and FFmpeg/ffprobe. The production containers include the media tools.

```bash
uv venv --python 3.11
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest -q
npm ci --prefix apps/web
npm run build --prefix apps/web
docker compose config -q
# Real, internal HTTP connectivity check:
docker compose exec -T api python - < scripts/check_moneyprinter.py
# Real topic-to-video smoke test; needs configured LLM and a stock provider:
.venv/bin/python scripts/smoke.py
# Select a particular provider:
.venv/bin/python scripts/smoke.py --source pixabay
# Real local-material/script path plus an API restart while the engine works:
.venv/bin/python scripts/smoke.py --material /path/to/clip.mp4 \
  --script /path/to/narration.txt --restart-api
```

Smoke tests call the real app, renderer, and providers. They verify progress, ranged preview, downloaded MP4 streams, aspect ratio, duration, and optionally API restart recovery. They exit with a clear blocker/failure instead of fabricating success. Unit tests use isolated HTTP stubs for adapter contracts and real generated media fixtures for ffprobe/export checks. They are not proof of external-service availability.

See [docs/validation.md](docs/validation.md) for the results from this workspace, [architecture](docs/architecture.md) for the request flow, and [integrations](docs/integrations.md) for engine extension points.

## Upstream packaging

The upstream checkout is unmodified and remains independently runnable with its original configuration, CLI, API, and Streamlit UI. Our Compose uses `deploy/moneyprinter/Dockerfile` (Python 3.11 Bookworm + FFmpeg + upstream requirements). The audited upstream Dockerfile uses Bullseye; its security package downloads returned HTTP 404 in this environment. This packaging change avoids patching upstream source. `deploy/moneyprinter/configure.py` creates a runtime TOML inside the container with one render slot, Edge subtitles, and environment-configured Pixabay/Pexels/Coverr keys. No upstream LLM key is needed because the app supplies script and terms.

This MVP is a local, single-user workspace exposed on loopback. Authentication, deletion/retention UI, cancellation, publishing, and additional engines are outside the current scope.
