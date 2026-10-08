import asyncio
from contextlib import asynccontextmanager, suppress
import fcntl
import logging
import httpx
from fastapi import FastAPI
from apps.api.adapters.llm import LLMAdapter
from apps.api.adapters.moneyprinter import MoneyPrinterAdapter
from apps.api.adapters.stock import StockConnections
from apps.api.config import Settings
from apps.api.db.jobs import JobStore
from apps.api.routes import config, videos
from apps.api.services.worker import JobWorker

logging.basicConfig(level=logging.INFO)
# Pixabay authenticates in the query string; HTTP request URLs must not log keys.
logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        for directory in ("inputs", "outputs/engine", "jobs"):
            (settings.data_dir / directory).mkdir(parents=True, exist_ok=True)
        # Hold a process lock for the lifetime of the worker. Accidentally
        # starting a second API process must not create concurrent dispatchers.
        with (settings.data_dir / "jobs" / "worker.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Another API worker owns this job directory. Run one worker.") from exc
            async with httpx.AsyncClient() as client:
                state = app.state
                state.settings = settings
                state.store = JobStore(settings.data_dir / "jobs" / "jobs.sqlite3")
                state.llm = LLMAdapter(settings, client)
                state.renderer = MoneyPrinterAdapter(settings, client)
                state.stock = StockConnections(settings, client)
                worker = JobWorker(settings, state.store, state.llm, state.renderer)
                state.worker_task = asyncio.create_task(worker.run(), name="video-job-worker")
                try:
                    yield
                finally:
                    state.worker_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await state.worker_task
                    fcntl.flock(lock, fcntl.LOCK_UN)

    app = FastAPI(title="AI Video Factory", version="0.1.0", lifespan=lifespan)
    app.include_router(config.router)
    app.include_router(videos.router)
    return app


app = create_app()
