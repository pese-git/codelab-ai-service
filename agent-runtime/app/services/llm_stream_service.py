"""
LLM streaming service for agent runtime.

Handles streaming responses from LLM, including tool calls and assistant messages.
Integrates with HITL (Human-in-the-Loop) for tool approval workflow.
"""
import json
import logging
import time
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from app.core.config import AppConfig
from app.models.schemas import StreamChunk
from app.services.llm_proxy_client import llm_proxy_client
from app.services.session_manager_async import AsyncSessionManager
from app.services.tool_parser import parse_tool_calls
from app.services.tool_registry import TOOLS_SPEC
from app.services.hitl_policy_service import hitl_policy_service
from app.services.hitl_manager import hitl_manager

# Event-Driven Architecture imports
from app.events.event_bus import event_bus
from app.events.tool_events import (
    ToolExecutionRequestedEvent,
    ToolApprovalRequiredEvent
)
from app.events.llm_events import (
    LLMRequestStartedEvent,
    LLMRequestCompletedEvent,
    LLMRequestFailedEvent
)

logger = logging.getLogger("agent-runtime.llm_stream")


async def stream_response(
    session_id: str,
    history: List[dict],
    allowed_tools: Optional[List[str]] = None,
    session_mgr: Optional[AsyncSessionManager] = None,
    correlation_id: Optional[str] = None
) -> AsyncGenerator[StreamChunk, None]:
    """
    Generate streaming response from LLM.
    
    When a tool_call is received, it's sent in the stream and generation stops.
    Tool execution happens on the IDE side via WebSocket.
    
    Args:
        session_id: Session identifier
        history: Message history for LLM
        allowed_tools: List of tool names allowed for this agent (None = all tools)
        session_mgr: Async session manager (optional, uses global if None)
        correlation_id: Correlation ID for event tracing (optional)
        
    Yields:
        StreamChunk: Chunks for SSE streaming (assistant_message, tool_call, or error)
    """
    # Get session manager from global if not provided
    if session_mgr is None:
        from app.services.session_manager_async import session_manager as global_mgr
        session_mgr = global_mgr
        if session_mgr is None:
            raise RuntimeError("SessionManager not initialized")
    
    try:
        logger.info(
            f"Starting LLM stream for session {session_id} with {len(history)} messages"
        )
        logger.debug(f"Last message: {history[-1] if history else 'none'}")

        # Filter tools based on allowed_tools
        tools_to_use = TOOLS_SPEC
        if allowed_tools is not None:
            tools_to_use = [
                tool for tool in TOOLS_SPEC
                if tool["function"]["name"] in allowed_tools
            ]
            logger.debug(
                f"Filtered tools: {len(tools_to_use)}/{len(TOOLS_SPEC)} "
                f"(allowed: {allowed_tools})"
            )

        # Prepare LLM request
        llm_request = {
            "model": AppConfig.LLM_MODEL,
            "messages": history,
            "stream": False,
            "tools": tools_to_use,
        }

        logger.debug(f"Calling LLM with model: {AppConfig.LLM_MODEL}, tools: {len(tools_to_use)}")

        # Publish LLM request started event
        start_time = time.time()
        logger.info(f"📊 Publishing LLM_REQUEST_STARTED event for session {session_id}")
        await event_bus.publish(
            LLMRequestStartedEvent(
                session_id=session_id,
                model=AppConfig.LLM_MODEL,
                messages_count=len(history),
                tools_count=len(tools_to_use),
                correlation_id=correlation_id
            )
        )
        logger.debug(f"✓ LLM_REQUEST_STARTED event published")

        # Call LLM proxy
        response_data = await llm_proxy_client.chat_completion(
            model=AppConfig.LLM_MODEL,
            messages=history,
            tools=tools_to_use,
            stream=False
        )
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.debug(f"LLM response received: {len(str(response_data))} chars")
        
        # Extract usage information (may be None for some providers)
        usage = response_data.get("usage") or {}
        logger.debug(f"Usage data: {usage}")
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        logger.debug(f"Tokens: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
        
        # Extract message from response
        result_message = response_data["choices"][0]["message"]
        content = result_message.get("content", "")
        metadata = {}

        # Extract tool_calls from content or metadata
        if isinstance(content, list):
            for obj in content:
                if isinstance(obj, dict) and "tool_calls" in obj and obj["tool_calls"]:
                    metadata["tool_calls"] = obj["tool_calls"]
                    break
        else:
            if "tool_calls" in result_message:
                metadata["tool_calls"] = result_message["tool_calls"]

        if "function_call" in result_message:
            metadata["function_call"] = result_message["function_call"]

        # Parse tool calls
        tool_calls, clean_content = parse_tool_calls(content, metadata)
        
        if tool_calls:
            logger.debug(f"Parsed {len(tool_calls)} tool calls")
        
        # Handle tool calls
        if tool_calls:
            # VALIDATION: Agent should call only ONE tool at a time
            if len(tool_calls) > 1:
                logger.warning(
                    f"LLM attempted to call {len(tool_calls)} tools simultaneously! "
                    f"Only the first tool will be executed. Tools: {[tc.tool_name for tc in tool_calls]}"
                )
            
            tool_call = tool_calls[0]

            logger.info(
                f"Tool call detected: {tool_call.tool_name} (call_id={tool_call.id})"
            )
            
            # Get current agent name from history
            current_agent = "unknown"
            for msg in reversed(history):
                if msg.get("role") == "assistant" and msg.get("name"):
                    current_agent = msg["name"]
                    break
            
            # Publish tool execution requested event
            await event_bus.publish(
                ToolExecutionRequestedEvent(
                    session_id=session_id,
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                    call_id=tool_call.id,
                    agent=current_agent,
                    correlation_id=correlation_id
                )
            )
            
            # Check if approval is required using HITL policy
            requires_approval, reason = hitl_policy_service.requires_approval(tool_call.tool_name)
            
            logger.info(
                f"Tool '{tool_call.tool_name}' requires_approval={requires_approval}"
                f"{f', reason={reason}' if reason else ''}"
            )
            
            # If approval required, save pending state
            if requires_approval:
                await hitl_manager.add_pending(
                    session_id=session_id,
                    call_id=tool_call.id,
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                    reason=reason
                )
                logger.info(f"Added HITL pending state for call_id={tool_call.id}")
                
                # Publish tool approval required event
                await event_bus.publish(
                    ToolApprovalRequiredEvent(
                        session_id=session_id,
                        tool_name=tool_call.tool_name,
                        arguments=tool_call.arguments,
                        call_id=tool_call.id,
                        reason=reason,
                        correlation_id=correlation_id
                    )
                )
            
            # Save assistant message with tool_call to history
            assistant_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.tool_name,
                        "arguments": json.dumps(tool_call.arguments)
                    }
                }]
            }
            
            logger.debug(
                f"Saving assistant message with tool_call: {tool_call.tool_name}"
            )
            
            # Append assistant message with tool_call to session
            # CRITICAL: Must persist IMMEDIATELY for tool_calls!
            # Tool result may arrive before background writer runs (5s delay)
            # Without immediate persistence, LLM won't find the tool_call in history
            
            # Check if session_mgr has the new method for tool_calls
            if hasattr(session_mgr, 'append_assistant_with_tool_calls'):
                # New architecture (adapter) - use dedicated method
                await session_mgr.append_assistant_with_tool_calls(
                    session_id=session_id,
                    tool_calls=assistant_msg["tool_calls"]
                )
                logger.debug(f"Assistant message with tool_call persisted via adapter")
            else:
                # Old AsyncSessionManager - use direct access to state
                session_state = session_mgr.get(session_id)
                if session_state:
                    session_state.messages.append(assistant_msg)
                    if hasattr(session_mgr, '_persist_immediately'):
                        await session_mgr._persist_immediately(session_id)
                        logger.debug(f"Assistant message with tool_call persisted immediately to DB")
                else:
                    logger.warning(
                        f"Session {session_id} not found - tool_call may not persist correctly"
                    )
            
            # Send tool_call chunk
            chunk = StreamChunk(
                type="tool_call",
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                requires_approval=requires_approval,
                is_final=True
            )
            
            # Publish LLM request completed event (with tool call) BEFORE yield
            logger.info(f"📊 Publishing LLM_REQUEST_COMPLETED event (with tool call) for session {session_id}")
            await event_bus.publish(
                LLMRequestCompletedEvent(
                    session_id=session_id,
                    model=AppConfig.LLM_MODEL,
                    duration_ms=duration_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    has_tool_calls=True,
                    correlation_id=correlation_id
                )
            )
            logger.debug(f"✓ LLM_REQUEST_COMPLETED event published")
            
            logger.debug(f"Yielding tool_call chunk: {tool_call.tool_name}")
            yield chunk
            
            # Stop generation - wait for tool_result from Gateway
            return

        # Handle regular assistant message
        if isinstance(content, list) and len(content) > 0:
            if isinstance(content[0], dict) and "content" in content[0]:
                clean_content = content[0]["content"]
            else:
                clean_content = str(content)
        elif not isinstance(clean_content, str):
            clean_content = str(clean_content) if clean_content else ""

        # Save assistant message to history
        # Note: append_message schedules persistence but doesn't need await
        await session_mgr.append_message(session_id, "assistant", clean_content)

        logger.info(f"Sending assistant message: {len(clean_content)} chars")

        # Send assistant message chunk
        chunk = StreamChunk(
            type="assistant_message",
            content=clean_content,
            token=clean_content,
            is_final=True
        )
        
        # Publish LLM request completed event (without tool call) BEFORE yield
        logger.info(f"📊 Publishing LLM_REQUEST_COMPLETED event (assistant message) for session {session_id}")
        await event_bus.publish(
            LLMRequestCompletedEvent(
                session_id=session_id,
                model=AppConfig.LLM_MODEL,
                duration_ms=duration_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                has_tool_calls=False,
                correlation_id=correlation_id
            )
        )
        logger.debug(f"✓ LLM_REQUEST_COMPLETED event published")
        
        logger.debug("Yielding assistant_message chunk")
        yield chunk

    except Exception as e:
        logger.error(
            f"Exception in stream_response for session {session_id}: {e}",
            exc_info=True
        )
        
        # Publish LLM request failed event
        await event_bus.publish(
            LLMRequestFailedEvent(
                session_id=session_id,
                model=AppConfig.LLM_MODEL,
                error=str(e),
                correlation_id=correlation_id
            )
        )
        
        # Send error chunk
        error_chunk = StreamChunk(
            type="error",
            error=str(e),
            is_final=True
        )
        yield error_chunk
