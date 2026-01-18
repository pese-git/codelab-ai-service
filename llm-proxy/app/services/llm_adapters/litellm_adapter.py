import logging
import pprint
from typing import Optional

from app.core.config import AppConfig
from app.models.schemas import ChatCompletionRequest

from .base import BaseLLMAdapter

logger = logging.getLogger("llm-proxy.litellm_adapter")

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # ty:ignore[invalid-assignment, unused-ignore-comment]


class LiteLLMAdapter(BaseLLMAdapter):
    """
    Адаптер для работы с LiteLLM proxy сервером.
    LiteLLM proxy предоставляет OpenAI-совместимый API для множества LLM провайдеров.
    Используем OpenAI клиент для взаимодействия с proxy.
    """

    def __init__(
        self,
        proxy_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        if not AsyncOpenAI:
            raise ImportError(
                "openai package not installed. Run 'pip install openai' (included with litellm)."
            )

        self.proxy_url = (proxy_url or AppConfig.LITELLM_PROXY_URL).rstrip("/")
        self.api_key = api_key or AppConfig.LITELLM_API_KEY or "dummy-key"
        self.default_model = default_model or AppConfig.DEFAULT_MODEL

        # OpenAI клиент для общения с LiteLLM proxy
        # LiteLLM proxy предоставляет OpenAI-совместимый endpoint
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=f"{self.proxy_url}/v1")

        logger.info(
            f"[LiteLLMAdapter] Initialized with proxy_url={self.proxy_url}, "
            f"default_model={self.default_model}"
        )

    async def get_models(self) -> list:
        """
        Получает список доступных моделей из LiteLLM proxy.
        Если не удается получить список, выбрасывает исключение.
        """
        models_resp = await self.client.models.list()
        models_list = []
        for model in models_resp.data:
            models_list.append(
                {
                    "id": model.id,
                    "name": model.id,
                    "provider": "LiteLLM",
                    "context_length": getattr(model, "context_length", 4096),
                    "is_available": True,
                }
            )

        logger.debug(
            f"[LiteLLMAdapter] Fetched {len(models_list)} models from proxy:\n"
            + pprint.pformat(models_list, indent=2, width=120)
        )

        return models_list

    async def chat(self, request: ChatCompletionRequest):
        """
        Выполняет chat completion запрос через LiteLLM proxy.
        Поддерживает streaming и non-streaming режимы, а также tool calling.
        """
        # Используем модель из запроса или по умолчанию
        model = request.model or self.default_model

        # Конвертируем сообщения в dict формат, сохраняя все поля
        messages = request.messages or []
        messages_dicts = [
            msg.model_dump(exclude_none=True) if hasattr(msg, "model_dump") else msg
            for msg in messages
        ]

        # Формируем параметры запроса
        create_params = {
            "model": model,
            "messages": messages_dicts,
            "stream": getattr(request, "stream", False),
        }

        # Прокидываем дополнительные параметры
        if request.temperature is not None:
            create_params["temperature"] = request.temperature
        if request.max_tokens is not None:
            create_params["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            create_params["top_p"] = request.top_p
        if request.presence_penalty is not None:
            create_params["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty is not None:
            create_params["frequency_penalty"] = request.frequency_penalty
        if request.stop is not None:
            create_params["stop"] = request.stop

        # Поддержка tool calling и function calling
        if getattr(request, "functions", None):
            create_params["functions"] = request.functions
        if getattr(request, "tools", None):
            create_params["tools"] = request.tools
        if getattr(request, "function_call", None) is not None:
            create_params["function_call"] = request.function_call
        if getattr(request, "tool_choice", None) is not None:
            create_params["tool_choice"] = request.tool_choice

        logger.debug(
            "[TRACE][LiteLLMAdapter] Full llm_request payload:\n"
            + pprint.pformat(create_params, indent=2, width=120)
        )

        # Non-streaming режим
        if not create_params["stream"]:
            try:
                response = await self.client.chat.completions.create(**create_params)

                logger.debug(
                    "[TRACE][LiteLLMAdapter] Full llm_response:\n"
                    + pprint.pformat(response, indent=2, width=120)
                )

                # Возвращаем полный ответ с usage данными
                return response.model_dump()

            except Exception as e:
                logger.error(f"[LiteLLMAdapter] Completion error: {e}", exc_info=True)
                logger.error(
                    f"[LiteLLMAdapter][EXCEPTION chat.non-stream] Locals:\n"
                    + pprint.pformat(locals(), indent=2, width=120)
                )
                return f"[Error] LiteLLM proxy unavailable: {e}"

        # Streaming режим
        async def token_gen():
            try:
                stream = await self.client.chat.completions.create(**create_params)
                async for chunk in stream:
                    token = ""
                    try:
                        # Извлекаем контент из delta
                        if chunk.choices and chunk.choices[0].delta.content:
                            token = chunk.choices[0].delta.content
                    except Exception:
                        logger.error(
                            "[LiteLLMAdapter][stream] chunk parse error", exc_info=True
                        )
                        logger.error(
                            f"[LiteLLMAdapter][stream] chunk:\n"
                            + pprint.pformat(chunk, indent=2, width=120)
                        )

                    if token:
                        logger.debug(f"[LiteLLMAdapter][stream] yield token: {token}")
                        yield token

            except Exception as e:
                logger.error(f"[LiteLLMAdapter][streaming] error: {e}", exc_info=True)
                logger.error(
                    f"[LiteLLMAdapter][EXCEPTION stream] Locals:\n"
                    + pprint.pformat(locals(), indent=2, width=120)
                )
                yield f"[Error] LiteLLM proxy stream unavailable: {e}"

        return token_gen()
