import json
import logging
import pprint

from app.core.config import AppConfig
from app.models.schemas import StreamChunk
from app.services.llm_proxy_client import llm_proxy_client
from app.services.session_manager import session_manager
from app.services.tool_parser import parse_tool_calls

logger = logging.getLogger("agent-runtime")


tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read any file from disk.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo back any string.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Some string"}},
                "required": ["text"],
            },
        },
    },
]


async def stream_response(session_id: str, history: list):
    """
    Генерирует streaming ответ от LLM.
    При получении tool_call - отправляет его в stream и ЗАВЕРШАЕТ генерацию.
    Не пытается выполнять tool локально.
    
    Args:
        session_id: ID сессии
        history: История сообщений для LLM
        
    Yields:
        StreamChunk: Чанки для SSE streaming
    """
    try:
        logger.info(
            f"[Agent] Starting stream_response: session_id={session_id}, messages={len(history)}"
        )
        logger.debug(
            "[Agent][TRACE] Full history:\n"
            + pprint.pformat(history, indent=2, width=120)
        )

        llm_request = {
            "model": AppConfig.LLM_MODEL,
            "messages": history,
            "stream": False,
            "tools": tools,
        }

        logger.debug(
            "[Agent][TRACE] Full llm_request payload:\n"
            + pprint.pformat(llm_request, indent=2, width=120)
        )

        # Запрос к LLM
        data = await llm_proxy_client.chat_completion(
            model=AppConfig.LLM_MODEL, messages=history, tools=tools, stream=False
        )
        
        logger.info(
            "[Agent][TRACE] LLM proxy responded:\n" + pprint.pformat(data, indent=2, width=120)
        )
        
        result_message = data["choices"][0]["message"]
        content = result_message.get("content", "")
        metadata = {}

        # Проверяем наличие tool_calls
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
        
        logger.debug(
            "[Agent][TRACE] Parsed tool_calls:\n" + pprint.pformat(tool_calls, indent=2, width=120)
        )

        if tool_calls:
            # ВАЖНО: При tool_call отправляем его в stream и ЗАВЕРШАЕМ генерацию
            # Не пытаемся выполнять tool локально
            tool_call = tool_calls[0]  # Берем первый tool_call
            
            logger.info(
                f"[Agent] Tool call detected: {tool_call.tool_name}, завершаем stream"
            )
            
            # Добавляем assistant message с tool_call в историю
            # tool_call.arguments уже dict, не нужно вызывать model_dump()
            arguments_dict = tool_call.arguments if isinstance(tool_call.arguments, dict) else tool_call.arguments.model_dump()
            
            assistant_msg = {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.tool_name,
                        "arguments": json.dumps(arguments_dict)
                    }
                }]
            }
            session_manager.get(session_id).messages.append(assistant_msg)
            
            # Отправляем tool_call в stream
            chunk = StreamChunk(
                type="tool_call",
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=arguments_dict,
                is_final=True
            )
            
            logger.debug(
                "[Agent][TRACE] Yielding tool_call chunk:\n"
                + pprint.pformat(chunk.model_dump(), indent=2, width=120)
            )
            
            yield chunk
            
            # Завершаем генерацию - ждем tool_result от Gateway
            return

        # Если tool_calls нет - обычный ассистентский ответ
        if isinstance(content, list) and len(content) > 0:
            if isinstance(content[0], dict) and "content" in content[0]:
                clean_content = content[0]["content"]
            else:
                clean_content = str(content)
        elif not isinstance(clean_content, str):
            clean_content = str(clean_content) if clean_content else ""

        # Добавляем ответ в историю
        session_manager.append_message(session_id, "assistant", clean_content)

        logger.info(
            f"[Agent] Sending assistant message: {len(clean_content)} chars"
        )

        # Отправляем assistant message
        chunk = StreamChunk(
            type="assistant_message",
            content=clean_content,
            token=clean_content,
            is_final=True
        )
        
        logger.debug(
            "[Agent][TRACE] Yielding assistant_message chunk:\n"
            + pprint.pformat(chunk.model_dump(), indent=2, width=120)
        )
        
        yield chunk

    except Exception as e:
        logger.error(
            f"[Agent][ERROR] Exception in stream_response for session {session_id}: {e}",
            exc_info=True
        )
        logger.error(
            "[Agent][ERROR] Locals at exception:\n"
            + pprint.pformat(locals(), indent=2, width=120)
        )
        
        # Отправляем ошибку в stream
        error_chunk = StreamChunk(
            type="error",
            error=str(e),
            is_final=True
        )
        yield error_chunk


# Оставляем старую функцию для обратной совместимости, но помечаем как deprecated
async def llm_stream(session_id: str):
    """
    DEPRECATED: Используйте stream_response вместо этой функции.
    Оставлено для обратной совместимости.
    """
    logger.warning("[Agent] llm_stream is deprecated, use stream_response instead")
    
    session = session_manager.get(session_id)
    if not session:
        logger.error(f"Session {session_id} not found")
        yield {"event": "error", "data": json.dumps({"error": "Session not found"})}
        return

    history = session_manager.get_history(session_id)
    
    async for chunk in stream_response(session_id, history):
        yield {
            "event": "message",
            "data": chunk.model_dump_json()
        }
