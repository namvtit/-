from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import UUID
import httpx
from apps.api.adapters.interfaces import VideoPlan
from apps.api.config import Settings
from apps.api.schemas.video import Connection, VideoInput

VOICES = {"vi": "vi-VN-HoaiMyNeural-Female", "en": "en-US-JennyNeural-Female", "zh": "zh-CN-XiaoxiaoNeural-Female"}


class MoneyPrinterAdapter:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client
        self.base = settings.moneyprinter_url.rstrip("/")

    async def submit(self, request: VideoInput, plan: VideoPlan) -> str:
        response = await self.client.post(f"{self.base}/api/v1/videos", json={
            "video_subject": request.topic, "video_script": plan.script,
            "video_terms": plan.search_terms, "video_language": request.language,
            "video_aspect": request.aspect_ratio, "voice_name": VOICES[request.language],
            "video_source": request.effective_source,
            "video_materials": [{"provider": "local", "url": key} for key in request.local_materials],
            "video_count": 1, "n_threads": 2, "bgm_type": "", "bgm_volume": 0,
            "subtitle_enabled": True, "font_name": "BeVietnamPro-Medium.ttf",
            "font_size": 48, "video_concat_mode": "sequential",
        }, timeout=30)
        response.raise_for_status()
        task_id = response.json()["data"]["task_id"]
        return str(UUID(task_id))

    async def task(self, task_id: str) -> dict | None:
        response = await self.client.get(f"{self.base}/api/v1/tasks/{task_id}", timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()["data"]

    async def busy(self) -> bool:
        response = await self.client.get(f"{self.base}/api/v1/tasks", params={"page_size": 1000}, timeout=10)
        response.raise_for_status()
        return any(task["state"] == 4 for task in response.json()["data"]["tasks"])

    def output_path(self, task_id: str, uri: str | None = None) -> Path:
        root = (self.settings.data_dir / "outputs" / "engine" / str(UUID(task_id))).resolve()
        # Resolve API output URIs locally through the shared output volume.
        name = f"/tasks/{task_id}/final-1.mp4" if uri is None else unquote(urlsplit(uri).path)
        prefix = f"/tasks/{task_id}/"
        if not name.startswith(prefix):
            raise ValueError("Renderer returned an output outside its task directory.")
        path = (root / name[len(prefix):]).resolve()
        if not path.is_relative_to(root) or path.suffix.lower() != ".mp4":
            raise ValueError("Renderer returned an unsafe output path.")
        return path

    async def connection(self) -> Connection:
        try:
            response = await self.client.get(f"{self.base}/ping", timeout=5)
            response.raise_for_status()
            if response.json() != "pong":
                raise ValueError("Unexpected ping response")
            return Connection(status="connected", detail="Renderer API is reachable.")
        except (httpx.HTTPError, ValueError):
            return Connection(status="unreachable", detail="Renderer is unavailable. Check docker compose logs moneyprinter.")
