"""
Сервис для явного переключения агентов.

Отвечает за обработку явных запросов на переключение агентов
от пользователя или системы.
"""

import logging
from typing import AsyncGenerator, Optional, TYPE_CHECKING

from ..entities.agent_context import AgentType
from ...models.schemas import StreamChunk
from ...core.errors import AgentSwitchError

if TYPE_CHECKING:
    from .agent_orchestration import AgentOrchestrationService
    from .helpers.agent_switch_helper import AgentSwitchHelper

logger = logging.getLogger("agent-runtime.domain.agent_switcher")


class AgentSwitcher:
    """
    Сервис для явного переключения агентов.
    
    Ответственности:
    - Валидация запросов на переключение
    - Выполнение переключения через AgentOrchestrationService
    - Генерация уведомлений о переключении
    - Получение информации о текущем агенте
    - Сброс сессии к Orchestrator
    
    Атрибуты:
        _agent_service: Сервис оркестрации агентов
        _switch_helper: Helper для переключения агентов
    """
    
    def __init__(
        self,
        agent_service: "AgentOrchestrationService",
        switch_helper: "AgentSwitchHelper"
    ):
        """
        Инициализация switcher.
        
        Args:
            agent_service: Сервис оркестрации агентов
            switch_helper: Helper для переключения агентов
        """
        self._agent_service = agent_service
        self._switch_helper = switch_helper
        
        logger.debug("AgentSwitcher инициализирован")
    
    async def switch(
        self,
        session_id: str,
        target_agent: AgentType,
        reason: Optional[str] = None,
        confidence: str = "high"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Выполнить явное переключение агента.
        
        Переключает текущего агента сессии на указанный целевой агент
        и генерирует уведомление для клиента.
        
        Args:
            session_id: ID сессии
            target_agent: Целевой тип агента
            reason: Причина переключения (опционально)
            confidence: Уровень уверенности (по умолчанию "high")
            
        Yields:
            StreamChunk: Уведомление о переключении
            
        Raises:
            AgentSwitchError: Если переключение невозможно
        """
        # Установить reason по умолчанию, если не указан
        if reason is None:
            reason = f"User requested switch to {target_agent.value}"
        
        logger.info(
            f"Явное переключение агента для сессии {session_id} "
            f"на {target_agent.value}: {reason}"
        )
        
        try:
            # Получить текущий контекст
            context = await self._agent_service.get_or_create_context(
                session_id=session_id,
                initial_agent=AgentType.ORCHESTRATOR
            )
            
            from_agent = context.current_agent
            
            # Проверить, не является ли целевой агент уже текущим
            if from_agent == target_agent:
                logger.info(
                    f"Агент {target_agent.value} уже активен для сессии {session_id}, "
                    "переключение не требуется"
                )
                
                # Все равно отправить уведомление для консистентности
                yield self._switch_helper.create_agent_switched_chunk(
                    from_agent=from_agent,
                    to_agent=target_agent,
                    reason=reason,
                    confidence=confidence,
                    is_final=True
                )
                return
            
            # Выполнить переключение агента
            context = await self._switch_helper.execute_agent_switch(
                session_id=session_id,
                target_agent=target_agent,
                reason=reason,
                confidence=confidence
            )
            
            # Уведомить о переключении
            yield self._switch_helper.create_agent_switched_chunk(
                from_agent=from_agent,
                to_agent=target_agent,
                reason=reason,
                confidence=confidence,
                is_final=True
            )
            
        except Exception as e:
            error_msg = f"Не удалось переключить агента для сессии {session_id}: {e}"
            logger.error(error_msg, exc_info=True)
            raise AgentSwitchError(error_msg) from e
    
    async def get_current_agent(self, session_id: str) -> Optional[AgentType]:
        """
        Получить текущего активного агента для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Тип текущего агента или None если сессия не существует
            
        Пример:
            >>> agent = await switcher.get_current_agent("session-1")
            >>> if agent:
            ...     print(f"Current agent: {agent.value}")
        """
        logger.debug(f"Получение текущего агента для сессии {session_id}")
        
        try:
            return await self._agent_service.get_current_agent(session_id)
        except Exception as e:
            logger.error(
                f"Ошибка при получении текущего агента для сессии {session_id}: {e}",
                exc_info=True
            )
            return None
    
    async def reset_to_orchestrator(self, session_id: str) -> None:
        """
        Сбросить сессию к Orchestrator агенту.
        
        Используется для возврата сессии в начальное состояние,
        где Orchestrator может заново проанализировать задачу.
        
        Args:
            session_id: ID сессии
            
        Пример:
            >>> await switcher.reset_to_orchestrator("session-1")
        """
        logger.info(f"Сброс сессии {session_id} к Orchestrator агенту")
        
        try:
            await self._switch_helper.execute_agent_switch(
                session_id=session_id,
                target_agent=AgentType.ORCHESTRATOR,
                reason="Session reset",
                confidence="high"
            )
        except Exception as e:
            error_msg = f"Не удалось сбросить сессию {session_id}: {e}"
            logger.error(error_msg, exc_info=True)
            raise AgentSwitchError(error_msg) from e
