from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "data")).resolve())
    moneyprinter_url: str = field(default_factory=lambda: os.getenv("MONEYPRINTER_URL", "http://moneyprinter:8080"))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "").strip().rstrip("/"))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "").strip())
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "").strip())
    pexels_api_key: str = field(default_factory=lambda: os.getenv("PEXELS_API_KEY", "").strip())
    pixabay_api_key: str = field(default_factory=lambda: os.getenv("PIXABAY_API_KEY", "").strip())
    coverr_api_key: str = field(default_factory=lambda: os.getenv("COVERR_API_KEY", "").strip())
    poll_interval: float = field(default_factory=lambda: max(0.1, float(os.getenv("POLL_INTERVAL_SECONDS", "3"))))
    job_timeout: int = field(default_factory=lambda: max(30, int(os.getenv("JOB_TIMEOUT_SECONDS", "1800"))))

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)

    @property
    def llm_api_base_url(self) -> str:
        # OpenAI-compatible gateways often document their bare host as the base.
        base = self.llm_base_url.rstrip("/")
        return f"{base}/v1" if base and not urlsplit(base).path else base

    @property
    def missing_llm_keys(self) -> list[str]:
        return [name.upper() for name in ("llm_base_url", "llm_api_key", "llm_model") if not getattr(self, name)]

    @property
    def stock_keys(self) -> dict[str, str]:
        return {"pixabay": self.pixabay_api_key, "pexels": self.pexels_api_key, "coverr": self.coverr_api_key}

    @property
    def default_footage_source(self) -> str:
        return next((source for source, key in self.stock_keys.items() if key), "pixabay")

    def required_configuration(self, params) -> list[str]:
        issues = []
        if not params.script and self.missing_llm_keys:
            issues.append(f"Set {', '.join(self.missing_llm_keys)} in .env to generate the narration script.")
        if params.effective_source != "local" and not self.stock_keys[params.effective_source]:
            issues.append(f"Set {params.effective_source.upper()}_API_KEY in .env or upload local MP4 clips.")
        return issues

    def setup_issues(self) -> list[str]:
        issues = []
        for name in ("llm_base_url", "llm_api_key", "llm_model"):
            if not getattr(self, name):
                issues.append(f"Set {name.upper()} in .env for AI script generation.")
        if not any(self.stock_keys.values()):
            issues.append("Set PIXABAY_API_KEY, PEXELS_API_KEY or COVERR_API_KEY for stock footage, or upload local MP4 clips.")
        return issues
