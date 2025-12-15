import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:8001/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["service"] == "agent-runtime"


@pytest.mark.asyncio
async def test_agent_message_stream_echo():
    correct_key = "my-super-secret-key"
    session_id = "pytest_stream"
    payload = {"session_id": session_id, "type": "user_message", "content": "This is stream test!"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "http://localhost:8001/agent/message/stream",
            json=payload,
            headers={"X-Internal-Auth": correct_key},
        )
        assert resp.status_code == 200
        data = resp.json()
    assert "token" in data
    assert data["token"] and data["token"].strip()
    assert data["type"] in ("assistant_message", "tool_call")


@pytest.mark.asyncio
async def test_agent_message_stream_missing_fields():
    correct_key = "my-super-secret-key"
    # Session ID не передан
    payload = {"type": "user_message", "content": "missing session"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "http://localhost:8001/agent/message/stream",
            json=payload,
            headers={"X-Internal-Auth": correct_key},
        )
        assert r.status_code == 422

    # Content не передан
    payload = {"session_id": "pytest", "type": "user_message"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "http://localhost:8001/agent/message/stream",
            json=payload,
            headers={"X-Internal-Auth": correct_key},
        )
        assert r.status_code == 422
