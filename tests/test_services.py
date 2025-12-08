import asyncio
import json

import httpx
import pytest
import websockets


@pytest.mark.asyncio
@pytest.mark.parametrize("base_url,service", [
    ("http://localhost:8000", "gateway"),
    ("http://localhost:8001", "agent-runtime"),
    ("http://localhost:8002", "llm-proxy"),
])
async def test_health(base_url, service):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{base_url}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["service"] == service

@pytest.mark.asyncio
async def test_llm_models():
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:8002/llm/models")
        assert r.status_code == 200
        models = r.json()
        assert isinstance(models, list)
        assert any(m["id"] == "gpt-4" for m in models)

@pytest.mark.asyncio
async def test_llm_stream_sse():
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "stream please"}],
        "stream": True
    }
    async with httpx.AsyncClient(timeout=10) as client:
        async with client.stream("POST", "http://localhost:8002/llm/stream", json=payload) as resp:
            assert resp.status_code == 200
            tokens = []
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    tokens.append(data["token"])
                    if data.get("is_final"):
                        break
    assert any(t.strip() for t in tokens)

@pytest.mark.asyncio
async def test_agent_message_stream():
    session_id = "test_py_agent"
    payload = {"session_id": session_id, "type": "user_message", "content": "pytest streaming"}
    async with httpx.AsyncClient(timeout=10) as client:
        async with client.stream("POST", "http://localhost:8001/agent/message/stream", json=payload) as resp:
            assert resp.status_code == 200
            got_final = False
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    if data.get("is_final"):
                        got_final = True
                        break
    assert got_final

@pytest.mark.asyncio
async def test_gateway_websocket_stream():
    session_id = "test_websocket_py"
    uri = f"ws://localhost:8000/ws/{session_id}"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            "type": "user_message",
            "content": "pytest streaming websocket"
        }))
        tokens, got_final = [], False
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "assistant_message":
                tokens.append(msg.get("token", ""))
                if msg.get("is_final"):
                    got_final = True
                    break
    assert any(t.strip() for t in tokens)
    assert got_final
