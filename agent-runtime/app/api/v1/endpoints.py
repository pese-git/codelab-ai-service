import pprint
import traceback

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.config import AppConfig, logger
from app.models.schemas import HealthResponse, Message
from app.services.chat_service import get_chat_service, ChatService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    logger.info("[Agent] Health check called")
    return HealthResponse.model_construct(
        status="healthy", service="agent-runtime", version=AppConfig.VERSION
    )


@router.post("/agent/message/stream")
async def message_stream(message: Message, chat_service: ChatService = Depends(get_chat_service)):
    try:
        result = await chat_service.stream_message(message)
        return JSONResponse(content=result)
    except Exception:
        logger.error(f"[TRACE][ERROR] Exception in /agent/message/stream\n{traceback.format_exc()}")
        return JSONResponse(content={"error": "Internal server error"}, status_code=500)
