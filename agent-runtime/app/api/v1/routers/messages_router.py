"""
Messages роутер.

Предоставляет endpoints для работы с сообщениями.
Включает streaming endpoint для real-time коммуникации.
"""

import logging
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from ..schemas.message_schemas import MessageStreamRequest
from ....services.multi_agent_orchestrator import multi_agent_orchestrator

logger = logging.getLogger("agent-runtime.api.messages")

router = APIRouter(prefix="/agent/message", tags=["messages"])


@router.post("/stream")
async def message_stream_sse(request: MessageStreamRequest):
    """
    SSE streaming endpoint для обработки сообщений.
    
    Этот endpoint сохраняет существующий протокол общения
    между Gateway и Agent Runtime.
    
    Принимает:
    - user_message: Обычное сообщение пользователя
    - tool_result: Результат выполнения инструмента от Gateway
    - switch_agent: Явный запрос переключения агента
    - hitl_decision: Решение пользователя по HITL
    
    Возвращает:
    - SSE stream с chunks (assistant_message, tool_call, agent_switched, error)
    
    Args:
        request: Запрос с сообщением
        
    Returns:
        EventSourceResponse: SSE stream
        
    Пример запроса:
        POST /agent/message/stream
        {
            "session_id": "session-123",
            "message": {
                "type": "user_message",
                "content": "Создай новый файл"
            }
        }
        
    Пример SSE ответа:
        event: message
        data: {"type":"assistant_message","token":"Конечно","is_final":false}
        
        event: message
        data: {"type":"tool_call","call_id":"call-1","tool_name":"write_file",...}
        
        event: done
        data: {"status":"completed"}
    
    Примечание:
        Этот endpoint использует существующий MultiAgentOrchestrator
        для сохранения обратной совместимости с Gateway.
        В будущем можно мигрировать на использование Command/Query handlers.
    """
    # Используем существующий orchestrator для обратной совместимости
    # Это сохраняет протокол общения Gateway ↔ Agent Runtime
    
    # Импортируем существующую реализацию из старого endpoints.py
    from ...endpoints import message_stream_sse as legacy_stream
    
    # Делегируем обработку существующему endpoint
    return await legacy_stream(request)


# Примечание для будущей миграции:
# После полной интеграции можно будет заменить на:
#
# @router.post("/stream")
# async def message_stream_sse(
#     request: MessageStreamRequest,
#     add_message_handler: AddMessageHandler = Depends(...)
# ):
#     async def event_generator():
#         # Добавить сообщение через Command
#         command = AddMessageCommand(...)
#         await add_message_handler.handle(command)
#         
#         # Обработать через orchestrator
#         async for chunk in multi_agent_orchestrator.process_message(...):
#             yield {"event": "message", "data": chunk.json()}
#     
#     return EventSourceResponse(event_generator())
