import json
import logging
from typing import Any, AsyncGenerator, Dict, List

import httpx

from app.core.config import AppConfig
from app.models.schemas import SSEToken

logger = logging.getLogger("agent-runtime")

# In-memory session store (session_id -> list of messages)
sessions: Dict[str, List[Dict[str, Any]]] = {}


def get_sessions():
    return sessions


async def llm_stream(session_id: str) -> AsyncGenerator[dict, None]:
    messages = sessions[session_id]
    llm_request = {"model": AppConfig.LLM_MODEL, "messages": messages, "stream": True}
    logger.info(
        f"[Agent] Sending request to LLM Proxy: session_id={session_id}, messages={len(messages)}"
    )

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{AppConfig.LLM_PROXY_URL}/v1/chat/completions",
            json=llm_request,
            headers={
                "Accept": "text/event-stream",
                "X-Internal-Auth": AppConfig.INTERNAL_API_KEY,
            },
        ) as resp:
            resp.raise_for_status()
            logger.info(f"[Agent] Connected to LLM Proxy, status_code={resp.status_code}")
            current_completion = ""
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or line.startswith("event:"):
                    continue
                if line == "[DONE]":
                    messages.append({"role": "assistant", "content": current_completion})
                    logger.info(f"[Agent] Appended final completion to session {session_id}")
                    # Финальный токен с is_final=True
                    yield {
                        "event": "message",
                        "data": SSEToken.model_construct(token="", is_final=True).model_dump_json(),
                    }
                    break
                if line.startswith("data:"):
                    json_str = line[5:].strip()
                    if not json_str.startswith("{"):
                        continue
                    try:
                        chunk = json.loads(json_str)
                        choices = chunk.get("choices", [{}])
                        delta = choices[0].get("delta", {})
                        token = delta.get("content")
                        if token:
                            current_completion += token
                        finish = choices[0].get("finish_reason")
                        sse_token = SSEToken.model_construct(
                            token=token or "", is_final=finish == "stop"
                        )
                        if finish == "stop":
                            messages.append({"role": "assistant", "content": current_completion})
                            logger.info(f"[Agent] Appended final token to session {session_id}")
                        yield {"event": "message", "data": sse_token.model_dump_json()}
                    except Exception as e:
                        logger.error(f"[Agent] Failed to parse chunk JSON: {json_str} ({e})")
                        continue
