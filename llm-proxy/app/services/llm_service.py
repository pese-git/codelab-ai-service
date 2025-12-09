import asyncio
import logging
from typing import AsyncGenerator

from app.models.schemas import BaseModel

logger = logging.getLogger("llm-proxy")


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
