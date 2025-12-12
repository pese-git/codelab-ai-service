from typing import Optional
import logging
import httpx

from app.core.config import AppConfig
from app.models.schemas import ChatCompletionRequest

from .base import BaseLLMAdapter

logger = logging.getLogger("llm-proxy")

class VLLMAdapter(BaseLLMAdapter):
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url or AppConfig.VLLM_BASE_URL or "http://localhost:8000/v1"
        self.api_key = api_key or getattr(AppConfig, "VLLM_API_KEY", None)
        self._client = httpx.AsyncClient(base_url=self.base_url)

    async def get_models(self) -> list:
        try:
            response = await self._client.get("/models")
            response.raise_for_status()
            data = response.json()
            models = []
            for model in data.get("data", []):
                models.append({
                    "id": model.get("id"),
                    "name": model.get("id"),
                    "provider": "vLLM",
                    "context_length": 8192,
                    "is_available": True,
                })
            return models or [
                {
                    "id": "local-vllm",
                    "name": "Local vLLM Model",
                    "provider": "vLLM",
                    "context_length": 8192,
                    "is_available": True,
                }
            ]
        except Exception as e:
            logger.warning(f"[VLLMAdapter] Cannot fetch models: {e}")
            return [
                {
                    "id": "local-vllm",
                    "name": "Local vLLM Model",
                    "provider": "vLLM",
                    "context_length": 8192,
                    "is_available": True,
                }
            ]

    async def chat(self, request: ChatCompletionRequest):
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": request.model,
            "messages": [m.dict() for m in request.messages],
            "stream": getattr(request, "stream", False),
        }
        if not payload["stream"]:
            try:
                response = await self._client.post("/chat/completions", json=payload, headers=headers, timeout=600)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"[VLLMAdapter] error: {e}")
                return f"[Error] vLLM unavailable: {e}"
        # stream mode
        async def token_gen():
            try:
                async with self._client.stream("POST", "/chat/completions", json=payload, headers=headers, timeout=600) as r:
                    async for line in r.aiter_lines():
                        if line.startswith('data:'):  # SSE format
                            data = line.removeprefix('data:').strip()
                            if not data or data == '[DONE]':
                                continue
                            try:
                                obj = httpx.Response(200, content=data).json()
                                token = obj["choices"][0]["delta"].get("content", "")
                                if token:
                                    yield token
                            except Exception as e:
                                logger.warning(f"[VLLMAdapter][stream] bad chunk: {e}")
            except Exception as e:
                logger.error(f"[VLLMAdapter][stream] error: {e}")
                yield f"[Error] vLLM stream unavailable: {e}"
        return token_gen()
