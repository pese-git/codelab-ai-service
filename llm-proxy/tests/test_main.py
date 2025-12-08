import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:8002/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["service"] == "llm-proxy"


@pytest.mark.asyncio
async def test_llm_models():
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:8002/llm/models")
        assert r.status_code == 200
        models = r.json()
        assert isinstance(models, list)
        assert any(m["id"] == "gpt-4" for m in models)


@pytest.mark.asyncio
async def test_llm_chat_echo():
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Echo test"}],
        "stream": False,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8002/llm/chat", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "Echo test" in data["message"]


@pytest.mark.asyncio
async def test_llm_stream():
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "stream this sentence"}],
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        async with client.stream("POST", "http://localhost:8002/llm/stream", json=payload) as resp:
            assert resp.status_code == 200
            seen_tokens = []
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    seen_tokens.append(data["token"])
                    if data.get("is_final"):
                        break
    assert any(t.strip() for t in seen_tokens)
    assert seen_tokens[-1] == ""  # финальный токен


@pytest.mark.asyncio
async def test_llm_chat_validation():
    # Нет messages
    payload = {"model": "gpt-4"}
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8002/llm/chat", json=payload)
        assert r.status_code == 422

    # Нет model
    payload = {"messages": [{"role": "user", "content": "fail"}]}
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8002/llm/chat", json=payload)
        assert r.status_code == 422
