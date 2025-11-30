# app/services/worker_streams.py
import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Tuple

import redis.asyncio as aioredis

from app.core.config import settings
from app.services.pipeline import run_assessment_pipeline
from app.services.queue import (
    STREAM_KEY,
    GROUP_NAME,
    DLQ_KEY,
    _get_redis_client,
    ensure_group_exists,
    move_to_dlq,
)

# R2 fetch + parsing helpers (you should have these files added)
from app.services.r2_fetch import get_object_bytes
from app.services.parse_utils import extract_text_auto

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Worker tuning
DEFAULT_MAX_RETRIES = int(getattr(settings, "WORKER_MAX_RETRIES", 5))
CLAIM_IDLE_MS = int(getattr(settings, "WORKER_CLAIM_IDLE_MS", 30_000))  # reclaim pending msgs older than 30s
READ_BLOCK_MS = int(getattr(settings, "WORKER_READ_BLOCK_MS", 5000))
PENDING_CHECK_INTERVAL = int(getattr(settings, "WORKER_PENDING_CHECK_INTERVAL", 10))  # seconds


async def _handle_pending_claims(client: aioredis.Redis, consumer_name: str) -> None:
    """
    Inspect pending entries and attempt to claim and process those that have been idle for >= CLAIM_IDLE_MS.
    """
    try:
        # Get summary of pending: will return list of pending entries if any
        # XINFO or XPENDING can be used; use XPENDING range to fetch candidate ids
        pending_info = await client.xpending(STREAM_KEY, GROUP_NAME, "-", "+", 10)
        if not pending_info:
            return

        for item in pending_info:
            # item: [id, consumer, idle_ms, deliveries]
            msg_id = item[0]
            idle_ms = item[2]
            if idle_ms >= CLAIM_IDLE_MS:
                logger.info("Attempting to claim pending msg %s (idle %sms)", msg_id, idle_ms)
                # Attempt to claim (returns list of [id, data] pairs)
                claimed = await client.xclaim(STREAM_KEY, GROUP_NAME, consumer_name, min_idle_time=CLAIM_IDLE_MS, message_ids=[msg_id])
                if not claimed:
                    continue
                for cid, data in claimed:
                    parsed = {k: v for k, v in data.items()}
                    ok = await _process_message(cid, parsed)
                    if ok:
                        await client.xack(STREAM_KEY, GROUP_NAME, cid)
                        await client.xdel(STREAM_KEY, cid)
                    else:
                        # leave pending for retry logic in main loop
                        logger.warning("Reclaimed message %s failed processing", cid)
    except Exception:
        logger.exception("Error while handling pending claims")


async def _process_message(message_id: str, data: Dict[str, Any]) -> bool:
    """
    Process single message (fields as dict). Returns True on success, False on failure.

    Expects `data` to be a dict of string->string where data["payload"] is JSON string.
    """
    try:
        payload_json = data.get("payload")
        payload = json.loads(payload_json) if payload_json else {}
        idempotency_key = (data.get("idempotency_key") or payload.get("idempotency_key") or "").strip()

        # Idempotency: mark processed keys to avoid double-processing
        if idempotency_key:
            client = _get_redis_client()
            processed_key = f"processed:{idempotency_key}"
            # setnx returns True if key was set (i.e., wasn't present)
            set_ok = await client.setnx(processed_key, "1")
            if not set_ok:
                logger.info("Skipping already processed idempotency key: %s", idempotency_key)
                return True
            # TTL for processed marker
            await client.expire(processed_key, 60 * 60 * 24 * 7)

        # Enrich resume_payload by fetching contents if storage_key provided
        resume_payload = payload.get("resume_payload", {}) or {}
        storage_key = resume_payload.get("storage_key")
        if storage_key:
            bucket = getattr(settings, "S3_BUCKET", None)
            if not bucket:
                logger.error("S3_BUCKET not configured but storage_key present; failing message to trigger retry")
                return False

            try:
                logger.info("Fetching object from bucket=%s key=%s", bucket, storage_key)
                obj_bytes = await get_object_bytes(bucket, storage_key)
                if not obj_bytes:
                    logger.warning("Empty object bytes for key %s", storage_key)
                    # treat as failure to allow retry / DLQ
                    return False
                # Parse bytes into text
                try:
                    text, kind = extract_text_auto(obj_bytes)
                    resume_payload["file_text"] = text
                    resume_payload["file_type"] = kind
                except Exception as parse_err:
                    logger.exception("Failed to parse object %s: %s", storage_key, parse_err)
                    # attach parse error for DLQ debugging and fail so retry logic can handle it
                    resume_payload["parse_error"] = str(parse_err)
                    payload["resume_payload"] = resume_payload
                    return False
            except Exception as fetch_err:
                logger.exception("Failed to fetch object %s from bucket %s: %s", storage_key, bucket, fetch_err)
                # treat as transient failure -> return False so retry/increment occurs
                return False
        else:
            # No storage_key: maybe resume_payload already contains file_text, that's fine.
            if resume_payload.get("file_text"):
                logger.debug("Message contains inline file_text; using it.")
            else:
                logger.debug("No storage_key or file_text provided; pipeline will run with empty resume payload.")

        # Run pipeline using enriched resume_payload
        job_payload = payload.get("job_payload", {}) or {}
        seed = int(payload.get("seed", 42))
        # Pass the enriched resume_payload to pipeline
        result = await run_assessment_pipeline(job_payload, resume_payload, seed=seed)
        logger.info("Message %s processed -> assessment %s", message_id, result.get("assessment_id"))
        return True

    except Exception:
        logger.exception("Unhandled exception while processing message %s", message_id)
        return False


