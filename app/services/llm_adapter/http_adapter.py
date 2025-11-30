# app/services/llm_adapters.http_adapter.py
"""
Async HTTP adapter to call an external LLM HTTP endpoint.
Expect JSON request/response. Retries with backoff.

Env configuration:
- LLM_HTTP_URL: required for this adapter
- LLM_API_KEY: optional, sent as Authorization: Bearer <key>
- LLM_TIMEOUT_SEC: request timeout (default 10)
- LLM_RETRIES: number of retries (default 2)
- LLM_BACKOFF_FACTOR: backoff multiplier (default 0.5)
"""

import os
import asyncio
from typing import Dict, Any
import httpx
import json
from app.core.config import settings

LLM_HTTP_URL = getattr(settings, "LLM_HTTP_URL", os.getenv("LLM_HTTP_URL"))
LLM_API_KEY = getattr(settings, "LLM_API_KEY", os.getenv("LLM_API_KEY", None))
TIMEOUT = float(getattr(settings, "LLM_TIMEOUT_SEC", os.getenv("LLM_TIMEOUT_SEC", 10)))
RETRIES = int(getattr(settings, "LLM_RETRIES", os.getenv("LLM_RETRIES", 2)))
BACKOFF = float(getattr(settings, "LLM_BACKOFF_FACTOR", os.getenv("LLM_BACKOFF_FACTOR", 0.5)))

if not LLM_HTTP_URL:
    # raise early if adapter loaded but missing config
    raise RuntimeError("LLM_HTTP_URL unset for http_adapter")

async def _post_once(client: httpx.AsyncClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
    resp = await client.post(LLM_HTTP_URL, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()

async def run_stage(stage_name: str, payload: Dict[str, Any], seed: int = 42) -> Dict[str, Any]:
    """
    Send a payload like:
    { "stage": stage_name, "input": payload, "seed": seed }
    Expect the external service to return JSON dict resembling stage output.
    """
    body = {"stage": stage_name, "input": payload, "seed": seed}
    async with httpx.AsyncClient() as client:
        last_exc = None
        for attempt in range(1, RETRIES + 2):
            try:
                return await _post_once(client, body)
            except Exception as exc:
                last_exc = exc
                if attempt <= RETRIES:
                    await asyncio.sleep(BACKOFF * attempt)
                    continue
                else:
                    raise last_exc
