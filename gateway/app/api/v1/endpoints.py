import json
import httpx
from fastapi import APIRouter, WebSocket, status, Depends, Request
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from app.core.config import AppConfig, logger
from app.models.websocket import (
    WSErrorResponse,
    WSUserMessage,
    WSToolResult,
    WSAgentSwitched,
    WSSwitchAgent,
    WSHITLDecision
)
from app.models.rest import HealthResponse
from app.core.dependencies import (
    get_session_manager,
    get_token_buffer_manager,
)
from app.services.session_manager import SessionManager
from app.services.token_buffer_manager import TokenBufferManager

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse.model_construct(
        status="healthy", service="gateway", version=AppConfig.VERSION
    )


# ==================== Agent Runtime Proxy Endpoints ====================

@router.get("/agents")
async def list_agents():
    """
    Proxy endpoint: Get list of all registered agents from Agent Runtime.
    
    Proxies to: GET /agents on Agent Runtime
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{AppConfig.AGENT_URL}/agents",
                headers={"X-Internal-Auth": AppConfig.INTERNAL_API_KEY},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Agent Runtime error: {e.response.status_code}, {e.response.text}")
            return JSONResponse(
                status_code=e.response.status_code,
                content={"error": f"Agent Runtime error: {e.response.status_code}"}
            )
        except Exception as e:
            logger.error(f"Error proxying to Agent Runtime: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": f"Gateway error: {str(e)}"}
            )


@router.get("/agents/{session_id}/current")
async def get_current_agent(session_id: str):
    """
    Proxy endpoint: Get current active agent for a session.
    
    Proxies to: GET /agents/{session_id}/current on Agent Runtime
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{AppConfig.AGENT_URL}/agents/{session_id}/current",
                headers={"X-Internal-Auth": AppConfig.INTERNAL_API_KEY},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Agent Runtime error: {e.response.status_code}, {e.response.text}")
            return JSONResponse(
                status_code=e.response.status_code,
                content={"error": f"Agent Runtime error: {e.response.status_code}"}
            )
        except Exception as e:
            logger.error(f"Error proxying to Agent Runtime: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": f"Gateway error: {str(e)}"}
            )


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """
    Proxy endpoint: Get message history for a session.
    
    Proxies to: GET /sessions/{session_id}/history on Agent Runtime
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{AppConfig.AGENT_URL}/sessions/{session_id}/history",
                headers={"X-Internal-Auth": AppConfig.INTERNAL_API_KEY},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Agent Runtime error: {e.response.status_code}, {e.response.text}")
            return JSONResponse(
                status_code=e.response.status_code,
                content={"error": f"Agent Runtime error: {e.response.status_code}"}
            )
        except Exception as e:
            logger.error(f"Error proxying to Agent Runtime: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": f"Gateway error: {str(e)}"}
            )


@router.get("/sessions")
async def list_sessions():
    """
    Proxy endpoint: List all active sessions.
    
    Proxies to: GET /sessions on Agent Runtime
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{AppConfig.AGENT_URL}/sessions",
                headers={"X-Internal-Auth": AppConfig.INTERNAL_API_KEY},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Agent Runtime error: {e.response.status_code}, {e.response.text}")
            return JSONResponse(
                status_code=e.response.status_code,
                content={"error": f"Agent Runtime error: {e.response.status_code}"}
            )
        except Exception as e:
            logger.error(f"Error proxying to Agent Runtime: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": f"Gateway error: {str(e)}"}
            )


