# app/services/deterministic_cache.py
import json
import asyncio
from typing import Any, Optional
from app.core.config import settings

try:
    import redis.asyncio as aioredis
except Exception:
    aioredis = None  # tests can monkeypatch or skip Redis if not available

DEFAULT_TTL = 60 * 60 * 24  # 24h

class DeterministicCache:
    def __init__(self, url: Optional[str] = None):
        self._url = url or settings.REDIS_URL
        self._client = None

    async def _get_client(self):
        if self._client is None:
            if aioredis is None:
                raise RuntimeError("redis.asyncio is not installed")
            self._client = aioredis.from_url(self._url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        client = await self._get_client()
        val = await client.get(key)
        if val is None:
            return None
        return json.loads(val)

    async def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL):
        client = await self._get_client()
        await client.set(key, json.dumps(value), ex=ttl)

    async def delete(self, key: str):
        client = await self._get_client()
        await client.delete(key)

# convenience sync wrapper for tests that don't want to await creation:
cache = DeterministicCache()
