"""
Unit of Work Pattern для управления транзакциями в SSE-стримах.

Предоставляет явное управление границами транзакций для долгоживущих
SSE-соединений с поддержкой микро-транзакций.
"""

import logging
import time
from typing import Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from prometheus_client import Histogram, Counter
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger = logging.getLogger("agent-runtime.infrastructure.unit_of_work")
    logger.warning("prometheus_client not available, metrics will be disabled")

logger = logging.getLogger("agent-runtime.infrastructure.unit_of_work")

# Prometheus метрики (если доступны)
if PROMETHEUS_AVAILABLE:
    transaction_duration = Histogram(
        'sse_transaction_duration_seconds',
        'Duration of SSE micro-transactions',
        ['operation']
    )
    
    transaction_commits = Counter(
        'sse_transaction_commits_total',
        'Total number of transaction commits',
        ['operation', 'status']
    )
else:
    transaction_duration = None
    transaction_commits = None


class SSEUnitOfWork:
    """
    Unit of Work для SSE-стримов с поддержкой микро-транзакций.
    
    Классический паттерн UoW (Martin Fowler) - управляет репозиториями
    и гарантирует атомарность транзакций.
    
    Особенности:
    - Создает и управляет сессией БД
    - Предоставляет репозитории с единой сессией
    - Поддерживает явные commit'ы после каждой операции с метриками
    - Автоматически rollback при ошибках
    
    Использование:
        >>> async with SSEUnitOfWork(session_factory=async_session_maker) as uow:
        ...     conversation = await uow.conversations.get(conv_id)
        ...     conversation.add_message(message)
        ...     await uow.conversations.save(conversation)
        ...     await uow.commit(operation="add_message")
    
    Атрибуты:
        _session_factory: Фабрика для создания сессий БД
        _session: Текущая сессия БД
        conversations: Repository для conversations
        agents: Repository для agent contexts
        approvals: Repository для approvals
        execution_plans: Repository для execution plans
    """
    
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession]
    ):
        """
        Инициализация Unit of Work.
        
        Args:
            session_factory: Callable для создания AsyncSession
        """
        self._session_factory = session_factory
        self._session = None
        
        # Репозитории (создаются в __aenter__)
        self.conversations = None
        self.agents = None
        self.approvals = None
        self.execution_plans = None
        
        logger.debug("SSEUnitOfWork initialized")
    
    async def __aenter__(self):
        """
        Вход в контекст - создание сессии БД и репозиториев.
        
        Returns:
            Self для использования в with statement
        """
        # Создать новую сессию
        self._session = self._session_factory()
        logger.debug("SSEUnitOfWork: New session created")
        
        # Создать репозитории с этой сессией
        from .repositories.conversation_repository_impl import ConversationRepositoryImpl
        from .repositories.agent_repository_impl import AgentRepositoryImpl
        from .repositories.approval_repository_impl import ApprovalRepositoryImpl
        from .repositories.execution_plan_repository_impl import ExecutionPlanRepositoryImpl
        
        self.conversations = ConversationRepositoryImpl(self._session)
        self.agents = AgentRepositoryImpl(self._session)
        self.approvals = ApprovalRepositoryImpl(self._session)
        self.execution_plans = ExecutionPlanRepositoryImpl(self._session)
        
        logger.debug("SSEUnitOfWork: Repositories initialized with session")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Выход из контекста - закрытие сессии.
        
        При ошибке выполняется rollback, затем сессия закрывается.
        
        Args:
            exc_type: Тип исключения (если было)
            exc_val: Значение исключения
            exc_tb: Traceback исключения
        """
        if self._session is None:
            return
        
        try:
            if exc_type is not None:
                logger.warning(
                    f"SSEUnitOfWork: Exception occurred ({exc_type.__name__}), "
                    f"rolling back transaction"
                )
                await self._session.rollback()
            else:
                # ✅ Финальный commit при нормальном выходе
                logger.debug("SSEUnitOfWork: Context exiting normally, committing transaction")
                await self._session.commit()
                logger.debug("SSEUnitOfWork: Transaction committed successfully")
        finally:
            # Всегда закрываем сессию (UoW владеет ею)
            await self._session.close()
            logger.debug("SSEUnitOfWork: Session closed")
            self._session = None
            
            # Очистить репозитории
            self.conversations = None
            self.agents = None
            self.approvals = None
            self.execution_plans = None
    
    @property
    def session(self) -> AsyncSession:
        """
        Получить текущую сессию БД.
        
        Returns:
            AsyncSession: Активная сессия БД
            
        Raises:
            RuntimeError: Если UoW не находится в контексте (сессия не создана)
        """
        if self._session is None:
            raise RuntimeError(
                "SSEUnitOfWork is not in context. "
                "Use 'async with SSEUnitOfWork(...) as uow:'"
            )
        return self._session
    
    async def commit(self, operation: str = "unknown"):
        """
        Явный commit текущей транзакции с метриками.
        
        Используется после каждой логической операции для создания
        микро-транзакций в рамках долгого SSE-стрима.
        
        Args:
            operation: Название операции для метрик и логирования
                      (например, "save_messages", "create_session")
        
        Raises:
            RuntimeError: Если UoW не находится в контексте
        """
        if self._session is None:
            raise RuntimeError(
                "SSEUnitOfWork is not in context. "
                "Use 'async with SSEUnitOfWork(...) as uow:'"
            )
        
        start_time = time.time()
        try:
            await self._session.commit()
            duration = time.time() - start_time
            
            # Записать метрики (если доступны)
            if PROMETHEUS_AVAILABLE and transaction_duration and transaction_commits:
                transaction_duration.labels(operation=operation).observe(duration)
                transaction_commits.labels(operation=operation, status="success").inc()
            
            logger.debug(
                f"SSEUnitOfWork: Transaction committed "
                f"(operation={operation}, duration={duration:.3f}s)"
            )
            
            # Предупреждение о долгих транзакциях (> 100ms)
            if duration > 0.1:
                logger.warning(
                    f"⚠️ SLOW TRANSACTION: {operation} took {duration:.3f}s "
                    f"(> 100ms threshold)"
                )
        except Exception as e:
            # Записать метрику ошибки
            if PROMETHEUS_AVAILABLE and transaction_commits:
                transaction_commits.labels(operation=operation, status="error").inc()
            
            logger.error(
                f"SSEUnitOfWork: Commit failed (operation={operation}): {e}",
                exc_info=True
            )
            raise
    
    async def flush(self):
        """
        Flush без commit - для проверки FK constraints.
        
        Полезно для валидации данных перед commit'ом.
        
        Raises:
            RuntimeError: Если UoW не находится в контексте
        """
        if self._session is None:
            raise RuntimeError(
                "SSEUnitOfWork is not in context. "
                "Use 'async with SSEUnitOfWork(...) as uow:'"
            )
        
        await self._session.flush()
        logger.debug("SSEUnitOfWork: Session flushed")
    
    async def rollback(self):
        """
        Явный rollback текущей транзакции.
        
        Используется для отмены изменений при обработке ошибок.
        
        Raises:
            RuntimeError: Если UoW не находится в контексте
        """
        if self._session is None:
            raise RuntimeError(
                "SSEUnitOfWork is not in context. "
                "Use 'async with SSEUnitOfWork(...) as uow:'"
            )
        
        await self._session.rollback()
        logger.debug("SSEUnitOfWork: Transaction rolled back")


class TransactionScope:
    """
    Контекстный менеджер для явного управления транзакциями.
    
    Используется для группировки нескольких операций в одну транзакцию
    с автоматическим commit/rollback.
    
    Использование:
        >>> async with TransactionScope(uow) as scope:
        ...     await service.operation1()
        ...     await service.operation2()
        ...     # Автоматический commit при выходе
    
    Атрибуты:
        _uow: Unit of Work для управления транзакцией
        _auto_commit: Флаг автоматического commit при выходе
    """
    
    def __init__(self, uow: SSEUnitOfWork, auto_commit: bool = True):
        """
        Инициализация scope транзакции.
        
        Args:
            uow: Unit of Work для управления транзакцией
            auto_commit: Автоматически commit при выходе (default: True)
        """
        self._uow = uow
        self._auto_commit = auto_commit
        logger.debug(f"TransactionScope initialized (auto_commit={auto_commit})")
    
    async def __aenter__(self):
        """Вход в scope транзакции."""
        logger.debug("TransactionScope: Entering scope")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Выход из scope транзакции.
        
        При ошибке выполняется rollback.
        При успехе и auto_commit=True выполняется commit.
        """
        if exc_type is not None:
            logger.warning(
                f"TransactionScope: Exception in scope ({exc_type.__name__}), "
                f"rolling back"
            )
            await self._uow.rollback()
        elif self._auto_commit:
            logger.debug("TransactionScope: Committing transaction")
            await self._uow.commit()
        else:
            logger.debug("TransactionScope: Exiting without commit (auto_commit=False)")
    
    async def commit(self):
        """Явный commit транзакции внутри scope."""
        await self._uow.commit()
    
    async def rollback(self):
        """Явный rollback транзакции внутри scope."""
        await self._uow.rollback()
