# app/utils/deterministic_cache.py
import json
import hashlib
from typing import Any, Optional
import asyncio

import redis.asyncio as redis
from app.core.config import settings

_redis_client: Optional[redis.Redis] = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        # settings.REDIS_URL is expected like redis://redis:6379/0
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client

def make_cache_key(stage: str, payload: dict, seed: int) -> str:
    # stable JSON stringify
    s = json.dumps({"stage": stage, "payload": payload, "seed": seed}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

async def get_cached(stage: str, payload: dict, seed: int) -> Optional[dict]:
    client = _get_redis()
    key = make_cache_key(stage, payload, seed)
    val = await client.get(key)
    if not val:
        return None
    try:
        return json.loads(val)
    except Exception:
        return None

async def set_cached(stage: str, payload: dict, seed: int, value: dict, expire: int = 60*60*24):
    client = _get_redis()
    key = make_cache_key(stage, payload, seed)
    await client.set(key, json.dumps(value, ensure_ascii=False), ex=expire)
