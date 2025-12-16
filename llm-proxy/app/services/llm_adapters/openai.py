from typing import Optional
import logging
import pprint
from app.core.config import AppConfig
from app.models.schemas import ChatCompletionRequest

from .base import BaseLLMAdapter

logger = logging.getLogger("llm-proxy")

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # ty:ignore[invalid-assignment, unused-ignore-comment]


class OpenAIAdapter(BaseLLMAdapter):
    async def get_models(self) -> list:
        # Сначала пробуем получить список моделей с OpenAI
        try:
            models_resp = await self.client.models.list()
            models_list = []
            for model in models_resp.data:
                # Преобразуем к формату LLMModel-friendly (минимально)
                if model.id.startswith("gpt-"):
                    models_list.append(
                        {
                            "id": model.id,
                            "name": model.id,
                            "provider": "OpenAI",
                            "context_length": 8192,
                            "is_available": True,
                        }
                    )
            if models_list:
                return models_list
        except Exception as e:
            logger.warning(
                f"[OpenAIAdapter] Cannot fetch list of models, fallback to defaults: {e}"
            )
        # fallback (ручной список)
        return [
            {
                "id": "gpt-4",
                "name": "GPT-4",
                "provider": "OpenAI",
                "context_length": 8192,
                "is_available": True,
            },
            {
                "id": "gpt-3.5-turbo",
                "name": "GPT-3.5 Turbo",
                "provider": "OpenAI",
                "context_length": 4096,
                "is_available": True,
            },
        ]

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        if not AsyncOpenAI:
            raise ImportError("openai>=1.0.0 package not installed. Run 'pip install openai'.")
        self.api_key = api_key or AppConfig.OPENAI_API_KEY
        self.base_url = base_url or AppConfig.OPENAI_BASE_URL
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def chat(self, request: ChatCompletionRequest):
        messages = request.messages or []
        
        # Build parameters to pass to OpenAI
        create_params = {
            "model": request.model,
            "messages": messages,
            "stream": getattr(request, "stream", False)
        }
        
        # Прокидываем tools/functions при наличии
        if getattr(request, "functions", None):
            create_params["functions"] = request.functions
        if getattr(request, "tools", None):
            create_params["tools"] = request.tools

        # Прокидываем function_call/tool_choice при наличии
        if getattr(request, "function_call", None) is not None:
            create_params["function_call"] = request.function_call
        if getattr(request, "tool_choice", None) is not None:
            create_params["tool_choice"] = request.tool_choice

        # Остальные параметры — как есть
        if request.temperature is not None:
            create_params["temperature"] = request.temperature
        if request.max_tokens is not None:
            create_params["max_tokens"] = request.max_tokens
            
        logger.debug(f"[TRACE][OpenAIAdapter] Full llm_request payload:\n" + pprint.pformat(create_params, indent=2, width=120))

     
        if not create_params["stream"]:
            try:
                response = await self.client.chat.completions.create(**create_params)

                logger.debug(f"[TRACE][OpenAIAdapter] Full llm_response:\n" + pprint.pformat(response, indent=2, width=120))
                return [choice.message.model_dump() for choice in response.choices]
            except Exception as e:
                logger.error(f"[OpenAIAdapter] OpenAI error: {e}")
                return f"[Error] OpenAI unavailable: {e}"

        # stream mode
        async def token_gen():
            try:
                stream = await self.client.chat.completions.create(**create_params)
                async for chunk in stream:
                    token = ""
                    try:
                        token = chunk.choices[0].delta.content or ""
                    except Exception:
                        pass
                    if token:
                        yield token
            except Exception as e:
                logger.error(f"[OpenAIAdapter][streaming] error: {e}")
                yield f"[Error] OpenAI stream unavailable: {e}"

        return token_gen()
