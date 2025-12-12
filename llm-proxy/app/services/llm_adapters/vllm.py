from typing import Optional
import logging
import os
import httpx
import openai

from app.core.config import AppConfig
from app.models.schemas import ChatCompletionRequest
from .base import BaseLLMAdapter

logger = logging.getLogger("llm-proxy")

class VLLMAdapter(BaseLLMAdapter):
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        # Для openai библиотеки нужно явно прописать base_url как OPENAI_API_BASE
        self.base_url = base_url or AppConfig.VLLM_BASE_URL or "http://localhost:8000/v1"
        self.api_key = api_key or getattr(AppConfig, "VLLM_API_KEY", None) or os.getenv("VLLM_API_KEY", "")
        # openai библиотека берёт настройки из окружения, но подстраховываемся:
        openai.api_key = self.api_key or "EMPTY_KEY"
        openai.api_base = self.base_url

    async def get_models(self) -> list:
        # Этот endpoint отсутствует у openai, реализуем через httpx
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            try:
                response = await client.get("/models")
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
        # Стандартная переменная base API в openai
        from openai import AsyncOpenAI
        oa_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        # Удаляем ключи со значением None как того требует OpenAI/vllm API
        messages = [{k: v for k, v in m.dict().items() if v is not None} for m in request.messages]
        payload = {
            "model": request.model,
            "messages": messages,
            "stream": getattr(request, "stream", False),
        }
        logger.debug(f"[DEBUG VLLM PAYLOAD] {payload}")
        if not payload["stream"]:
            try:
                response = await oa_client.chat.completions.create(**payload)
                logger.debug(f"[DEBUG VLLM RESPONSE] {response}")
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"[VLLMAdapter] error: {e}")
                return f"[Error] vLLM unavailable: {e}"
        # stream mode
        async def token_gen():
            try:
                async for chunk in await oa_client.chat.completions.create(**payload):
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        yield token
            except Exception as e:
                logger.error(f"[VLLMAdapter][stream] error: {e}")
                yield f"[Error] vLLM stream unavailable: {e}"
        return token_gen()
