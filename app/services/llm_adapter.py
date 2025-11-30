# app/services/llm_adapter.py
"""
Pluggable LLM adapter loader and facade.

Environment:
- LLM_ADAPTER: "mock" (default) or "http"
- LLM_ALLOW_FALLBACK: "true" or "1" to allow falling back to mock when HTTP adapter fails

Public:
- async def run_stage(stage_name: str, payload: dict, seed: int = 42) -> dict
"""

import os
import importlib
import asyncio
from typing import Any, Dict

from app.core.config import settings

_ADAPTER_NAME = getattr(settings, "LLM_ADAPTER", os.getenv("LLM_ADAPTER", "mock"))
_ALLOW_FALLBACK = str(getattr(settings, "LLM_ALLOW_FALLBACK", os.getenv("LLM_ALLOW_FALLBACK", "true"))).lower() in ("1","true","yes")

_adapter = None

def _load_adapter(name: str):
    global _adapter
    if name == "mock":
        mod = importlib.import_module("app.services.llm_adapters.mock_adapter")
    elif name == "http":
        mod = importlib.import_module("app.services.llm_adapters.http_adapter")
    else:
        # try dynamic import
        mod = importlib.import_module(name)
    # adapter module must implement async run_stage
    if not hasattr(mod, "run_stage"):
        raise RuntimeError(f"Adapter {name} does not expose run_stage()")
    _adapter = mod

# load at import time
try:
    _load_adapter(_ADAPTER_NAME)
except Exception:
    # fall back to mock always if anything goes wrong
    try:
        _load_adapter("mock")
    except Exception as exc:
        raise

async def run_stage(stage_name: str, payload: Dict[str, Any], seed: int = 42) -> Dict[str, Any]:
    """
    Unified entry to call the configured adapter.
    If adapter fails and fallback is allowed, fall back to mock adapter.
    """
    global _adapter
    if _adapter is None:
        _load_adapter(_ADAPTER_NAME)

    try:
        result = await _adapter.run_stage(stage_name, payload, seed=seed)
        return result
    except Exception as exc:
        # if fallback allowed, use mock adapter
        if _ALLOW_FALLBACK:
            try:
                mock = importlib.import_module("app.services.llm_adapters.mock_adapter")
                return await mock.run_stage(stage_name, payload, seed=seed)
            except Exception:
                raise
        raise
