"""
API v1 endpoints for agent runtime service.
"""
import json
import logging
import traceback

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.core.config import AppConfig
from app.core.dependencies import get_chat_service
from app.core.agent.prompts import SYSTEM_PROMPT
from app.models.schemas import AgentStreamRequest, HealthResponse, Message, AgentInfo
from app.services.chat_service import ChatService
from app.services.session_manager import session_manager
from app.services.llm_stream_service import stream_response
from app.services.multi_agent_orchestrator import multi_agent_orchestrator
from app.services.agent_router import agent_router
from app.agents.base_agent import AgentType

logger = logging.getLogger("agent-runtime.api")
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    logger.debug("Health check called")
    return HealthResponse.model_construct(
        status="healthy", 
        service="agent-runtime", 
        version=AppConfig.VERSION
    )


@router.post("/agent/message/stream")
async def message_stream_sse(request: AgentStreamRequest):
    """
    SSE streaming endpoint for Agent Runtime with multi-agent support.
    
    Accepts:
    - user_message: Regular user message
    - tool_result: Tool execution result from Gateway
    - switch_agent: Explicit agent switch request
    
    Returns:
    - SSE stream with chunks (assistant_message, tool_call, agent_switched, error)
    
    Multi-agent flow:
    1. User message → Orchestrator analyzes → Routes to specialist
    2. Specialist processes → May call tools or switch agents
    3. Tool results continue with current agent
    """
    async def event_generator():
        try:
            logger.info(f"SSE stream started for session: {request.session_id}")
            logger.debug(f"Message type: {request.message.get('type', 'user_message')}")
            
            # Get or create session (system prompt will be set by agent)
            session = session_manager.get_or_create(
                request.session_id,
                system_prompt=""  # Agent will set its own prompt
            )
            
            # Process incoming message
            message_type = request.message.get("type", "user_message")
            
            if message_type == "tool_result":
                # Tool execution result from Gateway
                call_id = request.message.get("call_id")
                tool_name = request.message.get("tool_name")
                result = request.message.get("result")
                
                logger.info(
                    f"Received tool_result: call_id={call_id}, "
                    f"tool={tool_name}, session={request.session_id}"
                )
                
                # CRITICAL: Validate call_id presence
                if not call_id:
                    error_msg = "tool_result must contain call_id"
                    logger.error(f"Missing call_id in tool_result: {request.message}")
                    raise ValueError(error_msg)
                
                # Add tool_result to history as tool message
                result_str = json.dumps(result) if not isinstance(result, str) else result
                session_manager.append_tool_result(
                    request.session_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    result=result_str
                )
                
                # Continue with current agent (empty message)
                async for chunk in multi_agent_orchestrator.process_message(
                    session_id=request.session_id,
                    message=""  # Empty message, continue after tool_result
                ):
                    chunk_dict = chunk.model_dump(exclude_none=True)
                    chunk_json = json.dumps(chunk_dict)
                    
                    yield {
                        "event": "message",
                        "data": chunk_json
                    }
                    
                    if chunk.is_final:
                        break
                
            elif message_type == "switch_agent":
                # Explicit agent switch request
                agent_type_str = request.message.get("agent_type")
                content = request.message.get("content", "")
                
                try:
                    target_agent = AgentType(agent_type_str)
                except ValueError:
                    error_msg = f"Invalid agent type: {agent_type_str}"
                    logger.error(error_msg)
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "type": "error",
                            "error": error_msg,
                            "is_final": True
                        })
                    }
                    return
                
                logger.info(
                    f"Explicit agent switch requested: {target_agent.value} "
                    f"for session {request.session_id}"
                )
                
                # Add user message to history
                if content:
                    session_manager.append_message(
                        request.session_id,
                        role="user",
                        content=content
                    )
                
                # Process with specified agent
                async for chunk in multi_agent_orchestrator.process_message(
                    session_id=request.session_id,
                    message=content,
                    agent_type=target_agent
                ):
                    chunk_dict = chunk.model_dump(exclude_none=True)
                    chunk_json = json.dumps(chunk_dict)
                    
                    yield {
                        "event": "message",
                        "data": chunk_json
                    }
                    
                    if chunk.is_final:
                        break
                
            else:
                # Regular user message
                content = request.message.get("content", "")
                logger.info(
                    f"Received user_message: session={request.session_id}, "
                    f"length={len(content)}"
                )
                
                session_manager.append_message(
                    request.session_id,
                    role="user",
                    content=content
                )
                
                # Process through multi-agent system
                async for chunk in multi_agent_orchestrator.process_message(
                    session_id=request.session_id,
                    message=content
                ):
                    chunk_dict = chunk.model_dump(exclude_none=True)
                    chunk_json = json.dumps(chunk_dict)
                    
                    logger.debug(
                        f"Sending chunk: type={chunk.type}, is_final={chunk.is_final}"
                    )
                    
                    yield {
                        "event": "message",
                        "data": chunk_json
                    }
                    
                    if chunk.is_final:
                        logger.info(
                            f"Stream completed for session {request.session_id}: "
                            f"final_type={chunk.type}"
                        )
                        break
            
            # Send done event
            yield {
                "event": "done",
                "data": json.dumps({"status": "completed"})
            }
            
        except Exception as e:
            logger.error(
                f"Exception in SSE stream for session {request.session_id}: {e}",
                exc_info=True
            )
            
            # Send error event
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "error": str(e),
                    "is_final": True
                })
            }
    
    return EventSourceResponse(event_generator())


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents():
    """
    Get information about all registered agents.
    
    Returns:
        List of agent information including capabilities and restrictions
    """
    logger.debug("Listing all registered agents")
    
    agents_info = []
    for agent_type in agent_router.list_agents():
        agent = agent_router.get_agent(agent_type)
        agents_info.append(AgentInfo(
            type=agent.agent_type.value,
            name=f"{agent.agent_type.value.capitalize()} Agent",
            description=agent.system_prompt.split('\n')[0],  # First line of prompt
            allowed_tools=agent.get_allowed_tools(),
            has_file_restrictions=bool(agent.file_restrictions)
        ))
    
    logger.info(f"Returning info for {len(agents_info)} agents")
    return agents_info


@router.get("/agents/{session_id}/current")
async def get_current_agent(session_id: str):
    """
    Get current active agent for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Current agent information and switch history
    """
    logger.debug(f"Getting current agent for session {session_id}")
    
    current_agent = multi_agent_orchestrator.get_current_agent(session_id)
    agent_history = multi_agent_orchestrator.get_agent_history(session_id)
    
    if not current_agent:
        return JSONResponse(
            content={"error": "Session not found"},
            status_code=404
        )
    
    return {
        "session_id": session_id,
        "current_agent": current_agent.value,
        "agent_history": agent_history,
        "switch_count": len(agent_history)
    }


@router.post("/agent/message/stream/legacy")
async def message_stream_legacy(
    message: Message,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    DEPRECATED: Legacy endpoint for backward compatibility.
    Use /agent/message/stream instead.
    """
    try:
        logger.warning("Using deprecated legacy endpoint")
        result = await chat_service.stream_message(message)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Exception in legacy endpoint: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "Internal server error"},
            status_code=500
        )
