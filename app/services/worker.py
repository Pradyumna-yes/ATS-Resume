# app/services/worker.py
import asyncio
import json
import logging
import redis.asyncio as aioredis
from app.core.config import settings
from app.services.pipeline import run_assessment_pipeline

logger = logging.getLogger(__name__)

async def worker_loop():
    url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    client = aioredis.from_url(url, decode_responses=True)
    logger.info("Worker connected to Redis, waiting for jobs...")
    while True:
        try:
            # BRPOP blocks until an item is available (timeout 5s to allow clean shutdown checks)
            res = await client.brpop("pipeline:queue", timeout=5)
            if not res:
                await asyncio.sleep(0.1)
                continue
            # res is (queue_name, payload_str)
            payload_str = res[1]
            payload = json.loads(payload_str)
            logger.info("Worker popped job: %s", payload)
            # For now, we only have resume_id/jobless flow; fetch resume/job if needed
            # We'll call run_assessment_pipeline with minimal payloads (demo)
            job_payload = {"raw_text": payload.get("raw_text", "")}
            resume_payload = {"file_text": payload.get("file_text", ""), "storage_key": payload.get("storage_key")}
            # run pipeline (mock or real)
            result = await run_assessment_pipeline(job_payload, resume_payload)
            logger.info("Assessment finished: %s", result.get("assessment_id"))
        except Exception as exc:
            logger.exception("Worker error: %s", exc)
            # small backoff on error
            await asyncio.sleep(1)

# helper to run worker in console
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_loop())
