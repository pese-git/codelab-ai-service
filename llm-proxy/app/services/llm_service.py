import asyncio
import logging
from typing import AsyncGenerator

from app.core.config import AppConfig
from app.models.schemas import BaseModel, ChatRequest

logger = logging.getLogger("llm-proxy")

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


class OpenAIAdapter:
    def __init__(self, api_key: str = None, base_url: str = None):
        if not AsyncOpenAI:
            raise ImportError("openai>=1.0.0 package not installed. Run 'pip install openai'.")
        self.api_key = api_key or AppConfig.OPENAI_API_KEY
        self.base_url = base_url or AppConfig.OPENAI_BASE_URL
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def chat(self, request: ChatRequest) -> str:
        messages = request.messages or []
        try:
            response = await self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                stream=False,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[OpenAIAdapter] OpenAI error: {e}")
            return f"[Error] OpenAI unavailable: {e}"

    async def streaming_generator(self, request: ChatRequest):
        messages = request.messages or []
        try:
            stream = await self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                stream=True,
            )
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


async def fake_token_generator(message: str) -> AsyncGenerator[str, None]:
    """Имитация потоковой генерации токенов."""
    logger.info(f"[LLM Proxy] Starting token generation for message: {message}")
    words = message.split()
    for idx, word in enumerate(words):
        logger.debug(f"[LLM Proxy] Yielding token {idx}: {word}")
        yield word + " "
        await asyncio.sleep(0.2)
    logger.info("[LLM Proxy] Token generation completed")


def sse(event: str, payload: BaseModel) -> dict:
    payload_json = payload.model_dump_json()
    logger.debug(f"[LLM Proxy] Sending SSE event '{event}': {payload_json}")
    return {
        "event": event,
        "data": payload_json,  # обязательно ключ "data"
    }
