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


#tools = [
#    {
#        "type": "function",
#        "name": "read_file",
#        "description": "Reads file contents.",
#        "parameters": {
#            "type": "object",
#            "properties": {
#                "path": {"type": "string", "description": "Path to file"}
#            },
#            "required": ["path"]
#        }
#    },
#    {
#        "type": "function",
#        "name": "echo",
#        "description": "Echo back text.",
#        "parameters": {
#            "type": "object",
#            "properties": {
#                "text": {"type": "string"}
#            },
#            "required": ["text"]
#        }
#    }
#]


tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read any file from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo back any string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Some string"}
                },
                "required": ["text"]
            }
        }
    }
]
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
                    "tool_call": json.loads(tool_call.model_dump_json())
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


async def llm_stream(session_id: str):
    """
    Send a non-streaming (stream=False) request to LLM Proxy and process tool calls/result.
    """
    session = sessions.get(session_id)
    if not session:
        logger.error(f"Session {session_id} not found")
        yield {
            "event": "error",
            "data": json.dumps({"error": "Session not found"})
        }
        return

    messages = session.messages
    llm_request = {
        "model": AppConfig.LLM_MODEL,
        "messages": messages,
        "stream": False,
        "tools": tools,
        #"function_call": "auto"
    }
    import pprint
    logger.info(
        f"[Agent] Sending request to LLM Proxy: session_id={session_id}, messages={len(messages)}"
    )
    logger.debug(f"[Agent][TRACE] Full llm_request payload:\n" + pprint.pformat(llm_request, indent=2, width=120))

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AppConfig.LLM_PROXY_URL}/v1/chat/completions",
            json=llm_request,
            headers={"X-Internal-Auth": AppConfig.INTERNAL_API_KEY},
            timeout=360.0,  # увеличили таймаут для долгих генераций
        )
        logger.info(f"[Agent] LLM proxy responded: {response.status_code}, body startswith: {response.text[:500]}")
        response.raise_for_status()
        data = response.json()
        result_message = data["choices"][0]["message"]
        content = result_message.get("content", "")
        metadata = {}
        if "tool_calls" in result_message:
            metadata["tool_calls"] = result_message["tool_calls"]
        if "function_call" in result_message:
            metadata["function_call"] = result_message["function_call"]

        # Парсим tool_calls если есть
        tool_calls, clean_content = parse_tool_calls(content, metadata)
        if tool_calls:
            for tool_call in tool_calls:
                yield {
                    "event": "tool_call",
                    "data": SSEToken.model_construct(
                        token="",
                        is_final=False,
                        type="tool_call",
                        metadata={"tool_call": tool_call.model_dump()}
                    ).model_dump_json()
                }
                await send_tool_call_to_gateway(session_id, tool_call)
                # TODO: добавить обработку результата и финализировать поток

        # Добавляем финальный ассистентский ответ, гарантируя, что content не None
        if clean_content is None:
            clean_content = ""
        elif not isinstance(clean_content, str):
            clean_content = str(clean_content)
        messages.append({"role": "assistant", "content": clean_content})
        logger.info(f"[Agent] Appended completion to session {session_id}")

        yield {
            "event": "message",
            "data": SSEToken.model_construct(
                token=clean_content,
                is_final=True,
                type="assistant_message"
            ).model_dump_json(),
        }