# ==================== WebSocket Endpoint ====================

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
    token_buffer_manager: "TokenBufferManager" = Depends(get_token_buffer_manager),
):
    """
    WebSocket endpoint для двунаправленной связи между IDE и Agent через HTTP streaming.
    
    Flow:
    1. IDE отправляет user_message или tool_result через WebSocket
    2. Gateway пересылает в Agent через HTTP streaming (SSE)
    3. Agent отправляет SSE события (assistant_message, tool_call)
    4. Gateway пересылает SSE события в IDE через WebSocket
    """
    await websocket.accept()
    logger.info(f"[{session_id}] WebSocket connected")
    await session_manager.add(session_id, websocket)
    
    try:
        async with httpx.AsyncClient(timeout=AppConfig.AGENT_STREAM_TIMEOUT) as client:
            while True:
                # Получаем сообщение от IDE
                raw_msg = await websocket.receive_text()
                logger.debug(f"[{session_id}] Received WS message: {raw_msg!r}")
                
                try:
                    ide_msg = json.loads(raw_msg)
                    msg_type = ide_msg.get("type")
                    
                    # Валидация сообщения
                    if msg_type == "user_message":
                        msg = WSUserMessage.model_validate(ide_msg)
                        logger.info(f"[{session_id}] Received user_message: role={msg.role}")
                    elif msg_type == "tool_result":
                        msg = WSToolResult.model_validate(ide_msg)
                        logger.info(f"[{session_id}] Received tool_result: call_id={msg.call_id}, has_error={msg.error is not None}")
                    elif msg_type == "switch_agent":
                        msg = WSSwitchAgent.model_validate(ide_msg)
                        logger.info(f"[{session_id}] Received switch_agent: target={msg.agent_type}")
                    elif msg_type == "hitl_decision":
                        msg = WSHITLDecision.model_validate(ide_msg)
                        logger.info(f"[{session_id}] Received hitl_decision: call_id={msg.call_id}, decision={msg.decision}")
                    else:
                        logger.warning(f"[{session_id}] Unknown message type: {msg_type}")
                        err = WSErrorResponse.model_construct(
                            type="error", content=f"Unknown message type: {msg_type}"
                        )
                        await websocket.send_json(err.model_dump())
                        continue
                        
                except Exception as e:
                    logger.error(f"[{session_id}] Failed to parse message: {e}")
                    err = WSErrorResponse.model_construct(
                        type="error", content=f"Invalid JSON message: {str(e)}"
                    )
                    await websocket.send_json(err.model_dump())
                    continue
                
                # Отправляем в Agent через HTTP streaming
                try:
                    logger.debug(f"[{session_id}] Forwarding to Agent via HTTP streaming")
                    async with client.stream(
                        "POST",
                        f"{AppConfig.AGENT_URL}/agent/message/stream",
                        json={"session_id": session_id, "message": ide_msg},
                        headers={"X-Internal-Auth": AppConfig.INTERNAL_API_KEY},
                    ) as response:
                        response.raise_for_status()
                        logger.debug(f"[{session_id}] Agent streaming started, status={response.status_code}")
                        
                        # Читаем SSE stream от Agent и пересылаем в IDE
                        # SSE формат:
                        # event: message
                        # data: {"type": "assistant_message", ...}
                        #
                        # event: done
                        # data: {"status": "completed"}
                        
                        current_event_type = None
                        
                        async for line in response.aiter_lines():
                            # Пустая строка - разделитель SSE событий
                            if not line:
                                current_event_type = None
                                continue
                            
                            # Обрабатываем строку с типом события
                            if line.startswith("event: "):
                                current_event_type = line[7:].strip()
                                logger.debug(f"[{session_id}] SSE event type: {current_event_type}")
                                
                                # Если получили event: done - завершаем обработку stream
                                if current_event_type == "done":
                                    logger.info(f"[{session_id}] Received 'done' event, completing stream")
                                    break
                                
                                continue
                            
                            # Обрабатываем строку с данными
                            if line.startswith("data: "):
                                data_str = line[6:]
                                
                                # Проверяем на специальный маркер [DONE]
                                if data_str == "[DONE]":
                                    logger.info(f"[{session_id}] Received [DONE] marker, completing stream")
                                    break
                                
                                # Парсим JSON данные только для event: message
                                if current_event_type == "message":
                                    try:
                                        data = json.loads(data_str)
                                        msg_type = data.get('type')
                                        logger.debug(f"[{session_id}] Received SSE data: type={msg_type}")
                                        
                                        # Фильтруем null значения, чтобы не отправлять лишние поля
                                        filtered_data = {k: v for k, v in data.items() if v is not None}
                                        
                                        logger.debug(f"[{session_id}] Sending to IDE: {json.dumps(filtered_data, indent=2)}")
                                        
                                        # Пересылаем событие в IDE через WebSocket
                                        await websocket.send_json(filtered_data)
                                        
                                    except json.JSONDecodeError as e:
                                        logger.warning(f"[{session_id}] Failed to parse SSE data: {e}, line={line}")
                                else:
                                    # Для других типов событий (например error) тоже пытаемся парсить
                                    try:
                                        data = json.loads(data_str)
                                        logger.debug(f"[{session_id}] Received SSE data for event '{current_event_type}': {data}")
                                        
                                        # Пересылаем событие в IDE
                                        await websocket.send_json(data)
                                        
                                    except json.JSONDecodeError as e:
                                        logger.warning(f"[{session_id}] Failed to parse SSE data for event '{current_event_type}': {e}")
                                
                                continue
                            
                            # SSE комментарий (heartbeat), игнорируем
                            if line.startswith(":"):
                                logger.debug(f"[{session_id}] SSE heartbeat received")
                                continue
                            
                            # Неизвестный формат строки
                            logger.debug(f"[{session_id}] Ignoring unknown SSE line: {line}")
                        
                        logger.info(f"[{session_id}] Agent streaming completed successfully")
                        
                except httpx.HTTPStatusError as e:
                    logger.error(f"[{session_id}] Agent HTTP error: {e.response.status_code}, {e.response.text}")
                    err = WSErrorResponse.model_construct(
                        type="error", content=f"Agent error: {e.response.status_code}"
                    )
                    await websocket.send_json(err.model_dump())
                except Exception as e:
                    logger.error(f"[{session_id}] Error streaming from Agent: {e}", exc_info=True)
                    err = WSErrorResponse.model_construct(
                        type="error", content=f"Streaming error: {str(e)}"
                    )
                    await websocket.send_json(err.model_dump())
                    
    except WebSocketDisconnect:
        logger.info(f"[{session_id}] WebSocket disconnected")
        await token_buffer_manager.remove(session_id)
        await session_manager.remove(session_id)
    except Exception as e:
        logger.error(f"[{session_id}] WS fatal error: {e}", exc_info=True)
        await token_buffer_manager.remove(session_id)
        await session_manager.remove(session_id)
