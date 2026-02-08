"""
Messages роутер.

Предоставляет endpoints для работы с сообщениями.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.message_schemas import MessageStreamRequest
from ....models.schemas import StreamChunk
from ....agents.base_agent import AgentType
from ....core.di import get_container
from ....services.database import get_db
from ....application.use_cases import (
    ProcessMessageUseCase,
    SwitchAgentUseCase,
    ProcessToolResultUseCase,
    HandleApprovalUseCase
)
from ....application.use_cases.process_message_use_case import ProcessMessageRequest
from ....application.use_cases.switch_agent_use_case import SwitchAgentRequest
from ....application.use_cases.process_tool_result_use_case import ProcessToolResultRequest
from ....application.use_cases.handle_approval_use_case import HandleApprovalRequest

logger = logging.getLogger("agent-runtime.api.messages")

router = APIRouter(prefix="/agent/message", tags=["messages"])


# ==================== Dependency Functions ====================

async def get_process_message_use_case(
    db: AsyncSession = Depends(get_db)
) -> ProcessMessageUseCase:
    """Получить Use Case для обработки сообщений."""
    return get_container().get_process_message_use_case(db)


async def get_switch_agent_use_case(
    db: AsyncSession = Depends(get_db)
) -> SwitchAgentUseCase:
    """Получить Use Case для переключения агента."""
    return get_container().get_switch_agent_use_case(db)


async def get_process_tool_result_use_case(
    db: AsyncSession = Depends(get_db)
) -> ProcessToolResultUseCase:
    """Получить Use Case для обработки результатов инструментов."""
    return get_container().get_process_tool_result_use_case(db)


async def get_handle_approval_use_case(
    db: AsyncSession = Depends(get_db)
) -> HandleApprovalUseCase:
    """Получить Use Case для обработки approval решений."""
    return get_container().get_handle_approval_use_case(db)


# ==================== Endpoints ====================


@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    process_message_use_case=Depends(get_process_message_use_case),
    switch_agent_use_case=Depends(get_switch_agent_use_case),
    process_tool_result_use_case=Depends(get_process_tool_result_use_case),
    handle_approval_use_case=Depends(get_handle_approval_use_case)
):
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
    # Использовать MessageOrchestrationService для всех типов сообщений
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
                use_case_request = ProcessMessageRequest(
                    session_id=session_id,
                    message=content,
                    agent_type=agent_type
                )
                async for chunk in process_message_use_case.execute(use_case_request):
                    # Преобразовать в SSE формат
                    chunk_json = chunk.model_dump_json(exclude_none=False)
                    if chunk.type == "plan_approval_required":
                        logger.info(f"[SSE] Sending plan_approval_required chunk: {chunk_json}")
                    yield f"data: {chunk_json}\n\n"
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
                use_case_request = ProcessToolResultRequest(
                    session_id=session_id,
                    call_id=call_id,
                    result=result,
                    error=error
                )
                async for chunk in process_tool_result_use_case.execute(use_case_request):
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
                # Переключаем агента через Use Case
                use_case_request = SwitchAgentRequest(
                    session_id=session_id,
                    new_agent_type=agent_type
                )
                async for chunk in switch_agent_use_case.execute(use_case_request):
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
        modified_arguments = message_data.get("modified_arguments")
        feedback = message_data.get("feedback")
        
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
                # Обрабатываем HITL решение через Use Case
                use_case_request = HandleApprovalRequest(
                    session_id=session_id,
                    approval_request_id=call_id,
                    approved=(decision == "approved"),
                    approval_type="hitl"
                )
                async for chunk in handle_approval_use_case.execute(use_case_request):
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
    
    elif message_type == "plan_decision":
        # Обработка Plan Approval решения пользователя
        approval_request_id = message_data.get("approval_request_id")
        decision = message_data.get("decision")
        feedback = message_data.get("feedback")
        
        if not approval_request_id or not decision:
            raise HTTPException(
                status_code=400,
                detail="approval_request_id and decision are required for plan_decision message"
            )
        
        logger.info(
            f"Processing Plan Approval decision for session {session_id}: "
            f"approval_request_id={approval_request_id}, decision={decision}"
        )
        
        async def plan_decision_generate():
            try:
                # Обрабатываем Plan Approval решение через Use Case
                use_case_request = HandleApprovalRequest(
                    session_id=session_id,
                    approval_request_id=approval_request_id,
                    approved=(decision == "approved"),
                    approval_type="plan"
                )
                async for chunk in handle_approval_use_case.execute(use_case_request):
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Error processing Plan Approval decision: {e}", exc_info=True)
                error_chunk = StreamChunk(
                    type="error",
                    error=str(e),
                    is_final=True
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            plan_decision_generate(),
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
