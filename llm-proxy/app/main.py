import asyncio
import logging
from typing import AsyncGenerator, List

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# ----------------- Logging -----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm-proxy")

app = FastAPI(title="LLM Proxy Service")


# ---------------------------------------------------------------------
# Fake LLM Token Generator
# ---------------------------------------------------------------------
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


# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------
class ChatRequest(BaseModel):
    model: str = "gpt-4"
    messages: List[dict]
    stream: bool = False


class ChatResponse(BaseModel):
    message: str
    model: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class LLMModel(BaseModel):
    id: str
    name: str
    provider: str
    context_length: int
    is_available: bool


# ---- SSE Models ----
class TokenChunk(BaseModel):
    type: str = "assistant_message"
    token: str
    is_final: bool = False


class SSEEvent(BaseModel):
    event: str = "message"
    data: str  # JSON-строка внутри data: ... (по спецификации SSE)


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
async def health_check():
    logger.info("[LLM Proxy] Health check called")
    return HealthResponse.model_construct(status="healthy", service="llm-proxy", version="0.1.0")


@app.get("/llm/models", response_model=List[LLMModel])
async def list_models():
    logger.info("[LLM Proxy] List models called")
    return [
        LLMModel.model_construct(
            id="gpt-4",
            name="GPT-4",
            provider="OpenAI",
            context_length=8192,
            is_available=True,
        ),
        LLMModel.model_construct(
            id="claude-2",
            name="Claude 2",
            provider="Anthropic",
            context_length=100000,
            is_available=True,
        ),
    ]


@app.post("/llm/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    last_message = request.messages[-1] if request.messages else {"content": ""}
    content = last_message.get("content", "")
    logger.info(f"[LLM Proxy] Chat request received: {content}, stream={request.stream}")

    if request.stream:
        return StreamingResponse(
            fake_token_generator(f"Echo from LLM: {content}"),
            media_type="text/event-stream",
        )

    return ChatResponse.model_construct(
        message=f"Echo from LLM: {content}",
        model=request.model,
    )


@app.post("/llm/stream")
async def stream_chat(request: ChatRequest, raw_request: Request):
    last_message = request.messages[-1]["content"] if request.messages else ""
    content = f"Echo from LLM: {last_message}"
    logger.info(f"[LLM Proxy] Stream request received for content: {content}")

    async def event_generator():
        logger.info("[LLM Proxy] Starting SSE event generator")
        async for token in fake_token_generator(content):
            chunk = TokenChunk.model_construct(token=token, is_final=False)
            logger.debug(f"[LLM Proxy] Yielding token SSE: {chunk.token}")
            yield sse("message", chunk)

        final_chunk = TokenChunk.model_construct(token="", is_final=True)
        logger.info("[LLM Proxy] Yielding final token SSE")
        yield sse("message", final_chunk)
        logger.info("[LLM Proxy] SSE stream completed")

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
