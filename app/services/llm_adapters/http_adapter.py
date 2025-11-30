import asyncio
import httpx
from app.core.config import settings

async def run_stage(stage_name: str, payload: dict, seed: int = 42) -> dict:
    # Minimal HTTP adapter that posts the payload to configured LLM_HTTP_URL
    # For tests, this will often be monkeypatched, so keep implementation simple.
    url = getattr(settings, "LLM_HTTP_URL", None)
    timeout = getattr(settings, "LLM_TIMEOUT_SEC", 20)
    if not url:
        raise RuntimeError("LLM_HTTP_URL is not configured")
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json={"stage": stage_name, "payload": payload, "seed": seed})
        resp.raise_for_status()
        return resp.json()
