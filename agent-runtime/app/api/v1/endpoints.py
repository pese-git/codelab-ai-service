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
from app.models.schemas import AgentStreamRequest, HealthResponse, Message
from app.services.chat_service import ChatService
from app.services.session_manager import session_manager
from app.services.llm_stream_service import stream_response

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
    SSE streaming endpoint for Agent Runtime.
    
    Accepts:
    - user_message: Regular user message
    - tool_result: Tool execution result from Gateway
    
    Returns:
    - SSE stream with chunks (assistant_message, tool_call, error)
    
    When tool_call is received from LLM, it's sent in stream and generation stops.
    Expects next request with tool_result to continue.
    """
    async def event_generator():
        try:
            logger.info(f"SSE stream started for session: {request.session_id}")
            logger.debug(f"Message type: {request.message.get('type', 'user_message')}")
            
            # Get or create session
            session = session_manager.get_or_create(
                request.session_id, 
                system_prompt=SYSTEM_PROMPT
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
            
            # Get history for LLM
            history = session_manager.get_history(request.session_id)
            
            logger.debug(f"Processing with {len(history)} messages in history")
            
            # Generate response through LLM stream service
            async for chunk in stream_response(request.session_id, history):
                # Use exclude_none=True to avoid sending null fields
                chunk_dict = chunk.model_dump(exclude_none=True)
                chunk_json = json.dumps(chunk_dict)
                
                logger.debug(
                    f"Sending chunk: type={chunk.type}, is_final={chunk.is_final}"
                )
                
                # Send chunk as SSE event
                event_data = {
                    "event": "message",
                    "data": chunk_json
                }
                
                yield event_data
                
                # If this is final chunk - stop stream
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
