import logging
import os
import pprint
from typing import AsyncGenerator, Optional

import openai

from app.core.config import AppConfig
from app.models.schemas import ChatCompletionRequest

from .base import BaseLLMAdapter

logger = logging.getLogger("llm-proxy.vllm_adapter")


class VLLMAdapter(BaseLLMAdapter):
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        # Для openai библиотеки нужно явно прописать base_url как OPENAI_API_BASE
        self.base_url = base_url or AppConfig.VLLM_BASE_URL or "http://localhost:8000/v1"
        self.api_key = (
            api_key or getattr(AppConfig, "VLLM_API_KEY", None) or os.getenv("VLLM_API_KEY", "")
        )
        # openai библиотека берёт настройки из окружения, но подстраховываемся:
        openai.api_key = self.api_key or "EMPTY_KEY"
        openai.api_base = self.base_url

    async def get_models(self) -> list:
        from openai import AsyncOpenAI

        oa_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        try:
            response = await oa_client.models.list()
            models = []
            for model in response.data:
                models.append(
                    {
                        "id": model.id,
                        "name": model.id,
                        "provider": "vLLM",
                        "context_length": getattr(model, "context_length", 8192),
                        "is_available": True,
                    }
                )
            logger.debug(f"[VLLMAdapter] Models fetched: {pprint.pformat(models, indent=2, width=120)}")
            return models or []
        except Exception as e:
            logger.warning(f"[VLLMAdapter] Cannot fetch models: {e}", exc_info=True)
            logger.debug(f"[VLLMAdapter][EXCEPTION get_models] Locals: {pprint.pformat(locals(), indent=2, width=120)}")
            return []

    async def chat(self, request: ChatCompletionRequest) -> str | AsyncGenerator[str, None]:
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
        logger.debug(f"[TRACE][VLLMAdapter] Full llm_request payload:\n" + pprint.pformat(payload, indent=2, width=120))
        if not payload["stream"]:
            try:
                response = await oa_client.chat.completions.create(**payload, timeout=600)
                logger.debug(f"[TRACE][VLLMAdapter] Full llm_response:\n" + pprint.pformat(response, indent=2, width=120))
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"[VLLMAdapter] error: {e}", exc_info=True)
                logger.error(f"[VLLMAdapter][EXCEPTION chat.non-stream] Locals: {pprint.pformat(locals(), indent=2, width=120)}")
                return f"[Error] vLLM unavailable: {e}"

        # stream mode
        async def token_gen():
            try:
                stream = await oa_client.chat.completions.create(**payload, timeout=600)
                async for chunk in stream:
                    logger.debug(f"[VLLMAdapter][stream] chunk: {pprint.pformat(chunk, indent=2, width=120)}")
                    token = None
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        logger.debug(f"[VLLMAdapter][stream] yield token: {token}")
                        yield token
            except Exception as e:
                logger.error(f"[VLLMAdapter][stream] error: {e}", exc_info=True)
                logger.error(f"[VLLMAdapter][EXCEPTION stream] Locals: {pprint.pformat(locals(), indent=2, width=120)}")
                yield f"[Error] vLLM stream unavailable: {e}"

        return token_gen()
