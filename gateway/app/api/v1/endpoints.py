from fastapi import APIRouter, WebSocket, Depends
from fastapi.responses import JSONResponse

from app.core.config import config, logger
from app.models.rest import HealthResponse
from app.core.dependencies import (
    get_session_manager,
    get_token_buffer_manager,
    get_agent_runtime_proxy,
    get_websocket_handler,
)
from app.services.session_manager import SessionManager
from app.services.token_buffer_manager import TokenBufferManager
from app.services.agent_runtime_proxy import AgentRuntimeProxy
from app.services.websocket import WebSocketHandler

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse.model_construct(
        status="healthy", service="gateway", version=config.version
    )


# ==================== Agent Runtime Proxy Endpoints ====================

@router.get("/agents")
async def list_agents(proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)):
    """
    Proxy endpoint: Get list of all registered agents from Agent Runtime.
    
    Proxies to: GET /agents on Agent Runtime
    """
    return await proxy.get("/agents")


@router.get("/agents/{session_id}/current")
async def get_current_agent(
    session_id: str,
    proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)
):
    """
    Proxy endpoint: Get current active agent for a session.
    
    Proxies to: GET /agents/{session_id}/current on Agent Runtime
    """
    return await proxy.get(f"/agents/{session_id}/current")


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)
):
    """
    Proxy endpoint: Get message history for a session.
    
    Proxies to: GET /sessions/{session_id}/history on Agent Runtime
    """
    return await proxy.get(f"/sessions/{session_id}/history")


@router.get("/sessions")
async def list_sessions(proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)):
    """
    Proxy endpoint: List all active sessions.
    
    Proxies to: GET /sessions on Agent Runtime
    """
    return await proxy.get("/sessions")


@router.post("/sessions")
async def create_session(proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)):
    """
    Proxy endpoint: Create a new session.
    
    Proxies to: POST /sessions on Agent Runtime
    
    Returns:
        Session information with session_id
    """
    return await proxy.post("/sessions")


@router.get("/sessions/{session_id}/pending-approvals")
async def get_pending_approvals(
    session_id: str,
    proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)
):
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
    return await proxy.get(f"/sessions/{session_id}/pending-approvals")


@router.get("/events/metrics/session/{session_id}")
async def get_session_metrics(
    session_id: str,
    proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)
):
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
    return await proxy.get(f"/events/metrics/session/{session_id}")


@router.get("/events/metrics/sessions")
async def get_all_session_metrics(
    proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)
):
    """
    Proxy endpoint: Get list of all sessions with LLM metrics.
    
    Proxies to: GET /events/metrics/sessions on Agent Runtime
    
    Returns:
        List of session IDs that have metrics data
    """
    logger.debug("Proxying all session metrics request")
    return await proxy.get("/events/metrics/sessions")


@router.get("/events/metrics")
async def get_event_metrics(
    proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)
):
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
    return await proxy.get("/events/metrics")


@router.get("/events/audit-log")
async def get_audit_log(
    session_id: str = None,
    event_type: str = None,
    limit: int = 100,
    proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)
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
    
    return await proxy.get("/events/audit-log", params=params)


@router.get("/events/stats")
async def get_event_bus_stats(
    proxy: AgentRuntimeProxy = Depends(get_agent_runtime_proxy)
):
    """
    Proxy endpoint: Get Event Bus statistics.
    
    Proxies to: GET /events/stats on Agent Runtime
    
    Returns:
        Statistics about event publishing and handling
    """
    logger.debug("Proxying event bus stats request")
    return await proxy.get("/events/stats")


# ==================== WebSocket Endpoint ====================

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
    token_buffer_manager: TokenBufferManager = Depends(get_token_buffer_manager),
    ws_handler: WebSocketHandler = Depends(get_websocket_handler),
):
    """
    WebSocket endpoint для двунаправленной связи между IDE и Agent через HTTP streaming.
    
    Flow:
    1. IDE отправляет user_message или tool_result через WebSocket
    2. Gateway пересылает в Agent через HTTP streaming (SSE)
    3. Agent отправляет SSE события (assistant_message, tool_call)
    4. Gateway пересылает SSE события в IDE через WebSocket
    """
    # Регистрируем сессию
    await session_manager.add(session_id, websocket)
    
    try:
        # Делегируем обработку WebSocketHandler
        await ws_handler.handle_connection(websocket, session_id)
    finally:
        # Очищаем ресурсы при завершении соединения
        await token_buffer_manager.remove(session_id)
        await session_manager.remove(session_id)
