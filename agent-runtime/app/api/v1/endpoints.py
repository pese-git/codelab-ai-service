from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from app.models.schemas import HealthResponse, Message
from app.services.llm_stream_service import llm_stream, get_sessions
from app.core.config import logger, AppConfig

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    logger.info("[Agent] Health check called")
    return HealthResponse.model_construct(
        status="healthy", service="agent-runtime", version=AppConfig.VERSION
    )

@router.post("/agent/message/stream")
async def message_stream(message: Message):
    logger.info(
        f"[Agent] Incoming message stream: session_id={message.session_id}, content={message.content}"
    )
    sessions = get_sessions()
    sessions.setdefault(message.session_id, [])
    sessions[message.session_id].append({"role": "user", "content": message.content})
    return EventSourceResponse(llm_stream(message.session_id))