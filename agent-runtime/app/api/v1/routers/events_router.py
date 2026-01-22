"""
Events и Metrics роутер.

Предоставляет endpoints для получения метрик и событий.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger("agent-runtime.api.events")

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/metrics")
async def get_event_metrics():
    """
    Get metrics collected from events.
    
    Returns metrics automatically collected by MetricsCollector:
    - Agent switches
    - Agent processing durations
    - Tool executions
    - HITL decisions
    - Errors
    
    Returns:
        Dictionary with all collected metrics
    """
    logger.debug("Getting event metrics")
    
    from ....events.subscribers import metrics_collector
    
    metrics = metrics_collector.get_metrics()
    
    # Add computed metrics
    computed = {}
    
    # Average durations for each agent
    for agent in metrics.get("agent_processing", {}).keys():
        avg = metrics_collector.get_agent_avg_duration(agent)
        computed[f"{agent}_avg_duration_ms"] = round(avg, 2)
    
    # Success rates for tools
    for tool in metrics.get("tool_executions", {}).keys():
        rate = metrics_collector.get_tool_success_rate(tool)
        computed[f"{tool}_success_rate"] = round(rate, 3)
    
    return {
        "metrics": metrics,
        "computed": computed,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/audit-log")
async def get_audit_log(
    session_id: str = None,
    event_type: str = None,
    limit: int = 100
):
    """
    Get audit log of critical events.
    
    Args:
        session_id: Filter by session ID (optional)
        event_type: Filter by event type (optional)
        limit: Maximum number of entries (default: 100)
    
    Returns:
        List of audit log entries with filtering
    """
    logger.debug(f"Getting audit log: session_id={session_id}, event_type={event_type}, limit={limit}")
    
    from ....events.subscribers import audit_logger
    
    log = audit_logger.get_audit_log(
        session_id=session_id,
        event_type=event_type,
        limit=limit
    )
    
    return {
        "audit_log": log,
        "count": len(log),
        "filters": {
            "session_id": session_id,
            "event_type": event_type,
            "limit": limit
        }
    }


@router.get("/stats")
async def get_event_bus_stats():
    """
    Get Event Bus statistics.
    
    Returns:
        Statistics about event publishing and handling
    """
    logger.debug("Getting event bus stats")
    
    from ....events.event_bus import event_bus
    
    stats = event_bus.get_stats()
    
    return {
        "total_published": stats.total_published,
        "successful_handlers": stats.successful_handlers,
        "failed_handlers": stats.failed_handlers,
        "last_event_time": stats.last_event_time.isoformat() if stats.last_event_time else None,
        "success_rate": round(
            stats.successful_handlers / max(stats.successful_handlers + stats.failed_handlers, 1),
            3
        )
    }


@router.get("/metrics/session/{session_id}")
async def get_session_metrics(session_id: str):
    """
    Get LLM metrics for a specific session.
    
    Returns detailed metrics about LLM requests for the session:
    - Total requests (successful and failed)
    - Token usage (prompt, completion, total)
    - Average duration
    - Requests with tool calls
    - Individual request details
    
    Args:
        session_id: Session identifier
    
    Returns:
        Session metrics with aggregated stats and request history
    """
    logger.debug(f"Getting session metrics for {session_id}")
    
    from ....events.subscribers import session_metrics_collector
    
    # Debug: проверим все доступные сессии
    all_sessions = session_metrics_collector.get_all_sessions()
    logger.debug(f"Available sessions with metrics: {all_sessions}")
    logger.debug(f"Total sessions with metrics: {len(all_sessions)}")
    
    metrics = session_metrics_collector.get_session_metrics(session_id)
    
    if not metrics:
        logger.warning(
            f"No metrics found for session {session_id}. "
            f"Available sessions: {all_sessions}"
        )
        return JSONResponse(
            content={"error": f"No metrics found for session {session_id}"},
            status_code=404
        )
    
    return metrics.to_dict()


@router.get("/metrics/sessions")
async def get_all_session_metrics():
    """
    Get list of all sessions with LLM metrics.
    
    Returns:
        List of session IDs that have metrics data
    """
    logger.debug("Getting all sessions with metrics")
    
    from ....events.subscribers import session_metrics_collector
    
    sessions = session_metrics_collector.get_all_sessions()
    
    return {
        "sessions": sessions,
        "count": len(sessions)
    }
