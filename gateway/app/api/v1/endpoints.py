import json

import httpx
from fastapi import APIRouter, WebSocket, Request, status
from starlette.websockets import WebSocketDisconnect

from app.core.config import AppConfig, logger
from app.models.schemas import HealthResponse, WSErrorResponse, WSUserMessage, WSToolResult, WSToolCall
from app.services.stream_service import get_token_buffers, stream_agent_single

router = APIRouter()

# Simple in-memory mapping: session_id -> websocket
active_websockets = {}

# In-memory storage for waiting tool results
timeout_seconds = 30  # how long to wait for tool_result
pending_tool_results = {}  # call_id: Future


@router.post("/tool/execute/{session_id}", status_code=status.HTTP_202_ACCEPTED)
async def tool_execute(session_id: str, tool_call: WSToolCall):
    logger.debug(f"ToolCall request payload: {tool_call.model_dump()}")
    ws = active_websockets.get(session_id)
    if ws is None:
        return {"status": "error", "detail": f"Session {session_id} not found"}
    import asyncio
    call_id = tool_call.call_id
    fut = asyncio.get_event_loop().create_future()
    pending_tool_results[call_id] = fut
    await ws.send_json(tool_call.model_dump())
    try:
        result = await asyncio.wait_for(fut, timeout=timeout_seconds)
        return {"status": "ok", "result": result}
    except asyncio.TimeoutError:
        pending_tool_results.pop(call_id, None)
        return {"status": "error", "detail": f"Timeout waiting for tool_result (call_id={call_id})"}
    finally:
        # После завершения очищаем future
        pending_tool_results.pop(call_id, None)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse.model_construct(
        status="healthy", service="gateway", version=AppConfig.VERSION
    )


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info(f"[{session_id}] WebSocket connected")
    active_websockets[session_id] = websocket
    token_buffers = get_token_buffers()
    try:
        async with httpx.AsyncClient() as client:
            while True:
                raw_msg = await websocket.receive_text()
                logger.debug(f"[{session_id}] Received WS message: {raw_msg!r}")
                try:
                    # Пробуем разобрать как tool_result
                    try:
                        tool_result = WSToolResult.model_validate(json.loads(raw_msg))
                        logger.debug(f"[{session_id}] Parsed WSToolResult: {tool_result}")
                        # Если есть ожидающий Future — выполнить его
                        fut = pending_tool_results.pop(tool_result.call_id, None)
                        if fut and not fut.done():
                            fut.set_result(tool_result.result)
                        await websocket.send_json({"status": "ok", "detail": f"tool_result for call_id={tool_result.call_id} received"})
                        continue
                    except Exception:
                        pass  # не tool_result, идём обычным путём
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
                    await stream_agent_single(client, session_id, msg, websocket)
                except Exception as e:
                    err = WSErrorResponse.model_construct(type="error", content=str(e))
                    await websocket.send_json(err.model_dump())
                    logger.error(f"[{session_id}] Error streaming: {e}")
    except WebSocketDisconnect:
        logger.info(f"[{session_id}] WebSocket disconnected")
        token_buffers.pop(session_id, None)
        active_websockets.pop(session_id, None)
    except Exception as e:
        logger.error(f"[{session_id}] WS fatal error: {e}")
