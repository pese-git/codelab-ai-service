"""
Сервис автоматической очистки старых сессий.

Фоновый сервис для периодической очистки неактивных сессий
и предотвращения memory leaks.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable

from ...domain.services.session_management import SessionManagementService

logger = logging.getLogger("agent-runtime.infrastructure.session_cleanup")


class SessionCleanupService:
    """
    Сервис автоматической очистки старых сессий.
    
    Запускает фоновую задачу для периодической очистки
    неактивных сессий старше указанного возраста.
    
    Атрибуты:
        _session_service_factory: Фабрика для создания session service с новой DB сессией
        _cleanup_interval_hours: Интервал между очистками (часы)
        _max_age_hours: Максимальный возраст сессии (часы)
        _task: Фоновая задача
    
    Пример:
        >>> async def create_session_service():
        ...     async with async_session_maker() as db:
        ...         repo = SessionRepositoryImpl(db)
        ...         return SessionManagementService(repo, event_publisher)
        >>> cleanup_service = SessionCleanupService(
        ...     session_service_factory=create_session_service,
        ...     cleanup_interval_hours=1,
        ...     max_age_hours=24
        ... )
        >>> await cleanup_service.start()
    """
    
    def __init__(
        self,
        session_service_factory: Callable[[], Awaitable[SessionManagementService]],
        cleanup_interval_hours: int = 1,
        max_age_hours: int = 24
    ):
        """
        Инициализация сервиса очистки.
        
        Args:
            session_service_factory: Async фабрика для создания session service
            cleanup_interval_hours: Интервал между очистками (часы)
            max_age_hours: Максимальный возраст сессии (часы)
        """
        self._session_service_factory = session_service_factory
        self._cleanup_interval = cleanup_interval_hours
        self._max_age = max_age_hours
        self._task: asyncio.Task | None = None
        self._running = False
        
        logger.info(
            f"SessionCleanupService initialized "
            f"(interval={cleanup_interval_hours}h, max_age={max_age_hours}h)"
        )
    
    async def start(self):
        """
        Запустить фоновую очистку.
        
        Создает asyncio задачу для периодической очистки.
        
        Пример:
            >>> await cleanup_service.start()
        """
        if self._running:
            logger.warning("SessionCleanupService already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info("SessionCleanupService started")
    
    async def stop(self):
        """
        Остановить фоновую очистку.
        
        Отменяет фоновую задачу и ждет её завершения.
        
        Пример:
            >>> await cleanup_service.stop()
        """
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("SessionCleanupService stopped")
    
    async def _cleanup_loop(self):
        """
        Цикл автоматической очистки.
        
        Выполняется периодически в фоновом режиме.
        """
        while self._running:
            try:
                # Подождать интервал
                await asyncio.sleep(self._cleanup_interval * 3600)
                
                # Выполнить очистку
                await self._perform_cleanup()
                
            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                # Продолжить работу несмотря на ошибку
    
    async def _perform_cleanup(self):
        """
        Выполнить очистку старых сессий.
        
        Создает новый session service через фабрику и вызывает cleanup.
        """
        try:
            logger.info(
                f"Starting cleanup of sessions older than {self._max_age} hours"
            )
            
            # Создать новый session service с fresh DB session
            session_service = await self._session_service_factory()
            
            # Очистить через доменный сервис
            count = await session_service.cleanup_old_sessions(
                max_age_hours=self._max_age
            )
            
            if count > 0:
                logger.info(f"Cleaned up {count} old sessions")
            else:
                logger.debug("No old sessions to clean up")
                
        except Exception as e:
            logger.error(f"Error performing cleanup: {e}", exc_info=True)
    
    async def cleanup_now(self) -> int:
        """
        Выполнить очистку немедленно (вне расписания).
        
        Полезно для ручного запуска или тестирования.
        
        Returns:
            Количество очищенных сессий
            
        Пример:
            >>> count = await cleanup_service.cleanup_now()
            >>> print(f"Cleaned {count} sessions")
        """
        logger.info("Manual cleanup triggered")
        await self._perform_cleanup()
        return 0  # TODO: Вернуть реальное количество
    
    def is_running(self) -> bool:
        """
        Проверить, запущен ли сервис.
        
        Returns:
            True если сервис запущен
        """
        return self._running
