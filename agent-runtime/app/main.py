import logging
import os
from typing import Any, AsyncGenerator, Dict, List

import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# ----------------- Logging -----------------
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("agent-runtime")

app = FastAPI(title="Agent Runtime Service")

LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "http://localhost:8002")

# session_id → list(messages)
sessions: Dict[str, List[Dict[str, Any]]] = {}


# ----------------- Models -----------------
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class Message(BaseModel):
    session_id: str
    type: str
    content: str


class MessageResponse(BaseModel):
    status: str
    message: str


class SSEToken(BaseModel):
    token: str
    is_final: bool
    type: str = "assistant_message"


# ----------------- Helpers -----------------
def parse_sse_line(line: str) -> SSEToken | None:
    """Парсим строку SSE от LLM Proxy в SSEToken"""
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


# ----------------- Streaming -----------------
async def llm_stream(session_id: str) -> AsyncGenerator[dict, None]:
    messages = sessions[session_id]
    llm_request = {"model": "gpt-4", "messages": messages, "stream": True}
    logger.info(
        f"[Agent] Sending request to LLM Proxy: session_id={session_id}, messages={len(messages)}"
    )

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{LLM_PROXY_URL}/llm/stream",
            json=llm_request,
            headers={"Accept": "text/event-stream"},
        ) as resp:
            resp.raise_for_status()
            logger.info(f"[Agent] Connected to LLM Proxy, status_code={resp.status_code}")

            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or line.startswith("event:"):
                    continue

                # Парсим JSON после 'data: '
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

                    # Обновляем сессию при финальном токене
                    if token_event.is_final:
                        full_content = "".join(
                            [t["content"] for t in messages if t.get("role") == "assistant"]
                            + [token_event.token]
                        )
                        messages.append({"role": "assistant", "content": full_content})
                        logger.info(f"[Agent] Appended final token to session {session_id}")

                    # Возвращаем словарь для EventSourceResponse
                    yield {
                        "event": "message",
                        "data": token_event.model_dump_json(),  # ровно один уровень data
                    }


# ----------------- Endpoints -----------------
@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    logger.info("[Agent] Health check called")
    return HealthResponse.model_construct(
        status="healthy", service="agent-runtime", version="0.1.0"
    )


@app.post("/agent/message/stream")
async def message_stream(message: Message):
    logger.info(
        f"[Agent] Incoming message stream: session_id={message.session_id}, content={message.content}"
    )
    sessions.setdefault(message.session_id, [])
    sessions[message.session_id].append({"role": "user", "content": message.content})
    return EventSourceResponse(llm_stream(message.session_id))


# ----------------- Main -----------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
