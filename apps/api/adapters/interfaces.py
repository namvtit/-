"""Narrow extension contracts. Implementations are added when an engine needs them."""
from pathlib import Path
from typing import Protocol
from pydantic import BaseModel, Field
from apps.api.schemas.video import VideoInput


class VideoPlan(BaseModel):
    script: str = Field(min_length=1, max_length=8000)
    search_terms: list[str] = Field(min_length=1, max_length=8)


class AssetProvider(Protocol):
    async def prepare(self, request: VideoInput, plan: VideoPlan) -> list[str]: ...


class VideoGenerator(Protocol):
    async def generate(self, request: VideoInput) -> VideoPlan: ...


class Renderer(Protocol):
    async def submit(self, request: VideoInput, plan: VideoPlan) -> str: ...
    async def task(self, task_id: str) -> dict | None: ...


class Publisher(Protocol):
    async def publish(self, video: Path, caption: str) -> str: ...
