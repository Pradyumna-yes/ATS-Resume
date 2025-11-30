# app/services/queue.py
import json
import uuid
from typing import Dict, Any, Optional
import redis.asyncio as aioredis
from app.core.config import settings

STREAM_KEY = "pipeline:stream"
GROUP_NAME = "pipeline:group"
DLQ_KEY = "pipeline:dlq"

def _get_redis_client():
    url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    return aioredis.from_url(url, decode_responses=True)

async def ensure_group_exists(stream: str = STREAM_KEY, group: str = GROUP_NAME):
    client = _get_redis_client()
    # create stream & group if not exist. XGROUP CREATE <stream> <group> $ MKSTREAM
    try:
        await client.xgroup_create(name=stream, groupname=group, id="$", mkstream=True)
    except Exception as exc:
        # If group exists, Redis raises BUSYGROUP; ignore
        if "BUSYGROUP" in str(exc).upper():
            return
        raise

async def enqueue_stream_job(payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> str:
    """
    Add a job to Redis Stream. Returns the stream id.
    payload: JSON-serializable dict
    idempotency_key: optional string to avoid duplicated processing (worker will check)
    """
    client = _get_redis_client()
    entry = {
        "payload": json.dumps(payload, ensure_ascii=False),
        "idempotency_key": idempotency_key or "",
    }
    # XADD stream * field value ...
    sid = await client.xadd(STREAM_KEY, entry)
    return str(sid)

# helper to move to DLQ with metadata
async def move_to_dlq(stream_id: str, payload: Dict[str, Any], reason: str):
    client = _get_redis_client()
    entry = {
        "original_id": stream_id,
        "payload": json.dumps(payload, ensure_ascii=False),
        "reason": reason
    }
    return await client.xadd(DLQ_KEY, entry)
