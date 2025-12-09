from typing import List

from pydantic import BaseModel


class ChatRequest(BaseModel):
    model: str
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
