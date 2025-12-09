import logging
import httpx
from typing import Any, AsyncGenerator, Dict, List
from app.models.schemas import SSEToken
from app.core.config import AppConfig

logger = logging.getLogger("agent-runtime")

# In-memory session store (session_id -> list of messages)
sessions: Dict[str, List[Dict[str, Any]]] = {}


def parse_sse_line(line: str) -> SSEToken | None:
    """Parse SSE line from LLM Proxy into SSEToken."""
    line = line.strip()
    if not line.startswith("data: "):
        return None
    try:
        token_event = SSEToken.model_validate_json(line[6:])
        logger.debug(f"[Agent] Parsed SSE token: {token_event.model_dump_json()}")
        return token_event
    except Exception as e:
        logger.error(f"[Agent] Failed to parse SSE line: {line} ({e})")
        return None

def get_sessions():
    return sessions

async def llm_stream(session_id: str) -> AsyncGenerator[dict, None]:
    messages = sessions[session_id]
    llm_request = {"model": "gpt-4", "messages": messages, "stream": True}
    logger.info(
        f"[Agent] Sending request to LLM Proxy: session_id={session_id}, messages={len(messages)}"
    )

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{AppConfig.LLM_PROXY_URL}/llm/stream",
            json=llm_request,
            headers={
                "Accept": "text/event-stream",
                "X-Internal-Auth": AppConfig.INTERNAL_API_KEY,
            },
        ) as resp:
            resp.raise_for_status()
            logger.info(f"[Agent] Connected to LLM Proxy, status_code={resp.status_code}")

            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or line.startswith("event:"):
                    continue

                if line.startswith("data:"):
                    json_str = line[6:].strip()
                    if not json_str.startswith("{"):
                        continue
                    try:
                        token_event = SSEToken.model_validate_json(json_str)
                        logger.info(f"[Agent] Parsed token: {token_event.model_dump_json()}")
                    except Exception as e:
                        logger.error(f"[Agent] Failed to parse token JSON: {json_str} ({e})")
                        continue

                    if token_event.is_final:
                        full_content = "".join(
                            [t["content"] for t in messages if t.get("role") == "assistant"]
                            + [token_event.token]
                        )
                        messages.append({"role": "assistant", "content": full_content})
                        logger.info(f"[Agent] Appended final token to session {session_id}")

                    yield {
                        "event": "message",
                        "data": token_event.model_dump_json(),
                    }