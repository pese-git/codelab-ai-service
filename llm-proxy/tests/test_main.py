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
    headers = {"x-internal-auth": "my-super-secret-key"}
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:8002/v1/llm/models", headers=headers)
        assert r.status_code == 200
        models = r.json()
        assert isinstance(models, list)
        # Позволяет проходить тесту для любого модели, например mock-llm или gpt-4
        assert any("id" in m for m in models)


@pytest.mark.asyncio
async def test_llm_chat_echo():
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Echo test"}],
        "stream": False,
        "temperature": 1
    }
    headers = {"x-internal-auth": "my-super-secret-key"}
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8002/v1/chat/completions", json=payload, headers=headers)
        assert r.status_code == 200
        data = r.json()
        # Находим "Echo test" по всей ответной структуре
        assert any("Echo test" in str(value) for value in data.values())


@pytest.mark.asyncio
async def test_llm_stream():
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "stream this sentence"}],
        "stream": True,
        "temperature": 1
    }
    headers = {"x-internal-auth": "my-super-secret-key"}
    async with httpx.AsyncClient(timeout=10) as client:
        async with client.stream("POST", "http://localhost:8002/v1/chat/completions", json=payload, headers=headers) as resp:
            assert resp.status_code == 200
            seen_chunks = []
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue  # пропустить пустые строки
                if line.startswith("data:"):
                    data_raw = line[5:].strip()
                    if not data_raw:
                        continue  # пропустить пустые data
                    if data_raw == "[DONE]":
                        break
                    data = json.loads(data_raw)
                    # собираем весь контент кусками
                    for choice in data.get("choices", []):
                        delta = choice.get("delta", {})
                        chunk = delta.get("content")
                        if chunk:
                            seen_chunks.append(chunk)
    assert any(t.strip() for t in seen_chunks)


@pytest.mark.asyncio
async def test_llm_chat_validation():
    # Нет messages
    payload = {"model": "gpt-4"}
    headers = {"x-internal-auth": "my-super-secret-key"}
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8002/v1/chat/completions", json=payload, headers=headers)
        assert r.status_code == 422

    # Нет model
    payload = {"messages": [{"role": "user", "content": "fail"}]}
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8002/v1/chat/completions", json=payload, headers=headers)
        assert r.status_code == 422
