import logging

from app.models.schemas import BaseModel

logger = logging.getLogger("llm-proxy")


def sse(event: str, payload: BaseModel) -> dict:
    payload_json = payload.model_dump_json()
    logger.debug(f"[LLM Proxy] Sending SSE event '{event}': {payload_json}")
    return {
        "event": event,
        "data": payload_json,  # обязательно ключ "data"
    }
