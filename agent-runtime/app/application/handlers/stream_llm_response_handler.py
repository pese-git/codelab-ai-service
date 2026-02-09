"""
Application Handler для стриминга LLM ответов.

Координирует use case стриминга ответов от LLM:
- Фильтрация инструментов
- Вызов LLM
- Обработка ответа
- Публикация событий
- Сохранение результатов
- Генерация стрима
"""

import time
import json
import logging
import uuid
from typing import AsyncGenerator, List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.interfaces.stream_handler import IStreamHandler
from ...domain.services.llm_response_processor import LLMResponseProcessor
from ...domain.services.tool_filter_service import ToolFilterService
from ...domain.session_context.services import ConversationManagementService
from ...domain.services.approval_management import ApprovalManager
from ...domain.entities.llm_response import ProcessedResponse
from ...infrastructure.llm.llm_client import LLMClient
from ...infrastructure.events.llm_event_publisher import LLMEventPublisher
from ...models.schemas import StreamChunk

logger = logging.getLogger("agent-runtime.application.stream_llm_response_handler")


class StreamLLMResponseHandler(IStreamHandler):
    """
    Application Service для стриминга ответов LLM.
    
    Координирует use case стриминга:
    1. Фильтрация инструментов по разрешенным
    2. Вызов LLM через клиент
    3. Обработка ответа через доменный сервис
    4. Публикация событий
    5. Сохранение результатов через доменные сервисы
    6. Генерация стрима для API слоя
    
    НЕ содержит:
    - Бизнес-логику (делегирует в Domain)
    - Технические детали LLM API (делегирует в Infrastructure)
    - HTTP/SSE логику (делегирует в API Layer)
    
    Атрибуты:
        _llm_client: Клиент для вызова LLM
        _tool_filter: Сервис фильтрации инструментов
        _response_processor: Сервис обработки ответов
        _event_publisher: Publisher для событий
        _session_service: Сервис управления сессиями
        _approval_manager: Unified approval manager
    
    Пример:
        >>> handler = StreamLLMResponseHandler(
        ...     llm_client=llm_client,
        ...     tool_filter=tool_filter,
        ...     response_processor=response_processor,
        ...     event_publisher=event_publisher,
        ...     session_service=session_service,
        ...     approval_manager=approval_manager
        ... )
        >>> async for chunk in handler.handle(
        ...     session_id="session-1",
        ...     history=[...],
        ...     model="gpt-4"
        ... ):
        ...     print(chunk)
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        tool_filter: ToolFilterService,
        response_processor: LLMResponseProcessor,
        event_publisher: LLMEventPublisher,
        session_service: ConversationManagementService,
        approval_manager: ApprovalManager,
        db: Optional[AsyncSession] = None
    ):
        """
        Инициализация handler.
        
        Args:
            llm_client: Клиент для вызова LLM
            tool_filter: Сервис фильтрации инструментов
            response_processor: Сервис обработки ответов
            event_publisher: Publisher для событий
            session_service: Сервис управления сессиями
            approval_manager: Unified approval manager
            db: Сессия БД для commit'ов (опционально)
        """
        self._llm_client = llm_client
        self._tool_filter = tool_filter
        self._response_processor = response_processor
        self._event_publisher = event_publisher
        self._session_service = session_service
        self._approval_manager = approval_manager
        self._db = db
        
        logger.info("StreamLLMResponseHandler initialized with ApprovalManager")
    
    async def handle(
        self,
        session_id: str,
        history: List[Dict[str, Any]],
        model: str,
        allowed_tools: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать запрос на стриминг ответа LLM.
        
        Use Case:
        1. Фильтровать инструменты по разрешенным
        2. Опубликовать событие начала запроса
        3. Вызвать LLM через клиент
        4. Обработать ответ через доменный сервис
        5. Обработать tool calls или обычное сообщение
        6. Опубликовать событие завершения
        7. Сгенерировать стрим для клиента
        
        Args:
            session_id: ID сессии
            history: История сообщений для LLM
            model: Имя модели
            allowed_tools: Список разрешенных инструментов (None = все)
            correlation_id: ID для трассировки (опционально)
            
        Yields:
            StreamChunk: Чанки для SSE стриминга
            
        Пример:
            >>> async for chunk in handler.handle(
            ...     session_id="session-1",
            ...     history=[{"role": "user", "content": "Hello"}],
            ...     model="gpt-4",
            ...     allowed_tools=["read_file", "write_file"]
            ... ):
            ...     if chunk.type == "tool_call":
            ...         print(f"Tool call: {chunk.tool_name}")
            ...     elif chunk.type == "assistant_message":
            ...         print(f"Message: {chunk.content}")
        """
        try:
            logger.debug(
                f"StreamLLMResponseHandler.handle() called for session {session_id} "
                f"with {len(history)} messages"
            )
            logger.info(
                f"Starting LLM stream for session {session_id} "
                f"with {len(history)} messages"
            )
            
            # 1. Фильтрация инструментов (Domain)
            tools = self._tool_filter.filter_tools(allowed_tools)
            
            # 2. Публикация события начала (Infrastructure)
            await self._event_publisher.publish_request_started(
                session_id=session_id,
                model=model,
                messages_count=len(history),
                tools_count=len(tools),
                correlation_id=correlation_id
            )
            
            # 3. Вызов LLM (Infrastructure)
            start_time = time.time()
            response = await self._llm_client.chat_completion(
                model=model,
                messages=history,
                tools=tools
            )
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.debug(
                f"LLM response received: content_length={len(response.content)}, "
                f"tool_calls={len(response.tool_calls)}, "
                f"duration={duration_ms}ms"
            )
            
            # 4. Обработка ответа (Domain)
            processed = self._response_processor.process_response(response)
            
            # Логирование предупреждений валидации
            if processed.validation_warnings:
                for warning in processed.validation_warnings:
                    logger.warning(f"Validation warning: {warning}")
            
            # 5. Обработка tool calls или обычного сообщения
            if processed.has_tool_calls():
                chunk = await self._handle_tool_call(
                    session_id=session_id,
                    processed=processed,
                    duration_ms=duration_ms,
                    history=history,
                    correlation_id=correlation_id
                )
            else:
                chunk = await self._handle_assistant_message(
                    session_id=session_id,
                    processed=processed,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id
                )
            
            # 6. Генерация стрима
            yield chunk
            
        except Exception as e:
            logger.error(
                f"Exception in stream_response for session {session_id}: {e}",
                exc_info=True
            )
            
            # Публикация события ошибки
            await self._event_publisher.publish_request_failed(
                session_id=session_id,
                model=model,
                error=str(e),
                correlation_id=correlation_id
            )
            
            # Генерация error chunk
            yield StreamChunk(
                type="error",
                error=str(e),
                is_final=True
            )
    
    async def _handle_tool_call(
        self,
        session_id: str,
        processed: ProcessedResponse,
        duration_ms: int,
        history: List[Dict[str, Any]],
        correlation_id: Optional[str]
    ) -> StreamChunk:
        """
        Обработать tool call.
        
        Координация:
        1. Извлечение текущего агента из истории
        2. Публикация события tool execution requested
        3. Сохранение pending approval (если требуется)
        4. Публикация события tool approval required (если требуется)
        5. Сохранение сообщения в сессию
        6. Публикация события завершения LLM запроса
        7. Создание chunk для стрима
        
        Args:
            session_id: ID сессии
            processed: Обработанный ответ LLM
            duration_ms: Длительность запроса в мс
            history: История сообщений (для извлечения агента)
            correlation_id: ID для трассировки
            
        Returns:
            StreamChunk для tool call
        """
        tool_call = processed.get_first_tool_call()
        
        if not tool_call:
            raise ValueError("No tool call found in processed response")
        
        logger.info(
            f"Tool call detected: {tool_call.tool_name} (call_id={tool_call.id})"
        )
        
        # Check if this is a virtual tool that should be handled internally
        from app.domain.services.tool_registry import VIRTUAL_TOOLS
        if tool_call.tool_name in VIRTUAL_TOOLS:
            logger.info(
                f"Virtual tool detected: {tool_call.tool_name} - handling internally"
            )
            return await self._handle_virtual_tool(
                session_id=session_id,
                tool_call=tool_call,
                processed=processed,
                duration_ms=duration_ms,
                history=history,
                correlation_id=correlation_id
            )
        
        # 1. Извлечение текущего агента из истории
        current_agent = "unknown"
        for msg in reversed(history):
            if msg.get("role") == "assistant" and msg.get("name"):
                current_agent = msg["name"]
                break
        
        # 2. Публикация события tool execution requested
        await self._event_publisher.publish_tool_execution_requested(
            session_id=session_id,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            call_id=tool_call.id,
            agent=current_agent,
            correlation_id=correlation_id
        )
        
        # 3. Approval: Сохранение pending approval (если требуется)
        if processed.requires_approval:
            await self._approval_manager.add_pending(
                request_id=tool_call.id,
                request_type="tool",
                subject=tool_call.tool_name,
                session_id=session_id,
                details={"arguments": tool_call.arguments},
                reason=processed.approval_reason
            )
            
            logger.info(
                f"Added pending approval for request_id={tool_call.id}, "
                f"tool={tool_call.tool_name}, reason={processed.approval_reason}"
            )
            
            # 4. Публикация события tool approval required
            await self._event_publisher.publish_tool_approval_required(
                session_id=session_id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                call_id=tool_call.id,
                reason=processed.approval_reason or "Unknown",
                correlation_id=correlation_id
            )
        
        # 5. Сохранение сообщения через доменный сервис
        tool_call_dict = tool_call.to_dict()
        
        # DIAGNOSTIC: Логирование формата tool_call перед сохранением
        logger.info(
            f"Saving assistant message with tool_call: {tool_call.tool_name}, "
            f"call_id={tool_call.id}"
        )
        logger.debug(f"Tool call dict format:\n{json.dumps(tool_call_dict, indent=2, ensure_ascii=False)}")
        
        await self._session_service.add_message(
            conversation_id=session_id,
            role="assistant",
            content="",
            tool_calls=[tool_call_dict]
        )
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Commit после сохранения assistant message
        if self._db:
            await self._db.commit()
            logger.debug(
                f"Assistant message with tool_call persisted and committed: {tool_call.tool_name}"
            )
        else:
            logger.debug(
                f"Assistant message with tool_call persisted (no db commit): {tool_call.tool_name}"
            )
        
        # 6. Публикация события завершения LLM запроса
        await self._event_publisher.publish_request_completed(
            session_id=session_id,
            model=processed.model,
            duration_ms=duration_ms,
            usage=processed.usage,
            has_tool_calls=True,
            correlation_id=correlation_id
        )
        
        # 7. Создание chunk для стрима
        return StreamChunk(
            type="tool_call",
            call_id=tool_call.id,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            requires_approval=processed.requires_approval,
            is_final=True
        )
    
    async def _handle_assistant_message(
        self,
        session_id: str,
        processed: ProcessedResponse,
        duration_ms: int,
        correlation_id: Optional[str]
    ) -> StreamChunk:
        """
        Обработать обычное сообщение ассистента.
        
        Координация:
        1. Сохранение сообщения в сессию
        2. Публикация события завершения LLM запроса
        3. Создание chunk для стрима
        
        Args:
            session_id: ID сессии
            processed: Обработанный ответ LLM
            duration_ms: Длительность запроса в мс
            correlation_id: ID для трассировки
            
        Returns:
            StreamChunk для assistant message
        """
        logger.info(
            f"Sending assistant message: {len(processed.content)} chars"
        )
        
        # 1. Сохранение сообщения через доменный сервис
        await self._session_service.add_message(
            conversation_id=session_id,
            role="assistant",
            content=processed.content
        )
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Commit после сохранения assistant message
        if self._db:
            await self._db.commit()
            logger.debug(f"Assistant message persisted and committed (no tool calls)")
        else:
            logger.debug(f"Assistant message persisted (no db commit, no tool calls)")
        
        # 2. Публикация события завершения
        await self._event_publisher.publish_request_completed(
            session_id=session_id,
            model=processed.model,
            duration_ms=duration_ms,
            usage=processed.usage,
            has_tool_calls=False,
            correlation_id=correlation_id
        )
        
        # 3. Создание chunk для стрима
        return StreamChunk(
            type="assistant_message",
            content=processed.content,
            token=processed.content,
            is_final=True
        )
    
    async def _handle_virtual_tool(
        self,
        session_id: str,
        tool_call,
        processed: ProcessedResponse,
        duration_ms: int,
        history: List[Dict[str, Any]],
        correlation_id: Optional[str]
    ) -> StreamChunk:
        """
        Обработать виртуальный инструмент (attempt_completion, ask_followup_question, create_plan).
        
        Виртуальные инструменты не отправляются на клиент для выполнения,
        а обрабатываются внутри agent-runtime.
        
        Args:
            session_id: ID сессии
            tool_call: Вызов виртуального инструмента
            processed: Обработанный ответ LLM
            duration_ms: Длительность запроса в мс
            history: История сообщений
            correlation_id: ID для трассировки
            
        Returns:
            StreamChunk с результатом обработки виртуального инструмента
        """
        logger.info(
            f"Handling virtual tool: {tool_call.tool_name} in session {session_id}"
        )
        
        # Извлечение текущего агента
        current_agent = "unknown"
        for msg in reversed(history):
            if msg.get("role") == "assistant" and msg.get("name"):
                current_agent = msg["name"]
                break
        
        # Публикация события
        await self._event_publisher.publish_tool_execution_requested(
            session_id=session_id,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            call_id=tool_call.id,
            agent=current_agent,
            correlation_id=correlation_id
        )
        
        # Сохранение assistant message с tool_call
        tool_call_dict = tool_call.to_dict()
        await self._session_service.add_message(
            conversation_id=session_id,
            role="assistant",
            content="",
            tool_calls=[tool_call_dict]
        )
        
        if self._db:
            await self._db.commit()
            logger.debug(f"Virtual tool call persisted: {tool_call.tool_name}")
        
        # Обработка конкретного виртуального инструмента
        if tool_call.tool_name == "create_plan":
            result = await self._handle_create_plan(
                session_id=session_id,
                tool_call=tool_call,
                current_agent=current_agent
            )
        elif tool_call.tool_name == "attempt_completion":
            result = await self._handle_attempt_completion(
                session_id=session_id,
                tool_call=tool_call
            )
        elif tool_call.tool_name == "ask_followup_question":
            result = await self._handle_ask_followup_question(
                session_id=session_id,
                tool_call=tool_call
            )
        else:
            result = f"Unknown virtual tool: {tool_call.tool_name}"
            logger.error(result)
        
        # Сохранение tool result
        await self._session_service.add_message(
            conversation_id=session_id,
            role="tool",
            content=result,
            tool_call_id=tool_call.id
        )
        
        if self._db:
            await self._db.commit()
            logger.debug(f"Virtual tool result persisted: {tool_call.tool_name}")
        
        # Публикация события завершения
        await self._event_publisher.publish_request_completed(
            session_id=session_id,
            model=processed.model,
            duration_ms=duration_ms,
            usage=processed.usage,
            has_tool_calls=True,
            correlation_id=correlation_id
        )
        
        # Для виртуальных инструментов возвращаем специальные типы chunk
        if tool_call.tool_name == "create_plan":
            # Парсим результат создания плана
            result_data = json.loads(result)
            
            if "error" in result_data:
                # Если ошибка, возвращаем как сообщение
                return StreamChunk(
                    type="assistant_message",
                    content=f"Failed to create plan: {result_data['error']}",
                    is_final=True
                )
            
            # Для create_plan возвращаем plan_approval_required
            return StreamChunk(
                type="plan_approval_required",
                plan_id=result_data.get("plan_id"),
                plan_summary={
                    "title": result_data.get("title", "Execution Plan"),
                    "description": result_data.get("description", ""),
                    "subtasks_count": result_data.get("subtasks_count", 0)
                },
                metadata={"requires_approval": True},
                is_final=True
            )
        elif tool_call.tool_name == "attempt_completion":
            # Для attempt_completion возвращаем обычное сообщение
            result_data = json.loads(result)
            return StreamChunk(
                type="assistant_message",
                content=result_data.get("result", "Task completed"),
                is_final=True
            )
        elif tool_call.tool_name == "ask_followup_question":
            # Для ask_followup_question возвращаем вопрос как сообщение
            question_data = json.loads(result)
            return StreamChunk(
                type="assistant_message",
                content=question_data.get("question", ""),
                metadata={"suggestions": question_data.get("suggestions", [])},
                is_final=True
            )
        else:
            # Fallback для неизвестных виртуальных инструментов
            return StreamChunk(
                type="assistant_message",
                content=result,
                is_final=True
            )
    
    async def _handle_create_plan(
        self,
        session_id: str,
        tool_call,
        current_agent: str
    ) -> str:
        """
        Обработать create_plan - создание плана выполнения.
        
        Вызывает ArchitectAgent.create_plan() для создания плана в БД,
        затем возвращает информацию о плане для approval.
        """
        logger.info(f"Creating execution plan for session {session_id}")
        
        # Извлекаем параметры из tool_call
        title = tool_call.arguments.get("title", "Execution Plan")
        description = tool_call.arguments.get("description", "")
        subtasks = tool_call.arguments.get("subtasks", [])
        
        if not subtasks:
            error_msg = "create_plan requires at least one subtask"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        try:
            # Создаем план напрямую, используя новую ExecutionPlan entity
            from app.domain.execution_context.entities import ExecutionPlan, Subtask
            from app.domain.execution_context.value_objects import PlanId, SubtaskId
            from app.domain.session_context.value_objects import ConversationId
            from app.domain.agent_context.value_objects import AgentId
            from app.infrastructure.persistence.repositories.execution_plan_repository_impl import ExecutionPlanRepositoryImpl
            
            # Создаем plan_repository с текущей db сессией из SSEUnitOfWork
            if not self._db:
                raise ValueError("Database session not available in StreamLLMResponseHandler")
            
            plan_repository = ExecutionPlanRepositoryImpl(self._db)
            
            # Создаем ExecutionPlan entity
            plan_id = str(uuid.uuid4())
            plan = ExecutionPlan(
                id=PlanId(plan_id),
                conversation_id=ConversationId(session_id),
                goal=f"{title}\n\n{description}" if description else title,
                metadata={
                    "created_by": "architect",
                    "title": title,
                    "description": description
                }
            )
            
            # Создаем subtasks с ID
            subtask_ids = [str(uuid.uuid4()) for _ in subtasks]
            
            for i, subtask_data in enumerate(subtasks):
                # Конвертируем dependency indices в IDs
                dep_indices = subtask_data.get("dependencies", [])
                dep_ids = []
                for dep_idx in dep_indices:
                    if isinstance(dep_idx, int) and 0 <= dep_idx < len(subtask_ids):
                        dep_ids.append(SubtaskId(subtask_ids[dep_idx]))
                
                # Определяем agent_id из agent name
                agent_name = subtask_data["agent"]
                agent_id = AgentId(value=agent_name)
                
                subtask = Subtask(
                    id=SubtaskId(subtask_ids[i]),
                    description=subtask_data.get("description", subtask_data.get("title", "")),
                    agent_id=agent_id,
                    dependencies=dep_ids,
                    estimated_time=f"{subtask_data.get('estimated_time_minutes', 5)} min",
                    metadata={
                        "index": i,
                        "title": subtask_data.get("title", ""),
                        "dependency_indices": dep_indices
                    }
                )
                plan.add_subtask(subtask)
            
            # Сохраняем план в БД (в статусе DRAFT)
            # Commit произойдет автоматически через SSEUnitOfWork
            await plan_repository.save(plan)
            
            # Flush для немедленной видимости в текущей транзакции
            await self._db.flush()
            
            logger.info(
                f"Plan {plan.id.value} created successfully with {len(plan.subtasks)} subtasks"
            )
            
            # Возвращаем информацию о созданном плане
            return json.dumps({
                "status": "plan_created",
                "plan_id": plan.id.value,
                "title": title,
                "description": description,
                "subtasks_count": len(subtasks),
                "requires_approval": True
            })
            
        except Exception as e:
            error_msg = f"Failed to create plan: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg})
    
    async def _handle_attempt_completion(
        self,
        session_id: str,
        tool_call
    ) -> str:
        """Обработать attempt_completion - завершение задачи."""
        result = tool_call.arguments.get("result", "Task completed")
        logger.info(f"Task completion for session {session_id}: {result[:100]}")
        
        return json.dumps({
            "status": "completed",
            "result": result
        })
    
    async def _handle_ask_followup_question(
        self,
        session_id: str,
        tool_call
    ) -> str:
        """Обработать ask_followup_question - запрос уточнения."""
        question = tool_call.arguments.get("question", "")
        suggestions = tool_call.arguments.get("suggestions", [])
        
        logger.info(f"Followup question for session {session_id}: {question}")
        
        return json.dumps({
            "status": "question_asked",
            "question": question,
            "suggestions": suggestions
        })
