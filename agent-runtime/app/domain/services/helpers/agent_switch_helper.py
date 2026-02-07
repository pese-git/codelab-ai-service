"""
Вспомогательный сервис для обработки переключений агентов.

Инкапсулирует общую логику переключения агентов, используемую
в MessageProcessor и ToolResultHandler для устранения дублирования кода.
"""

import logging
from typing import Optional, TYPE_CHECKING

from ...agent_context.value_objects.agent_capabilities import AgentType
from ...agent_context.entities.agent import Agent as AgentContext
from ....models.schemas import StreamChunk

if TYPE_CHECKING:
    from ..session_management import SessionManagementService
    from ..agent_orchestration import AgentOrchestrationService

logger = logging.getLogger("agent-runtime.domain.helpers.agent_switch")


class AgentSwitchHelper:
    """
    Вспомогательный сервис для обработки переключений агентов.
    
    Инкапсулирует общую логику, используемую в MessageProcessor и ToolResultHandler:
    - Поиск call_id для switch_mode tool_call
    - Добавление tool_result для switch_mode
    - Выполнение переключения агента
    - Генерация StreamChunk для уведомления
    
    Атрибуты:
        _session_service: Сервис управления сессиями
        _agent_service: Сервис оркестрации агентов
    """
    
    def __init__(
        self,
        session_service: "SessionManagementService",
        agent_service: "AgentOrchestrationService"
    ):
        """
        Инициализация helper.
        
        Args:
            session_service: Сервис управления сессиями
            agent_service: Сервис оркестрации агентов
        """
        self._session_service = session_service
        self._agent_service = agent_service
    
    async def find_switch_mode_call_id(
        self,
        session_id: str
    ) -> Optional[str]:
        """
        Найти call_id последнего switch_mode tool_call в истории.
        
        Ищет в обратном порядке последний assistant message с tool_calls,
        содержащий вызов switch_mode инструмента.
        
        Args:
            session_id: ID сессии
            
        Returns:
            call_id если найден, иначе None
        """
        session = await self._session_service.get_session(session_id)
        history = session.get_history_for_llm()
        
        # Найти последний tool_call для switch_mode
        for msg in reversed(history):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    if tc.get("function", {}).get("name") == "switch_mode":
                        call_id = tc.get("id")
                        logger.debug(
                            f"Найден call_id для switch_mode: {call_id} "
                            f"в сессии {session_id}"
                        )
                        return call_id
        
        logger.debug(f"call_id для switch_mode не найден в сессии {session_id}")
        return None
    
    async def add_switch_mode_tool_result(
        self,
        session_id: str,
        call_id: str,
        target_agent: AgentType
    ) -> None:
        """
        Добавить tool_result для switch_mode в историю сессии.
        
        Предотвращает ошибку "No tool output found" от LLM провайдера,
        добавляя результат выполнения switch_mode инструмента.
        
        Args:
            session_id: ID сессии
            call_id: ID вызова switch_mode
            target_agent: Целевой агент
        """
        logger.debug(
            f"Добавляем tool_result для switch_mode (call_id={call_id}) "
            f"в сессию {session_id}"
        )
        
        await self._session_service.add_tool_result(
            session_id=session_id,
            call_id=call_id,
            result=f"Switched to {target_agent.value} agent",
            error=None
        )
    
    async def execute_agent_switch(
        self,
        session_id: str,
        target_agent: AgentType,
        reason: str,
        confidence: str = "medium"
    ) -> AgentContext:
        """
        Выполнить переключение агента с селективной очисткой контекста.
        
        Процесс:
        1. Получить текущий контекст агента
        2. Подготовить контекст сессии (очистить tool messages)
        3. Выполнить переключение через AgentOrchestrationService
        4. Вернуть обновленный контекст
        
        Селективная очистка предотвращает дублирование tool_call_id
        между агентами и сохраняет результаты работы.
        
        Args:
            session_id: ID сессии
            target_agent: Целевой тип агента
            reason: Причина переключения
            confidence: Уровень уверенности (high/medium/low)
            
        Returns:
            Обновленный контекст агента
        """
        logger.info(
            f"Выполняется переключение агента в сессии {session_id}: "
            f"target={target_agent.value}, reason={reason}, confidence={confidence}"
        )
        
        # 1. Получить текущий контекст для определения from_agent
        try:
            current_context = await self._agent_service.get_or_create_context(
                session_id=session_id,
                initial_agent=AgentType.ORCHESTRATOR
            )
            from_agent = current_context.current_agent.value
        except Exception as e:
            logger.warning(
                f"Не удалось получить текущий контекст для {session_id}: {e}, "
                "используем 'unknown' как from_agent"
            )
            from_agent = "unknown"
        
        # 2. Подготовить контекст сессии (селективная очистка tool messages)
        try:
            cleanup_info = await self._session_service.prepare_agent_switch_context(
                session_id=session_id,
                from_agent=from_agent,
                to_agent=target_agent.value
            )
            
            logger.info(
                f"Session context prepared for agent switch: "
                f"removed {cleanup_info['removed_count']} tool messages, "
                f"preserved result: {bool(cleanup_info.get('preserved_result'))}"
            )
        except Exception as e:
            logger.error(
                f"Ошибка при подготовке контекста сессии для переключения: {e}",
                exc_info=True
            )
            # Продолжаем переключение даже если очистка не удалась
        
        # 3. Выполнить переключение агента
        context = await self._agent_service.switch_agent(
            session_id=session_id,
            target_agent=target_agent,
            reason=reason,
            confidence=confidence
        )
        
        logger.info(
            f"Контекст обновлен после переключения: "
            f"current_agent={context.current_agent.value}, "
            f"switch_count={context.switch_count}"
        )
        
        return context
    
    def create_agent_switched_chunk(
        self,
        from_agent: AgentType,
        to_agent: AgentType,
        reason: str,
        confidence: str = "medium",
        is_final: bool = False
    ) -> StreamChunk:
        """
        Создать StreamChunk для уведомления о переключении агента.
        
        Генерирует стандартизированный chunk для информирования клиента
        о произошедшем переключении агента.
        
        Args:
            from_agent: Исходный агент
            to_agent: Целевой агент
            reason: Причина переключения
            confidence: Уровень уверенности
            is_final: Является ли чанк финальным
            
        Returns:
            StreamChunk с типом "agent_switched"
        """
        return StreamChunk(
            type="agent_switched",
            content=f"Switched to {to_agent.value} agent",
            metadata={
                "from_agent": from_agent.value,
                "to_agent": to_agent.value,
                "reason": reason,
                "confidence": confidence
            },
            is_final=is_final
        )
    
    async def handle_agent_switch_request(
        self,
        session_id: str,
        chunk: StreamChunk,
        current_context: AgentContext
    ) -> tuple[AgentContext, StreamChunk]:
        """
        Обработать запрос на переключение агента от агента.
        
        Комплексный метод, объединяющий:
        1. Извлечение параметров из chunk
        2. Поиск и добавление tool_result для switch_mode
        3. Выполнение переключения
        4. Создание уведомления
        
        Этот метод устраняет дублирование логики между MessageProcessor
        и ToolResultHandler.
        
        Args:
            session_id: ID сессии
            chunk: StreamChunk с типом "switch_agent"
            current_context: Текущий контекст агента
            
        Returns:
            Кортеж (новый_контекст, chunk_уведомления)
        """
        # Извлечь параметры из chunk
        target_agent_str = chunk.metadata.get("target_agent")
        target_agent = AgentType(target_agent_str)
        reason = chunk.metadata.get("reason", "Agent requested switch")
        confidence = chunk.metadata.get("confidence", "medium")
        from_agent = current_context.current_agent
        
        logger.info(
            f"Агент запросил переключение в сессии {session_id}: "
            f"{from_agent.value} -> {target_agent.value}"
        )
        
        # Найти call_id для switch_mode
        switch_call_id = await self.find_switch_mode_call_id(session_id)
        
        # Добавить tool_result для switch_mode, если call_id найден
        if switch_call_id:
            await self.add_switch_mode_tool_result(
                session_id=session_id,
                call_id=switch_call_id,
                target_agent=target_agent
            )
        else:
            logger.warning(
                f"Не найден call_id для switch_mode tool_call в сессии {session_id}, "
                "tool_result не добавлен"
            )
        
        # Выполнить переключение агента
        new_context = await self.execute_agent_switch(
            session_id=session_id,
            target_agent=target_agent,
            reason=reason,
            confidence=confidence
        )
        
        # Создать уведомление о переключении
        notification_chunk = self.create_agent_switched_chunk(
            from_agent=from_agent,
            to_agent=target_agent,
            reason=reason,
            confidence=confidence,
            is_final=False
        )
        
        return new_context, notification_chunk
