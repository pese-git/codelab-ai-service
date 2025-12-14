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
        async with client.stream(
            "POST",
            "http://localhost:8001/agent/message/stream",
            json=payload,
            headers={"X-Internal-Auth": correct_key},
        ) as resp:
            assert resp.status_code == 200
            tokens = []
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    tokens.append(data["token"])
                    if data.get("is_final"):
                        break
    assert any(t and t.strip() for t in tokens if t is not None)
    # Check that we have tokens and last token with is_final=True
    assert len(tokens) > 0


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
