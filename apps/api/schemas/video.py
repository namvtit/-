from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Status(str, Enum):
    RECEIVED = "RECEIVED"
    GENERATING_SCRIPT = "GENERATING_SCRIPT"
    PREPARING_MATERIALS = "PREPARING_MATERIALS"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VideoInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    topic: str = Field(min_length=1, max_length=500)
    language: Literal["vi", "en", "zh"] = "vi"
    duration: int = Field(default=45, ge=30, le=60, strict=True)
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    script: str | None = Field(default=None, max_length=8000)
    footage_source: Literal["pixabay", "pexels", "coverr", "local"] = "pexels"
    local_materials: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("script")
    @classmethod
    def empty_script(cls, value: str | None) -> str | None:
        return value or None

    @property
    def effective_source(self) -> str:
        return "local" if self.local_materials else self.footage_source

    @field_validator("local_materials")
    @classmethod
    def material_keys(cls, keys: list[str]) -> list[str]:
        from uuid import UUID
        for key in keys:
            try:
                if not key.endswith(".mp4") or str(UUID(key[:-4])) != key[:-4]:
                    raise ValueError()
            except ValueError:
                raise ValueError("Use material IDs returned by POST /api/materials.")
        return list(dict.fromkeys(keys))


class VideoMetadata(BaseModel):
    duration: float
    width: int
    height: int
    size_bytes: int
    video_codec: str
    audio_codec: str


class Job(BaseModel):
    id: str
    input: VideoInput
    status: Status
    progress: int = Field(ge=0, le=100)
    upstream_task_id: str | None = None
    created_at: str
    updated_at: str
    error: str | None = None
    metadata: VideoMetadata | None = None
    preview_url: str | None = None
    download_url: str | None = None


class Material(BaseModel):
    id: str
    name: str
    size_bytes: int


class Connection(BaseModel):
    status: Literal["connected", "unreachable", "missing_configuration", "not_checked"]
    detail: str


class StockProvider(BaseModel):
    id: Literal["pixabay", "pexels", "coverr"]
    name: str
    configured: bool
    missing_keys: list[str]
    connection: Connection


class PublicConfig(BaseModel):
    llm_base_url: str
    llm_model: str
    llm_configured: bool
    llm_connection: Connection
    renderer: str = "MoneyPrinterTurbo"
    renderer_connection: Connection
    stock_configured: bool
    stock_providers: list[StockProvider]
    default_footage_source: Literal["pixabay", "pexels", "coverr"]
    tts: str = "Edge TTS"
    setup_issues: list[str]