async def worker_loop(consumer_name: str = None, max_retries: int = DEFAULT_MAX_RETRIES):
    """
    Main worker loop polling Redis Streams via consumer group.
    - Claims pending items older than CLAIM_IDLE_MS
    - Reads new entries with XREADGROUP
    - Calls _process_message to handle each entry
    - On failure increments retry counter; if retries >= max_retries moves message to DLQ
    """
    consumer_name = consumer_name or f"worker-{uuid.uuid4().hex[:8]}"
    client = _get_redis_client()
    logger.info("Worker '%s' starting and connecting to Redis...", consumer_name)
    await ensure_group_exists()

    while True:
        try:
            # handle orphaned pending messages first
            try:
                await _handle_pending_claims(client, consumer_name)
            except Exception:
                logger.exception("Error while handling pending claims")

            # Blocking read for new messages
            entries: List[Tuple[str, List[Tuple[str, Dict[str, str]]]]] = await client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=consumer_name,
                streams={STREAM_KEY: ">"},
                count=1,
                block=READ_BLOCK_MS,
            )
            if not entries:
                await asyncio.sleep(0.05)
                continue

            for stream_name, messages in entries:
                for msg_id, data in messages:
                    # data is mapping of field->value (strings)
                    parsed = {k: v for k, v in data.items()}
                    ok = await _process_message(msg_id, parsed)
                    if ok:
                        # acknowledge and delete from stream
                        await client.xack(STREAM_KEY, GROUP_NAME, msg_id)
                        await client.xdel(STREAM_KEY, msg_id)
                        # cleanup retry counter if present
                        await client.delete(f"retries:{msg_id}")
                    else:
                        # increment retry counter and decide DLQ move
                        retries_key = f"retries:{msg_id}"
                        retries = await client.incr(retries_key)
                        await client.expire(retries_key, 60 * 60 * 24)
                        logger.warning("Message %s failed (retry %s/%s)", msg_id, retries, max_retries)
                        if retries >= max_retries:
                            # Move to DLQ with reason and acknowledge+delete
                            payload_json = parsed.get("payload")
                            try:
                                payload_obj = json.loads(payload_json) if payload_json else {}
                            except Exception:
                                payload_obj = {"_raw": payload_json}
                            await move_to_dlq(msg_id, payload_obj, reason=f"exceeded {max_retries} retries")
                            await client.xack(STREAM_KEY, GROUP_NAME, msg_id)
                            await client.xdel(STREAM_KEY, msg_id)
                            await client.delete(retries_key)
        except asyncio.CancelledError:
            logger.info("Worker '%s' cancelled, shutting down.", consumer_name)
            break
        except Exception:
            logger.exception("Worker main loop error, sleeping briefly before retrying")
            await asyncio.sleep(1)


if __name__ == "__main__":
    import sys

    # Allow optional args: consumer_name and max_retries
    cname = None
    m_retries = DEFAULT_MAX_RETRIES
    if len(sys.argv) >= 2:
        cname = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            m_retries = int(sys.argv[2])
        except Exception:
            pass

    logger.info("Starting worker (consumer=%s, max_retries=%s)...", cname or "auto", m_retries)
    try:
        asyncio.run(worker_loop(consumer_name=cname, max_retries=m_retries))
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user; exiting.")
