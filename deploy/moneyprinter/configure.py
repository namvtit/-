"""Generate upstream's runtime TOML; no upstream source edits or imports."""
import json
import os
from pathlib import Path

stock_config = ""
for source in ("pexels", "pixabay", "coverr"):
    key = os.getenv(f"{source.upper()}_API_KEY", "").strip()
    stock_config += f'{source}_api_keys = {json.dumps([key] if key else [])}\n'
Path("config.toml").write_text(
    'listen_host = "0.0.0.0"\nlisten_port = 8080\nlog_level = "INFO"\n'
    '[app]\nenable_redis = false\nmax_concurrent_tasks = 1\nmax_queued_tasks = 1\n'
    'subtitle_provider = "edge"\nllm_provider = "openai"\n'
    + stock_config +
    '[ui]\n', encoding="utf-8",
)
