"""Connection checks only; MoneyPrinterTurbo owns stock search and downloads."""
import asyncio
import time
import httpx
from apps.api.config import Settings
from apps.api.schemas.video import Connection, StockProvider


class StockConnections:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client
        self.cache: dict[str, tuple[float, Connection]] = {}

    async def providers(self) -> list[StockProvider]:
        return await asyncio.gather(*(self.provider(source, key) for source, key in self.settings.stock_keys.items()))

    async def provider(self, source: str, key: str) -> StockProvider:
        missing = [] if key else [f"{source.upper()}_API_KEY"]
        if missing:
            connection = Connection(status="missing_configuration", detail=f"Missing: {missing[0]}.")
        elif source in self.cache and self.cache[source][0] > time.monotonic():
            connection = self.cache[source][1]
        else:
            connection = await self.check(source, key)
            self.cache[source] = (time.monotonic() + 60, connection)
        return StockProvider(id=source, name={"pixabay": "Pixabay", "pexels": "Pexels", "coverr": "Coverr"}[source],
                             configured=bool(key), missing_keys=missing, connection=connection)

    async def check(self, source: str, key: str) -> Connection:
        endpoints = {
            "pixabay": ("https://pixabay.com/api/videos/", {"key": key, "q": "nature", "per_page": 3}, {}),
            "pexels": ("https://api.pexels.com/videos/search", {"query": "nature", "per_page": 1}, {"Authorization": key}),
            "coverr": ("https://api.coverr.co/videos", {"query": "nature", "page_size": 1}, {"Authorization": f"Bearer {key}"}),
        }
        url, params, headers = endpoints[source]
        try:
            response = await self.client.get(url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            field = "videos" if source == "pexels" else "hits"
            if not isinstance(data, dict) or not isinstance(data.get(field), list):
                return Connection(status="unreachable", detail="Provider returned an unexpected search response.")
            return Connection(status="connected", detail="Video search API responded. Matching footage and downloads are checked per job.")
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            reason = "check the API key" if status in (401, 403) else "check provider availability and quota"
            return Connection(status="unreachable", detail=f"Video search API returned HTTP {status}; {reason}.")
        except httpx.RequestError:
            return Connection(status="unreachable", detail="Video search API is unreachable or timed out; check network access.")
        except ValueError:
            return Connection(status="unreachable", detail="Video search API returned an invalid JSON response.")
