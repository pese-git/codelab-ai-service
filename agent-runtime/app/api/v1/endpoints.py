import json
import pprint
import traceback

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.core.config import AppConfig, logger
from app.models.schemas import AgentStreamRequest, HealthResponse, Message
from app.core.dependencies import get_chat_service
from app.services.chat_service import ChatService
from app.services.session_manager import session_manager
from app.services.llm_stream_service import stream_response
from app.core.agent.prompts import SYSTEM_PROMPT

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    logger.info("[Agent] Health check called")
    return HealthResponse.model_construct(
        status="healthy", service="agent-runtime", version=AppConfig.VERSION
    )


@router.post("/agent/message/stream")
async def message_stream_sse(request: AgentStreamRequest):
    """
    Новый SSE streaming endpoint для Agent Runtime.
    
    Принимает:
    - user_message: обычное сообщение пользователя
    - tool_result: результат выполнения инструмента от Gateway
    
    Возвращает:
    - SSE stream с чанками (assistant_message, tool_call, error)
    
    При получении tool_call от LLM - отправляет его в stream и завершает генерацию.
    Ожидает следующего запроса с tool_result для продолжения.
    """
    async def event_generator():
        try:
            logger.info(
                f"[Agent] SSE stream started for session: {request.session_id}"
            )
            logger.debug(
                f"[Agent][TRACE] Request message:\n"
                + pprint.pformat(request.message, indent=2, width=120)
            )
            
            # Получаем или создаем сессию
            session = session_manager.get_or_create(
                request.session_id, 
                system_prompt=SYSTEM_PROMPT
            )
            
            # Обрабатываем входящее сообщение
            message_type = request.message.get("type", "user_message")
            
            if message_type == "tool_result":
                # Это результат выполнения инструмента
                call_id = request.message.get("call_id")
                tool_name = request.message.get("tool_name")
                result = request.message.get("result")
                
                logger.info(
                    f"[Agent] Received tool_result from Gateway: "
                    f"call_id={call_id}, tool_name={tool_name}, session={request.session_id}"
                )
                logger.debug(
                    f"[Agent][TRACE] Tool result message:\n"
                    + pprint.pformat(request.message, indent=2, width=120)
                )
                
                # КРИТИЧНО: Проверяем наличие call_id
                if not call_id:
                    logger.error(
                        f"[Agent][ERROR] tool_result missing call_id! This will cause Azure OpenAI error. "
                        f"message={request.message}"
                    )
                    raise ValueError("tool_result must contain call_id")
                
                # Добавляем tool_result в историю как tool message
                result_str = json.dumps(result) if not isinstance(result, str) else result
                session_manager.append_tool_result(
                    request.session_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    result=result_str
                )
                
            else:
                # Это обычное user message
                content = request.message.get("content", "")
                logger.info(
                    f"[Agent] Received user_message: session={request.session_id}, "
                    f"content_len={len(content)}"
                )
                
                session_manager.append_message(
                    request.session_id,
                    role="user",
                    content=content
                )
            
            # Получаем историю для LLM
            history = session_manager.get_history(request.session_id)
            
            logger.debug(
                f"[Agent][TRACE] History for LLM ({len(history)} messages):\n"
                + pprint.pformat(history, indent=2, width=120)
            )
            
            # Генерируем ответ через LLM stream service
            async for chunk in stream_response(request.session_id, history):
                # Используем exclude_none=True чтобы не отправлять null поля
                chunk_dict = chunk.model_dump(exclude_none=True)
                chunk_json = json.dumps(chunk_dict)
                
                logger.debug(
                    f"[Agent] Sending chunk: type={chunk.type}, is_final={chunk.is_final}"
                )
                
                # Отправляем chunk как SSE event
                event_data = {
                    "event": "message",
                    "data": chunk_json
                }
                
                yield event_data
                
                # Если это финальный chunk - завершаем stream
                if chunk.is_final:
                    logger.info(
                        f"[Agent] Stream completed for session {request.session_id}: "
                        f"final_type={chunk.type}"
                    )
                    break
            
            # Отправляем done event
            yield {
                "event": "done",
                "data": json.dumps({"status": "completed"})
            }
            
        except Exception as e:
            logger.error(
                f"[Agent][ERROR] Exception in SSE stream for session {request.session_id}: {e}",
                exc_info=True
            )
            logger.error(
                "[Agent][ERROR] Traceback:\n" + traceback.format_exc()
            )
            
            # Отправляем error event
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "error": str(e),
                    "is_final": True
                })
            }
    
    return EventSourceResponse(event_generator())


# Старый endpoint для обратной совместимости
@router.post("/agent/message/stream/legacy")
async def message_stream_legacy(message: Message, chat_service: ChatService = Depends(get_chat_service)):
    """
    DEPRECATED: Старый endpoint для обратной совместимости.
    Используйте /agent/message/stream вместо этого.
    """
    try:
        logger.warning("[Agent] Using deprecated legacy endpoint")
        result = await chat_service.stream_message(message)
        return JSONResponse(content=result)
    except Exception:
        logger.error(f"[TRACE][ERROR] Exception in /agent/message/stream/legacy\n{traceback.format_exc()}")
        return JSONResponse(content={"error": "Internal server error"}, status_code=500)
