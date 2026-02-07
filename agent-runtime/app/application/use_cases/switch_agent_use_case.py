"""
Use Case для явного переключения агента.

Координирует переключение агента для сессии с сохранением контекста.
"""

import logging
from typing import Optional, AsyncGenerator
from dataclasses import dataclass

from .base_use_case import StreamingUseCase
from ...models.schemas import StreamChunk
from ...domain.agent_context.value_objects.agent_capabilities import AgentType

logger = logging.getLogger("agent-runtime.use_cases.switch_agent")


@dataclass
class SwitchAgentRequest:
    """
    Запрос на переключение агента.
    
    Attributes:
        session_id: ID сессии
        target_agent: Целевой тип агента
        reason: Причина переключения (опционально)
    
    Пример:
        >>> request = SwitchAgentRequest(
        ...     session_id="session-123",
        ...     target_agent=AgentType.CODER,
        ...     reason="User requested code changes"
        ... )
    """
    session_id: str
    target_agent: AgentType
    reason: Optional[str] = None


class SwitchAgentUseCase(StreamingUseCase[SwitchAgentRequest, StreamChunk]):
    """
    Use Case для явного переключения агента.
    
    Координирует:
    1. Валидацию возможности переключения
    2. Сохранение контекста текущего агента
    3. Переключение на новый агент
    4. Уведомление клиента о переключении
    
    Зависимости:
        - AgentSwitcher: Переключение агентов
        - SessionLockManager: Управление блокировками
    
    Пример:
        >>> use_case = SwitchAgentUseCase(
        ...     agent_switcher=agent_switcher,
        ...     lock_manager=lock_manager
        ... )
        >>> request = SwitchAgentRequest(
        ...     session_id="session-123",
        ...     target_agent=AgentType.CODER
        ... )
        >>> async for chunk in use_case.execute(request):
        ...     print(chunk)
    """
    
    def __init__(
        self,
        agent_switcher,  # AgentSwitcher
        lock_manager  # SessionLockManager
    ):
        """
        Инициализация Use Case.
        
        Args:
            agent_switcher: Switcher агентов из Domain Layer
            lock_manager: Менеджер блокировок сессий
        """
        self._agent_switcher = agent_switcher
        self._lock_manager = lock_manager
        
        logger.debug("SwitchAgentUseCase инициализирован")
    
    async def execute(
        self,
        request: SwitchAgentRequest
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Выполнить переключение агента.
        
        Args:
            request: Запрос с параметрами переключения
            
        Yields:
            StreamChunk: Чанки для SSE streaming
            
        Raises:
            SessionNotFoundError: Если сессия не найдена
            AgentSwitchError: Если переключение невозможно
            ValueError: Если target_agent невалиден
            
        Пример потока:
            1. agent_switched (информация о переключении)
            2. done (завершение)
        """
        logger.info(
            f"Переключение агента для сессии {request.session_id} "
            f"на {request.target_agent.value}"
        )
        
        try:
            # Блокировка сессии для предотвращения конкурентных запросов
            async with self._lock_manager.lock(request.session_id):
                # Делегировать переключение в AgentSwitcher (Domain Layer)
                async for chunk in self._agent_switcher.switch(
                    session_id=request.session_id,
                    target_agent=request.target_agent,
                    reason=request.reason
                ):
                    yield chunk
                    
                    # Логирование переключения
                    if chunk.type == "agent_switched":
                        logger.info(
                            f"Агент успешно переключен: "
                            f"{chunk.metadata.get('from_agent')} -> "
                            f"{chunk.metadata.get('to_agent')}"
                        )
        
        except Exception as e:
            logger.error(
                f"Ошибка переключения агента для сессии {request.session_id}: {e}",
                exc_info=True
            )
            # Отправить error chunk клиенту
            yield StreamChunk(
                type="error",
                error=str(e),
                is_final=True
            )
