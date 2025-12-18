import json
import httpx
from fastapi import APIRouter, WebSocket, status, Depends
from starlette.websockets import WebSocketDisconnect

from app.core.config import AppConfig, logger
from app.models.websocket import WSErrorResponse, WSUserMessage, WSToolResult, WSToolCall
from app.models.rest import HealthResponse
from app.services.stream_service import stream_agent_single
from app.core.dependencies import (
    get_session_manager,
    get_tool_result_manager,
    get_token_buffer_manager,
)
from app.services.session_manager import SessionManager
from app.services.tool_result_manager import ToolResultManager
from app.services.token_buffer_manager import TokenBufferManager

router = APIRouter()

timeout_seconds = 30  # how long to wait for tool_result

@router.post("/tool/execute/{session_id}", status_code=status.HTTP_202_ACCEPTED)
async def tool_execute(
    session_id: str,
    tool_call: WSToolCall,
    session_manager: SessionManager = Depends(get_session_manager),
    tool_result_manager: ToolResultManager = Depends(get_tool_result_manager)
):
    logger.debug(f"ToolCall request payload: {tool_call.model_dump()}")
    ws = await session_manager.get(session_id)
    if ws is None:
        return {"status": "error", "detail": f"Session {session_id} not found"}
    call_id = tool_call.call_id
    fut = await tool_result_manager.register(call_id)
    await ws.send_json(tool_call.model_dump())
    import asyncio
    try:
        result = await asyncio.wait_for(fut, timeout=timeout_seconds)
        return {"status": "ok", "result": result}
    except asyncio.TimeoutError:
        await tool_result_manager.pop(call_id)
        return {"status": "error", "detail": f"Timeout waiting for tool_result (call_id={call_id})"}
    finally:
        await tool_result_manager.pop(call_id)

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse.model_construct(
        status="healthy", service="gateway", version=AppConfig.VERSION
    )

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
    tool_result_manager: ToolResultManager = Depends(get_tool_result_manager),
    token_buffer_manager: "TokenBufferManager" = Depends(get_token_buffer_manager),
):
    await websocket.accept()
    logger.info(f"[{session_id}] WebSocket connected")
    await session_manager.add(session_id, websocket)
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
                        await tool_result_manager.resolve(tool_result.call_id, tool_result.result)
                        await websocket.send_json(
                            {"status": "ok", "detail": f"tool_result for call_id={tool_result.call_id} received"}
                        )
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
        await token_buffer_manager.remove(session_id)
        await session_manager.remove(session_id)
    except Exception as e:
        logger.error(f"[{session_id}] WS fatal error: {e}")
