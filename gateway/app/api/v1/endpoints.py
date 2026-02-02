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
    WSHITLDecision,
    WSPlanApprovalRequired,
    WSPlanDecision
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


@router.post("/sessions")
async def create_session():
    """
    Proxy endpoint: Create a new session.
    
    Proxies to: POST /sessions on Agent Runtime
    
    Returns:
        Session information with session_id
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
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


@router.get("/sessions/{session_id}/pending-approvals")
async def get_pending_approvals(session_id: str):
    """
    Proxy endpoint: Get pending approval requests for a session.
    
    This endpoint is used by the IDE to restore pending approvals
    after restart or reinstall.
    
    Proxies to: GET /sessions/{session_id}/pending-approvals on Agent Runtime
    
    Args:
        session_id: Session identifier
        
    Returns:
        List of pending approval requests
    """
    logger.debug(f"Proxying pending-approvals request for session {session_id}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{AppConfig.AGENT_URL}/sessions/{session_id}/pending-approvals",
                headers={"X-Internal-Auth": AppConfig.INTERNAL_API_KEY},
            )
            
            if response.status_code == 404:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Session {session_id} not found"}
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
            logger.error(f"Error proxying pending-approvals request: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": f"Gateway error: {str(e)}"}
            )


@router.get("/events/metrics/session/{session_id}")
async def get_session_metrics(session_id: str):
    """
    Proxy endpoint: Get LLM metrics for a specific session.
    
    Returns detailed metrics about LLM requests for the session:
    - Total requests (successful and failed)
    - Token usage (prompt, completion, total)
    - Average duration
    - Requests with tool calls
    - Individual request details
    
    Proxies to: GET /events/metrics/session/{session_id} on Agent Runtime
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session metrics with aggregated stats and request history
    """
    logger.debug(f"Proxying session metrics request for {session_id}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{AppConfig.AGENT_URL}/events/metrics/session/{session_id}",
                headers={"X-Internal-Auth": AppConfig.INTERNAL_API_KEY},
            )
            
            if response.status_code == 404:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"No metrics found for session {session_id}"}
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
            logger.error(f"Error proxying session metrics request: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": f"Gateway error: {str(e)}"}
            )


@router.get("/events/metrics/sessions")
async def get_all_session_metrics():
    """
    Proxy endpoint: Get list of all sessions with LLM metrics.
    
    Proxies to: GET /events/metrics/sessions on Agent Runtime
    
    Returns:
        List of session IDs that have metrics data
    """
    logger.debug("Proxying all session metrics request")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{AppConfig.AGENT_URL}/events/metrics/sessions",
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
            logger.error(f"Error proxying session metrics list: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": f"Gateway error: {str(e)}"}
            )


@router.get("/events/metrics")
async def get_event_metrics():
    """
    Proxy endpoint: Get metrics collected from events.
    
    Returns metrics automatically collected by MetricsCollector:
    - Agent switches
    - Agent processing durations
    - Tool executions
    - HITL decisions
    - Errors
    
    Proxies to: GET /events/metrics on Agent Runtime
    
    Returns:
        Dictionary with all collected metrics
    """
    logger.debug("Proxying event metrics request")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{AppConfig.AGENT_URL}/events/metrics",
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
            logger.error(f"Error proxying event metrics: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": f"Gateway error: {str(e)}"}
            )


@router.get("/events/audit-log")
async def get_audit_log(
    session_id: str = None,
    event_type: str = None,
    limit: int = 100
):
    """
    Proxy endpoint: Get audit log of critical events.
    
    Proxies to: GET /events/audit-log on Agent Runtime
    
    Args:
        session_id: Filter by session ID (optional)
        event_type: Filter by event type (optional)
        limit: Maximum number of entries (default: 100)
    
    Returns:
        List of audit log entries with filtering
    """
    logger.debug(f"Proxying audit log request: session_id={session_id}, event_type={event_type}")
    
    params = {}
    if session_id:
        params["session_id"] = session_id
    if event_type:
        params["event_type"] = event_type
    if limit:
        params["limit"] = limit
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{AppConfig.AGENT_URL}/events/audit-log",
                params=params,
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
            logger.error(f"Error proxying audit log: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": f"Gateway error: {str(e)}"}
            )


@router.get("/events/stats")
async def get_event_bus_stats():
    """
    Proxy endpoint: Get Event Bus statistics.
    
    Proxies to: GET /events/stats on Agent Runtime
    
    Returns:
        Statistics about event publishing and handling
    """
    logger.debug("Proxying event bus stats request")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{AppConfig.AGENT_URL}/events/stats",
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
            logger.error(f"Error proxying event bus stats: {e}", exc_info=True)
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
                    elif msg_type == "plan_decision":
                        msg = WSPlanDecision.model_validate(ide_msg)
                        logger.info(f"[{session_id}] Received plan_decision: approval_request_id={msg.approval_request_id}, decision={msg.decision}")
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
                                        
                                        # Логируем plan_approval_required для отладки
                                        if msg_type == "plan_approval_required":
                                            logger.info(f"[{session_id}] plan_approval_required BEFORE filter: {json.dumps(data)}")
                                            logger.info(f"[{session_id}] plan_approval_required AFTER filter: {json.dumps(filtered_data)}")
                                        
                                        logger.debug(f"[{session_id}] Sending to IDE: {json.dumps(filtered_data, indent=2)}")
                                        
                                        # Пересылаем событие в IDE через WebSocket
                                        await websocket.send_json(filtered_data)
                                        
                                    except json.JSONDecodeError as e:
                                        logger.warning(f"[{session_id}] Failed to parse SSE data: {e}, line={line}")
                                else:
                                    # Для других типов событий (например error) тоже пытаемся парсить
                                    try:
                                        data = json.loads(data_str)
                                        msg_type = data.get('type')
                                        logger.debug(f"[{session_id}] Received SSE data for event '{current_event_type}': type={msg_type}")
                                        
                                        # Фильтруем null значения для всех событий
                                        filtered_data = {k: v for k, v in data.items() if v is not None}
                                        
                                        # Логируем plan_approval_required для отладки
                                        if msg_type == "plan_approval_required":
                                            logger.info(f"[{session_id}] plan_approval_required BEFORE filter: {json.dumps(data)}")
                                            logger.info(f"[{session_id}] plan_approval_required AFTER filter: {json.dumps(filtered_data)}")
                                        
                                        # Пересылаем событие в IDE
                                        await websocket.send_json(filtered_data)
                                        
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
                    # Для streaming response нужно прочитать содержимое перед доступом к .text
                    try:
                        error_body = await e.response.aread()
                        error_text = error_body.decode('utf-8')
                        logger.error(f"[{session_id}] Agent HTTP error: {e.response.status_code}, {error_text}")
                    except Exception as read_err:
                        logger.error(f"[{session_id}] Agent HTTP error: {e.response.status_code}, failed to read response: {read_err}")
                        error_text = "Unable to read error response"
                    
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
