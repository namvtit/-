"""One durable FIFO dispatcher. Network waits never block request handlers."""
import asyncio
from datetime import datetime, timezone
import json
import logging
import httpx
from apps.api.adapters.interfaces import VideoPlan
from apps.api.adapters.llm import LLMAdapter
from apps.api.adapters.moneyprinter import MoneyPrinterAdapter
from apps.api.config import Settings
from apps.api.db.jobs import JobStore, now
from apps.api.schemas.video import Status, VideoInput
from apps.api.services.media import finalize

logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(self, settings: Settings, store: JobStore, llm: LLMAdapter, renderer: MoneyPrinterAdapter):
        self.settings, self.store = settings, store
        self.llm, self.renderer = llm, renderer

    async def run(self):
        while True:
            job = self.store.pending()
            if job:
                try:
                    await self.process(job)
                except asyncio.CancelledError:
                    raise  # Durable state is reconciled by the next worker process.
                except Exception as exc:
                    # Never put HTTP request/response bodies or credentials into errors.
                    error = str(exc) if isinstance(exc, ValueError) else "Internal processing failure; check API logs."
                    logger.error("Job %s failed (%s)", job["id"], type(exc).__name__)
                    self.store.update(job["id"], status=Status.FAILED.value, error=error)
            await asyncio.sleep(self.settings.poll_interval)

    async def process(self, job: dict):
        job_id = job["id"]
        request = VideoInput.model_validate_json(job["input_json"])
        if job["upstream_task_id"]:
            await self.poll(job)
            return
        if job["submission_started_at"]:
            # Upstream POST has no idempotency key. A crash after acceptance but
            # before saving its ID is ambiguous: do not bill/render twice.
            self.store.update(job_id, status=Status.FAILED.value,
                              error="Renderer submission was interrupted before its task ID was saved. Check renderer logs before retrying.")
            return
        # Upstream may still be rendering an earlier timed-out/ambiguous job.
        # A lost connection never grants permission to start another render.
        try:
            if await self.renderer.busy():
                return
        except (httpx.HTTPError, ValueError, KeyError):
            self.store.update(job_id, error="Waiting for the renderer connection; no new render was submitted.")
            return
        if not job["script"]:
            self.store.update(job_id, status=Status.GENERATING_SCRIPT.value, progress=5, error=None)
            plan = await self.llm.generate(request)
            job = self.store.update(job_id, script=plan.script, terms_json=json.dumps(plan.search_terms))
        else:
            plan = VideoPlan(script=job["script"], search_terms=json.loads(job["terms_json"]))
        self.store.update(job_id, status=Status.PREPARING_MATERIALS.value, progress=15, error=None)
        for key in request.local_materials:
            if not (self.settings.data_dir / "inputs" / key).is_file():
                raise ValueError("An uploaded material is missing; upload it again and create a new job.")
        if request.effective_source == "local" and not request.local_materials:
            raise ValueError("Local footage is selected; upload at least one MP4 clip or select a stock provider.")
        missing = self.settings.required_configuration(request)
        if missing:
            raise ValueError(" ".join(missing))
        self.store.update(job_id, submission_started_at=now())
        try:
            task_id = await self.renderer.submit(request, plan)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ValueError("Renderer submission failed or its response was lost. Check renderer logs before retrying; the request was not automatically repeated.") from exc
        job = self.store.update(job_id, upstream_task_id=task_id, error=None)
        await self.poll(job)

    async def poll(self, job: dict):
        job_id, task_id = job["id"], job["upstream_task_id"]
        start = datetime.fromisoformat(job["submission_started_at"] or job["created_at"])
        while True:
            try:
                task = await self.renderer.task(task_id)
            except (httpx.HTTPError, ValueError, KeyError):
                self.store.update(job_id, error="Renderer connection interrupted; retrying task status.")
                task = "unreachable"
            if task is None:
                # Engine process restart loses its in-memory task registry. Only
                # its final video (never combined/intermediate clips) is recoverable.
                source = self.renderer.output_path(task_id)
                if source.is_file():
                    await self.complete(job, source)
                else:
                    self.store.update(job_id, status=Status.FAILED.value,
                                      error="Renderer task was lost after a restart and no final MP4 exists. Create a new job to retry.")
                return
            if isinstance(task, dict):
                state = task.get("state")
                if state == -1:
                    # Upstream errors may contain a provider key; scrub configured secrets.
                    error = str(task.get("error") or "MoneyPrinterTurbo generation failed.")
                    for secret in (self.settings.llm_api_key, *self.settings.stock_keys.values()):
                        if secret:
                            error = error.replace(secret, "[redacted]")
                    self.store.update(job_id, status=Status.FAILED.value,
                                      error=f"Renderer ({task.get('failed_stage') or 'pipeline'}): {error[:1500]}")
                    return
                if state == 1:
                    videos = task.get("videos") or []
                    if not videos:
                        raise ValueError("Renderer reported completion without a final MP4.")
                    await self.complete(job, self.renderer.output_path(task_id, videos[0]))
                    return
                if state != 4:
                    raise ValueError("Renderer returned an unknown task state.")
                progress = max(15, min(94, int(task.get("progress", 0))))
                status = Status.RENDERING if progress >= 50 else Status.PREPARING_MATERIALS
                # Never regress a rendering state during reconnect/recovery.
                if self.store.get(job_id)["status"] == Status.RENDERING.value:
                    status = Status.RENDERING
                self.store.update(job_id, status=status.value, progress=progress, error=None)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            if elapsed >= self.settings.job_timeout:
                self.store.update(job_id, status=Status.FAILED.value,
                                  error="Generation timed out. The engine may still be working; new renders wait until it is idle. Check renderer logs before retrying.")
                return
            await asyncio.sleep(self.settings.poll_interval)

    async def complete(self, job: dict, source):
        request = VideoInput.model_validate_json(job["input_json"])
        self.store.update(job["id"], status=Status.RENDERING.value, progress=95, error=None)
        destination = self.settings.data_dir / "outputs" / job["id"] / "video.mp4"
        metadata = await finalize(source, destination, request.duration, request.aspect_ratio)
        self.store.update(job["id"], status=Status.COMPLETED.value, progress=100, error=None,
                          final_mp4_path=str(destination), metadata_json=metadata.model_dump_json())
