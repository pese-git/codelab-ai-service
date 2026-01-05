"""
LLM streaming service for agent runtime.

Handles streaming responses from LLM, including tool calls and assistant messages.
Integrates with HITL (Human-in-the-Loop) for tool approval workflow.
"""
import json
import logging
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from app.core.config import AppConfig
from app.models.schemas import StreamChunk
from app.services.llm_proxy_client import llm_proxy_client
from app.services.session_manager import session_manager
from app.services.tool_parser import parse_tool_calls
from app.services.tool_registry import TOOLS_SPEC
from app.services.hitl_policy_service import hitl_policy_service
from app.services.hitl_manager import hitl_manager

logger = logging.getLogger("agent-runtime.llm_stream")


async def stream_response(
    session_id: str,
    history: List[dict],
    allowed_tools: Optional[List[str]] = None
) -> AsyncGenerator[StreamChunk, None]:
    """
    Generate streaming response from LLM.
    
    When a tool_call is received, it's sent in the stream and generation stops.
    Tool execution happens on the IDE side via WebSocket.
    
    Args:
        session_id: Session identifier
        history: Message history for LLM
        allowed_tools: List of tool names allowed for this agent (None = all tools)
        
    Yields:
        StreamChunk: Chunks for SSE streaming (assistant_message, tool_call, or error)
    """
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

        # Call LLM proxy
        response_data = await llm_proxy_client.chat_completion(
            model=AppConfig.LLM_MODEL,
            messages=history,
            tools=tools_to_use,
            stream=False
        )
        
        logger.debug(f"LLM response received: {len(str(response_data))} chars")
        
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
            
            # Check if approval is required using HITL policy
            requires_approval, reason = hitl_policy_service.requires_approval(tool_call.tool_name)
            
            logger.info(
                f"Tool '{tool_call.tool_name}' requires_approval={requires_approval}"
                f"{f', reason={reason}' if reason else ''}"
            )
            
            # If approval required, save pending state
            if requires_approval:
                hitl_manager.add_pending(
                    session_id=session_id,
                    call_id=tool_call.id,
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                    reason=reason
                )
                logger.info(f"Added HITL pending state for call_id={tool_call.id}")
            
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
            
            session_manager.get(session_id).messages.append(assistant_msg)
            
            # Send tool_call chunk
            chunk = StreamChunk(
                type="tool_call",
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                requires_approval=requires_approval,
                is_final=True
            )
            
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
        session_manager.append_message(session_id, "assistant", clean_content)

        logger.info(f"Sending assistant message: {len(clean_content)} chars")

        # Send assistant message chunk
        chunk = StreamChunk(
            type="assistant_message",
            content=clean_content,
            token=clean_content,
            is_final=True
        )
        
        logger.debug("Yielding assistant_message chunk")
        yield chunk

    except Exception as e:
        logger.error(
            f"Exception in stream_response for session {session_id}: {e}",
            exc_info=True
        )
        
        # Send error chunk
        error_chunk = StreamChunk(
            type="error",
            error=str(e),
            is_final=True
        )
        yield error_chunk
