import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Optional

import httpx

from app.core.config import AppConfig
from app.models.schemas import SSEToken, SessionState, ToolCall, ToolResult
from app.services.tool_manager import get_tool_tracker
from app.services.tool_parser import parse_tool_calls

logger = logging.getLogger("agent-runtime")

# In-memory session store (session_id -> SessionState)
sessions: Dict[str, SessionState] = {}


def get_sessions():
    return sessions


async def send_tool_call_to_gateway(session_id: str, tool_call: ToolCall) -> Optional[ToolResult]:
    """Send tool call to Gateway and wait for result"""
    tracker = get_tool_tracker()
    
    # Register the tool call
    await tracker.register_tool_call(tool_call, session_id)
    
    # Send to Gateway
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{AppConfig.GATEWAY_URL}/tool/execute",
                json={
                    "session_id": session_id,
                    "tool_call": tool_call.model_dump()
                },
                headers={"X-Internal-Auth": AppConfig.INTERNAL_API_KEY},
                timeout=30.0
            )
            
            if response.status_code == 200:
                await tracker.mark_executing(tool_call.id)
                
                # Wait for result (this would be improved with websocket or polling)
                # For now, we'll simulate waiting
                await asyncio.sleep(0.5)
                
                # In real implementation, Gateway would call back with result
                # For now, return None to continue flow
                return None
            else:
                logger.error(f"Failed to send tool call to Gateway: {response.status_code}")
                await tracker.fail_tool_call(tool_call.id, f"Gateway error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending tool call to Gateway: {e}")
            await tracker.fail_tool_call(tool_call.id, str(e))
    
    return None


async def llm_stream(session_id: str) -> AsyncGenerator[dict, None]:
    """Stream LLM responses, handling tool calls along the way"""
    
    # Get session - it should already exist from endpoints
    session = sessions.get(session_id)
    if not session:
        logger.error(f"Session {session_id} not found")
        yield {
            "event": "error",
            "data": json.dumps({"error": "Session not found"})
        }
        return
    
    messages = session.messages
    
    llm_request = {"model": AppConfig.LLM_MODEL, "messages": messages, "stream": True}
    logger.info(
        f"[Agent] Sending request to LLM Proxy: session_id={session_id}, messages={len(messages)}"
    )

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{AppConfig.LLM_PROXY_URL}/v1/chat/completions",
            json=llm_request,
            headers={
                "Accept": "text/event-stream",
                "X-Internal-Auth": AppConfig.INTERNAL_API_KEY,
            },
        ) as resp:
            resp.raise_for_status()
            logger.info(f"[Agent] Connected to LLM Proxy, status_code={resp.status_code}")
            current_completion = ""
            accumulated_metadata = {}
            
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or line.startswith("event:"):
                    continue
                
                if line == "[DONE]":
                    # Check for tool calls in the final content
                    tool_calls, clean_content = parse_tool_calls(
                        current_completion, accumulated_metadata
                    )
                    
                    if tool_calls:
                        # Pause streaming to execute tool calls
                        logger.info(f"[Agent] Found {len(tool_calls)} tool calls in response")
                        
                        for tool_call in tool_calls:
                            # Send tool call event
                            yield {
                                "event": "tool_call",
                                "data": SSEToken.model_construct(
                                    token="",
                                    is_final=False,
                                    type="tool_call",
                                    metadata={"tool_call": tool_call.model_dump()}
                                ).model_dump_json()
                            }
                            
                            # Execute tool call
                            await send_tool_call_to_gateway(session_id, tool_call)
                            
                            # TODO: Handle tool result when Gateway integration is complete
                    
                    # Append clean content to messages
                    messages.append({"role": "assistant", "content": clean_content})
                    logger.info(f"[Agent] Appended final completion to session {session_id}")
                    
                    # Send final token
                    yield {
                        "event": "message",
                        "data": SSEToken.model_construct(
                            token="", 
                            is_final=True,
                            type="assistant_message"
                        ).model_dump_json(),
                    }
                    break
                
                if line.startswith("data:"):
                    json_str = line[5:].strip()
                    if not json_str.startswith("{"):
                        continue
                    
                    try:
                        chunk = json.loads(json_str)
                        choices = chunk.get("choices", [{}])
                        delta = choices[0].get("delta", {})
                        
                        # Extract content and metadata
                        token = delta.get("content", "")
                        if token:
                            current_completion += token
                        
                        # Accumulate metadata for tool call detection
                        if delta.get("tool_calls"):
                            if "tool_calls" not in accumulated_metadata:
                                accumulated_metadata["tool_calls"] = []
                            accumulated_metadata["tool_calls"].extend(delta["tool_calls"])
                        
                        if delta.get("function_call"):
                            accumulated_metadata["function_call"] = delta["function_call"]
                        
                        finish = choices[0].get("finish_reason")
                        
                        # Check for tool calls in streaming content
                        if token:
                            # Quick check if content might contain tool calls
                            if any(marker in token for marker in ['<', '(', 'tool:', 'function:']):
                                tool_calls, _ = parse_tool_calls(token)
                                if tool_calls:
                                    logger.debug(f"Found potential tool call in token: {token}")
                        
                        # Send token to client
                        sse_token = SSEToken.model_construct(
                            token=token,
                            is_final=finish == "stop",
                            type="assistant_message"
                        )
                        
                        if finish == "stop":
                            # Final processing will happen at [DONE]
                            pass
                        
                        yield {"event": "message", "data": sse_token.model_dump_json()}
                        
                    except Exception as e:
                        logger.error(f"[Agent] Failed to parse chunk JSON: {json_str} ({e})")
                        continue
