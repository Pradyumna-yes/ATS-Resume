# tests/test_llm_adapter.py
import pytest
import asyncio
from importlib import reload
import os
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_mock_adapter_runs():
    # force adapter to mock by env var
    os.environ["LLM_ADAPTER"] = "mock"
    # reload module to pick new env
    from app.services import llm_adapter
    reload(llm_adapter)
    res = await llm_adapter.run_stage("C_RESUME_PARSE", {"file_text":"hi"}, seed=1)
    assert isinstance(res, dict)
    assert "confidence" in res or "skills" in res

@pytest.mark.asyncio
async def test_http_adapter_fallback(monkeypatch, tmp_path):
    # prepare environment
    os.environ["LLM_ADAPTER"] = "http"
    os.environ["LLM_HTTP_URL"] = "https://example.invalid/llm"  # unreachable
    os.environ["LLM_ALLOW_FALLBACK"] = "true"
    # reload
    from importlib import reload
    from app.services import llm_adapter
    reload(llm_adapter)

    # monkeypatch http adapter to raise, and ensure fallback uses mock
    from app.services.llm_adapters import http_adapter, mock_adapter
    async def fake_run(stage, payload, seed=42):
        raise RuntimeError("simulated http failure")
    monkeypatch.setattr("app.services.llm_adapters.http_adapter.run_stage", fake_run)

    res = await llm_adapter.run_stage("D_MATCHER_SCORER", {"jd":{},"resume":{}}, seed=2)
    assert isinstance(res, dict)
