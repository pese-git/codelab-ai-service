"""
Реализация репозитория HITL.

Конкретная реализация HITLRepository для работы с SQLAlchemy.
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ....domain.repositories.hitl_repository import HITLRepository
from ....domain.entities.hitl import HITLPendingState, HITLAuditLog
from ....core.errors import RepositoryError
from ..models import PendingApproval
from ....services.database import DatabaseService

logger = logging.getLogger("agent-runtime.infrastructure.hitl_repository")


class HITLRepositoryImpl(HITLRepository):
    """
    Реализация репозитория HITL для SQLAlchemy.
    
    Использует DatabaseService для высокоуровневых операций
    и прямые SQL запросы для специфичных операций.
    
    Атрибуты:
        _db: Сессия БД
        _db_service: Сервис БД для высокоуровневых операций
    
    Пример:
        >>> repository = HITLRepositoryImpl(db_session, db_service)
        >>> pending = await repository.find_by_session_id("session-1")
    """
    
    def __init__(self, db: AsyncSession, db_service: DatabaseService):
        """
        Инициализация репозитория.
        
        Args:
            db: Сессия БД SQLAlchemy
            db_service: Сервис БД для высокоуровневых операций
        """
        self._db = db
        self._db_service = db_service
    
    async def get(self, id: str) -> Optional[HITLPendingState]:
        """
        Получить pending approval по call_id.
        
        Args:
            id: Call ID (используется как primary key)
            
        Returns:
            HITLPendingState если найден, None иначе
        """
        try:
            result = await self._db.execute(
                select(PendingApproval).where(
                    PendingApproval.call_id == id,
                    PendingApproval.status == 'pending'
                )
            )
            model = result.scalar_one_or_none()
            
            if not model:
                return None
            
            return HITLPendingState(
                call_id=model.call_id,
                tool_name=model.tool_name,
                arguments=model.arguments,
                reason=model.reason,
                created_at=model.created_at,
                timeout_seconds=300  # Default timeout
            )
            
        except Exception as e:
            logger.error(f"Error getting pending approval {id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="get",
                entity_type="HITLPendingState",
                reason=str(e),
                details={"call_id": id}
            )
    
    async def save(self, entity: HITLPendingState) -> None:
        """
        Сохранить pending approval.
        
        Note: Используйте save_pending() для создания новых approvals.
        Этот метод для совместимости с базовым Repository.
        
        Args:
            entity: HITLPendingState для сохранения
            
        Raises:
            RepositoryError: При ошибке сохранения
        """
        try:
            # Проверить существование
            result = await self._db.execute(
                select(PendingApproval).where(
                    PendingApproval.call_id == entity.call_id
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Обновить существующий
                existing.tool_name = entity.tool_name
                existing.arguments = entity.arguments
                existing.reason = entity.reason
                existing.status = 'pending'
            else:
                # Создать новый
                model = PendingApproval(
                    session_id="",  # Будет установлен в save_pending
                    call_id=entity.call_id,
                    tool_name=entity.tool_name,
                    arguments=entity.arguments,
                    reason=entity.reason,
                    status='pending'
                )
                self._db.add(model)
            
            await self._db.flush()
            logger.debug(f"Saved pending approval {entity.call_id}")
            
        except Exception as e:
            logger.error(f"Error saving pending approval {entity.call_id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="save",
                entity_type="HITLPendingState",
                reason=str(e),
                details={"call_id": entity.call_id}
            )
    
    async def delete(self, id: str) -> bool:
        """
        Удалить pending approval по call_id.
        
        Args:
            id: Call ID
            
        Returns:
            True если удален, False если не найден
        """
        return await self.delete_by_call_id(id)
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[HITLPendingState]:
        """
        Получить список pending approvals с пагинацией.
        
        Args:
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список pending approvals
        """
        try:
            result = await self._db.execute(
                select(PendingApproval)
                .where(PendingApproval.status == 'pending')
                .order_by(PendingApproval.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            models = result.scalars().all()
            
            return [
                HITLPendingState(
                    call_id=model.call_id,
                    tool_name=model.tool_name,
                    arguments=model.arguments,
                    reason=model.reason,
                    created_at=model.created_at,
                    timeout_seconds=300
                )
                for model in models
            ]
            
        except Exception as e:
            logger.error(f"Error listing pending approvals: {e}", exc_info=True)
            raise RepositoryError(
                operation="list",
                entity_type="HITLPendingState",
                reason=str(e)
            )
    
    async def exists(self, id: str) -> bool:
        """
        Проверить существование pending approval.
        
        Args:
            id: Call ID
            
        Returns:
            True если существует
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(PendingApproval)
                .where(
                    PendingApproval.call_id == id,
                    PendingApproval.status == 'pending'
                )
            )
            count = result.scalar()
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking pending approval existence {id}: {e}")
            return False
    
    async def count(self) -> int:
        """
        Подсчитать общее количество pending approvals.
        
        Returns:
            Количество pending approvals
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(PendingApproval)
                .where(PendingApproval.status == 'pending')
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error counting pending approvals: {e}")
            return 0
    
    async def find_by_session_id(
        self,
        session_id: str
    ) -> List[HITLPendingState]:
        """
        Найти все pending approvals для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Список pending approvals
        """
        try:
            pending_approvals = await self._db_service.get_pending_approvals(
                self._db, session_id
            )
            
            return [
                HITLPendingState(
                    call_id=approval['call_id'],
                    tool_name=approval['tool_name'],
                    arguments=approval['arguments'],
                    reason=approval.get('reason'),
                    created_at=approval['created_at'],
                    timeout_seconds=300
                )
                for approval in pending_approvals
            ]
            
        except Exception as e:
            logger.error(
                f"Error finding pending approvals for session {session_id}: {e}",
                exc_info=True
            )
            raise RepositoryError(
                operation="find_by_session_id",
                entity_type="HITLPendingState",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    async def find_by_call_id(
        self,
        session_id: str,
        call_id: str
    ) -> Optional[HITLPendingState]:
        """
        Найти pending approval по call_id.
        
        Args:
            session_id: ID сессии
            call_id: ID tool call
            
        Returns:
            HITLPendingState если найден, None иначе
        """
        try:
            result = await self._db.execute(
                select(PendingApproval).where(
                    PendingApproval.call_id == call_id,
                    PendingApproval.session_id == session_id,
                    PendingApproval.status == 'pending'
                )
            )
            model = result.scalar_one_or_none()
            
            if not model:
                logger.debug(f"No pending approval found for call_id={call_id}")
                return None
            
            return HITLPendingState(
                call_id=model.call_id,
                tool_name=model.tool_name,
                arguments=model.arguments,
                reason=model.reason,
                created_at=model.created_at,
                timeout_seconds=300
            )
            
        except Exception as e:
            logger.error(
                f"Error finding pending approval {call_id}: {e}",
                exc_info=True
            )
            raise RepositoryError(
                operation="find_by_call_id",
                entity_type="HITLPendingState",
                reason=str(e),
                details={"session_id": session_id, "call_id": call_id}
            )
    
    async def save_pending(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        arguments: dict,
        reason: Optional[str] = None
    ) -> HITLPendingState:
        """
        Сохранить pending approval.
        
        Args:
            session_id: ID сессии
            call_id: ID tool call
            tool_name: Имя инструмента
            arguments: Аргументы инструмента
            reason: Причина требования одобрения
            
        Returns:
            Созданный HITLPendingState
        """
        try:
            await self._db_service.save_pending_approval(
                db=self._db,
                session_id=session_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
                reason=reason
            )
            
            # Создать и вернуть entity
            pending_state = HITLPendingState(
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
                reason=reason,
                timeout_seconds=300
            )
            
            logger.info(
                f"Saved pending approval: session={session_id}, "
                f"call_id={call_id}, tool={tool_name}"
            )
            
            return pending_state
            
        except Exception as e:
            logger.error(
                f"Error saving pending approval {call_id}: {e}",
                exc_info=True
            )
            raise RepositoryError(
                operation="save_pending",
                entity_type="HITLPendingState",
                reason=str(e),
                details={
                    "session_id": session_id,
                    "call_id": call_id,
                    "tool_name": tool_name
                }
            )
    
    async def delete_by_call_id(self, call_id: str) -> bool:
        """
        Удалить pending approval по call_id.
        
        Args:
            call_id: ID tool call
            
        Returns:
            True если удален, False если не найден
        """
        try:
            result = await self._db_service.delete_pending_approval(
                self._db, call_id
            )
            
            if result:
                logger.info(f"Deleted pending approval: call_id={call_id}")
            
            return result
            
        except Exception as e:
            logger.error(
                f"Error deleting pending approval {call_id}: {e}",
                exc_info=True
            )
            raise RepositoryError(
                operation="delete_by_call_id",
                entity_type="HITLPendingState",
                reason=str(e),
                details={"call_id": call_id}
            )
    
    async def cleanup_expired(
        self,
        session_id: str,
        timeout_seconds: int = 300
    ) -> int:
        """
        Очистить expired pending approvals для сессии.
        
        Args:
            session_id: ID сессии
            timeout_seconds: Timeout в секундах
            
        Returns:
            Количество удаленных approvals
        """
        try:
            # Получить все pending для сессии
            pending_states = await self.find_by_session_id(session_id)
            
            # Найти expired
            expired_count = 0
            for pending_state in pending_states:
                if pending_state.is_expired():
                    await self.delete_by_call_id(pending_state.call_id)
                    expired_count += 1
            
            if expired_count > 0:
                logger.info(
                    f"Cleaned up {expired_count} expired approvals "
                    f"for session {session_id}"
                )
            
            return expired_count
            
        except Exception as e:
            logger.error(
                f"Error cleaning up expired approvals for {session_id}: {e}",
                exc_info=True
            )
            raise RepositoryError(
                operation="cleanup_expired",
                entity_type="HITLPendingState",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    async def save_audit_log(self, audit_log: HITLAuditLog) -> None:
        """
        Сохранить audit log entry.
        
        Note: Текущая реализация - no-op, так как audit logs
        отслеживаются через event-driven architecture.
        
        Args:
            audit_log: Audit log entry
        """
        logger.debug(
            f"Audit log for {audit_log.call_id}: {audit_log.decision.value} "
            f"(tracked via events)"
        )
        # TODO: Implement persistent audit trail if required
