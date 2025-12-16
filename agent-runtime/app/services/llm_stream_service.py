import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Optional
import pprint
from app.core.config import AppConfig
from app.models.schemas import SSEToken, SessionState, ToolCall, WSToolCall
from app.services.tool_parser import parse_tool_calls
from app.services.llm_proxy_client import llm_proxy_client
from app.services.session_manager import session_manager
from app.services.tool_call_handler import tool_call_handler

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
# SessionManager теперь управляет всеми сессиями


# ToolCallHandler теперь инкапсулирует работу с инструментами


async def llm_stream(session_id: str):
    """
    Send a non-streaming (stream=False) request to LLM Proxy and process tool calls/result.
    """
    session = session_manager.get(session_id)
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

    logger.info(
        f"[Agent] Sending request to LLM Proxy: session_id={session_id}, messages={len(messages)}"
    )
    logger.debug(f"[Agent][TRACE] Full llm_request payload:\n" + pprint.pformat(llm_request, indent=2, width=120))

    data = await llm_proxy_client.chat_completion(
        model=AppConfig.LLM_MODEL,
        messages=messages,
        tools=tools,
        stream=False
    )
    logger.info(f"[Agent] LLM proxy responded: {str(data)[:256]}")
    result_message = data["choices"][0]["message"]
    content = result_message.get("content", "")
    metadata = {}
    
    # Новый блок: если content — список, искать tool_calls в каждом из dict
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

    # Парсим tool_calls если есть
    tool_calls, clean_content = parse_tool_calls(content, metadata)
    logger.debug(f"[Agent][TRACE] ToolCalls:\n" + pprint.pformat(tool_calls, indent=2, width=120))
    if tool_calls:
        # Поддерживаем только первый tool_call (как в OpenAI)
        tool_call = tool_calls[0]
        logger.debug(f"[Agent][TRACE] TOOL CALL:\n" + pprint.pformat(tool_call, indent=2, width=120))
        # 1. Выполняем tool через Gateway
        tool_result = await tool_call_handler.execute(session_id, tool_call)
        # 2. Добавляем result как function message в историю диалога (OpenAI pattern)
        function_message = {
            "role": "function",
            "name": tool_call.tool_name,
            "content": tool_result if isinstance(tool_result, str) else str(tool_result)
        }
        session_manager.get(session_id).messages.append(function_message)
        # 3. Делаем повторный запрос в LLM (уже с user + assistant(function_call)+ function result)
        new_messages = session_manager.get(session_id).messages
        data2 = await llm_proxy_client.chat_completion(
            model=AppConfig.LLM_MODEL,
            messages=new_messages,
            tools=tools,
            stream=False
        )
        logger.info(f"[Agent] Second LLM proxy call for final assistant reply: {str(data2)[:256]}")
        result_message2 = data2["choices"][0]["message"]
        final_content = result_message2.get("content", "")
        # Добавляем ассистентский финальный ответ в историю
        session_manager.append_message(session_id, "assistant", final_content)
        yield {
            "event": "message",
            "data": SSEToken.model_construct(
                token=final_content,
                is_final=True,
                type="assistant_message"
            ).model_dump_json(),
        }
        return

    # Если tool_calls нет -- обычный ассистентский ответ
    if clean_content is None:
        clean_content = ""
    elif not isinstance(clean_content, str):
        clean_content = str(clean_content)
    session_manager.append_message(session_id, "assistant", clean_content)
    logger.info(f"[Agent] Appended completion to session {session_id}")

    yield {
        "event": "message",
        "data": SSEToken.model_construct(
            token=clean_content,
            is_final=True,
            type="assistant_message"
        ).model_dump_json(),
    }
