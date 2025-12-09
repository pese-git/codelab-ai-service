import json

import httpx
from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.core.config import AppConfig, logger
from app.models.schemas import HealthResponse, WSErrorResponse, WSUserMessage
from app.services.stream_service import get_token_buffers, stream_agent_sse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse.model_construct(
        status="healthy", service="gateway", version=AppConfig.VERSION
    )


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info(f"[{session_id}] WebSocket connected")
    token_buffers = get_token_buffers()
    try:
        async with httpx.AsyncClient() as client:
            while True:
                raw_msg = await websocket.receive_text()
                logger.debug(f"[{session_id}] Received WS message: {raw_msg!r}")
                try:
                    msg = WSUserMessage.model_validate(json.loads(raw_msg))
                    logger.debug(f"[{session_id}] Parsed WSUserMessage: {msg}")
                except Exception:
                    err = WSErrorResponse.model_construct(
                        type="error", content="Invalid JSON message"
                    )
                    await websocket.send_json(err.model_dump())
                    logger.warning(f"[{session_id}] Invalid WS JSON, sent error")
                    continue
                try:
                    await stream_agent_sse(client, session_id, msg, websocket)
                except Exception as e:
                    err = WSErrorResponse.model_construct(type="error", content=str(e))
                    await websocket.send_json(err.model_dump())
                    logger.error(f"[{session_id}] Error streaming: {e}")
    except WebSocketDisconnect:
        logger.info(f"[{session_id}] WebSocket disconnected")
        token_buffers.pop(session_id, None)
    except Exception as e:
        logger.error(f"[{session_id}] WS fatal error: {e}")
