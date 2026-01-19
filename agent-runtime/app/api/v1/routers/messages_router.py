"""
Messages роутер.

Предоставляет endpoints для работы с сообщениями.
Использует новый MessageOrchestrationService для обработки.
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional

from ..schemas.message_schemas import MessageStreamRequest
from ....models.schemas import StreamChunk
from ....agents.base_agent import AgentType

logger = logging.getLogger("agent-runtime.api.messages")

router = APIRouter(prefix="/agent/message", tags=["messages"])


@router.post("/stream")
async def message_stream_sse(request: MessageStreamRequest):
    """
    SSE streaming endpoint для обработки сообщений.
    
    Использует новый MessageOrchestrationService для обработки сообщений
    через систему мульти-агентов с поддержкой streaming ответов.
    
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
        StreamingResponse: SSE stream
        
    Пример запроса:
        POST /agent/message/stream
        {
            "session_id": "session-123",
            "message": {
                "type": "user_message",
                "content": "Создай новый файл",
                "agent_type": "coder"  // опционально
            }
        }
        
    Пример SSE ответа:
        data: {"type":"agent_switched","content":"Switched to coder agent",...}
        
        data: {"type":"assistant_message","token":"Конечно","is_final":false}
        
        data: {"type":"tool_call","call_id":"call-1","tool_name":"write_file",...}
        
        data: {"type":"done","is_final":true}
    """
    # Получить MessageOrchestrationService из глобального контекста
    from ....main import message_orchestration_service
    
    if not message_orchestration_service:
        # Fallback на старый orchestrator для обратной совместимости
        logger.warning(
            "MessageOrchestrationService not initialized, "
            "falling back to legacy MultiAgentOrchestrator"
        )
        from ....services.multi_agent_orchestrator import multi_agent_orchestrator
        
        async def legacy_generate():
            session_id = request.session_id
            message_data = request.message
            message_type = message_data.get("type")
            
            if message_type == "user_message":
                content = message_data.get("content", "")
                agent_type_str = message_data.get("agent_type")
                agent_type = AgentType(agent_type_str) if agent_type_str else None
                
                try:
                    async for chunk in multi_agent_orchestrator.process_message(
                        session_id=session_id,
                        message=content,
                        agent_type=agent_type
                    ):
                        yield f"data: {chunk.model_dump_json()}\n\n"
                except Exception as e:
                    logger.error(f"Error in legacy orchestrator: {e}", exc_info=True)
                    error_chunk = StreamChunk(
                        type="error",
                        error=str(e),
                        is_final=True
                    )
                    yield f"data: {error_chunk.model_dump_json()}\n\n"
            else:
                error_chunk = StreamChunk(
                    type="error",
                    error=f"Unsupported message type: {message_type}",
                    is_final=True
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            legacy_generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # Использовать новый MessageOrchestrationService
    session_id = request.session_id
    message_data = request.message
    message_type = message_data.get("type")
    
    if message_type == "user_message":
        content = message_data.get("content", "")
        agent_type_str = message_data.get("agent_type")
        agent_type = AgentType(agent_type_str) if agent_type_str else None
        
        logger.info(
            f"Processing user message for session {session_id} "
            f"(agent: {agent_type.value if agent_type else 'auto'}) "
            f"via MessageOrchestrationService"
        )
        
        async def generate():
            try:
                async for chunk in message_orchestration_service.process_message(
                    session_id=session_id,
                    message=content,
                    agent_type=agent_type
                ):
                    # Преобразовать в SSE формат
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                error_chunk = StreamChunk(
                    type="error",
                    error=str(e),
                    is_final=True
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    elif message_type == "tool_result":
        # Обработка результатов инструментов
        call_id = message_data.get("call_id")
        result = message_data.get("result")
        error = message_data.get("error")
        
        if not call_id:
            raise HTTPException(
                status_code=400,
                detail="call_id is required for tool_result message"
            )
        
        logger.info(
            f"Processing tool_result for session {session_id}: "
            f"call_id={call_id}, has_error={error is not None}"
        )
        
        async def tool_result_generate():
            try:
                async for chunk in message_orchestration_service.process_tool_result(
                    session_id=session_id,
                    call_id=call_id,
                    result=result,
                    error=error
                ):
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Error processing tool_result: {e}", exc_info=True)
                error_chunk = StreamChunk(
                    type="error",
                    error=str(e),
                    is_final=True
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            tool_result_generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    elif message_type == "switch_agent":
        # Обработка явного переключения агента
        agent_type_str = message_data.get("agent_type")
        reason = message_data.get("reason", "User requested agent switch")
        
        if not agent_type_str:
            raise HTTPException(
                status_code=400,
                detail="agent_type is required for switch_agent message"
            )
        
        try:
            agent_type = AgentType(agent_type_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent_type: {agent_type_str}"
            )
        
        logger.info(
            f"Processing agent switch for session {session_id} to {agent_type.value}"
        )
        
        async def switch_agent_generate():
            try:
                # Переключаем агента через MessageOrchestrationService
                async for chunk in message_orchestration_service.switch_agent(
                    session_id=session_id,
                    agent_type=agent_type,
                    reason=reason
                ):
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Error switching agent: {e}", exc_info=True)
                error_chunk = StreamChunk(
                    type="error",
                    error=str(e),
                    is_final=True
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            switch_agent_generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    elif message_type == "hitl_decision":
        # Обработка HITL решения пользователя
        call_id = message_data.get("call_id")
        decision = message_data.get("decision")
        
        if not call_id or not decision:
            raise HTTPException(
                status_code=400,
                detail="call_id and decision are required for hitl_decision message"
            )
        
        logger.info(
            f"Processing HITL decision for session {session_id}: "
            f"call_id={call_id}, decision={decision}"
        )
        
        async def hitl_decision_generate():
            try:
                # Обрабатываем HITL решение через MessageOrchestrationService
                async for chunk in message_orchestration_service.process_hitl_decision(
                    session_id=session_id,
                    call_id=call_id,
                    decision=decision
                ):
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Error processing HITL decision: {e}", exc_info=True)
                error_chunk = StreamChunk(
                    type="error",
                    error=str(e),
                    is_final=True
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            hitl_decision_generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported message type: {message_type}"
        )
