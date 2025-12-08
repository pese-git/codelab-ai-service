import json

import httpx
import pytest
import websockets


@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:8000/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["service"] == "gateway"


@pytest.mark.asyncio
async def test_gateway_websocket_stream():
    session_id = "test_py_gateway"
    uri = f"ws://localhost:8000/ws/{session_id}"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "user_message", "content": "pytest streaming websocket"}))
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


@pytest.mark.asyncio
async def test_gateway_websocket_error():
    # Отправляем некорректный JSON — ожидаем ошибку
    session_id = "test_py_gateway_err"
    uri = f"ws://localhost:8000/ws/{session_id}"
    async with websockets.connect(uri) as ws:
        await ws.send("not a json")
        msg = json.loads(await ws.recv())
        assert msg.get("type") == "error"
        assert "Invalid JSON message" in msg.get("content")
