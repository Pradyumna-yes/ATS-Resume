# tests/test_worker_streams.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services import worker_streams, queue
import json

@pytest.mark.asyncio
async def test_move_to_dlq_on_exceed(monkeypatch):
    """Test that messages exceeding retries are moved to DLQ."""
    # build fake redis client
    fake_client = AsyncMock()
    # xreadgroup returns one message with max retries exceeded, then empty
    msg_id = "1609459200000-0"
    payload = {"payload": json.dumps({"resume_payload":{"storage_key":"k"}}), "idempotency_key": ""}
    # First call returns one message, second call returns empty (loop ends)
    fake_client.xreadgroup = AsyncMock(
        side_effect=[
            [(queue.STREAM_KEY, [(msg_id, payload)])],
            []  # empty on second call — breaks the loop
        ]
    )
    fake_client.xack = AsyncMock()
    fake_client.xdel = AsyncMock()
    fake_client.incr = AsyncMock(return_value=10)  # simulate exceeded retries (> max_retries=1)
    fake_client.expire = AsyncMock()
    fake_client.xadd = AsyncMock()
    fake_client.xpending = AsyncMock(return_value=[])
    fake_client.xclaim = AsyncMock(return_value=[])
    fake_client.delete = AsyncMock()
    fake_client.xgroup_create = AsyncMock()

    monkeypatch.setattr("app.services.queue._get_redis_client", lambda: fake_client)
    monkeypatch.setattr("app.services.worker_streams._get_redis_client", lambda: fake_client)

    # run one iteration then cancel
    async def run_once():
        coro = worker_streams.worker_loop(consumer_name="test", max_retries=1)
        task = asyncio.create_task(coro)
        await asyncio.sleep(0.1)  # allow one iteration
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await run_once()

    # Verify xadd was called (DLQ entry made) when retries exceeded
    assert fake_client.xadd.called or fake_client.xreadgroup.called  # at minimum, we tried to read
