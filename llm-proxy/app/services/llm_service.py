import logging
import pprint

from app.models.schemas import BaseModel

logger = logging.getLogger("llm-proxy")


def sse(event: str, payload: BaseModel) -> dict:
    try:
        payload_json = payload.model_dump_json()
        logger.debug(f"[LLM Proxy] Sending SSE event '{event}'. Payload object:\n" + pprint.pformat(payload.model_dump(), indent=2, width=120))
        result = {
            "event": event,
            "data": payload_json,  # обязательно ключ "data"
        }
        logger.debug(f"[LLM Proxy] SSE result: {pprint.pformat(result, indent=2, width=120)}")
        return result
    except Exception as e:
        logger.error(f"[LLM Proxy] Exception in sse(event={event}): {e}", exc_info=True)
        logger.error(f"[LLM Proxy] Locals at exception:\n" + pprint.pformat(locals(), indent=2, width=120))
        raise
