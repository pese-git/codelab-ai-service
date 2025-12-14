from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.config import AppConfig, logger
from app.models.schemas import HealthResponse, Message, SessionState
from app.services.llm_stream_service import get_sessions, llm_stream

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

    # Create SessionState if not exists
    if message.session_id not in sessions:
        sessions[message.session_id] = SessionState(
            session_id=message.session_id,
            messages=[{"role": "system", "content": "You are a helpful assistant."}]
        )
    
    # Append user message to session
    sessions[message.session_id].messages.append({"role": "user", "content": message.content})
    
    return EventSourceResponse(llm_stream(message.session_id))
