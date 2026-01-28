"""
Реализация репозитория approval requests.

Конкретная реализация ApprovalRepository для работы с SQLAlchemy.
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ....domain.repositories.approval_repository import ApprovalRepository
from ....domain.entities.approval import PendingApprovalState
from ....core.errors import RepositoryError
from ..models import PendingApproval

logger = logging.getLogger("agent-runtime.infrastructure.approval_repository")


class ApprovalRepositoryImpl(ApprovalRepository):
    """
    Реализация репозитория approval requests для SQLAlchemy.
    
    Работает напрямую с моделью PendingApproval без mapper'а,
    так как PendingApprovalState - это простой Pydantic model.
    
    Атрибуты:
        _db: Сессия БД
    
    Пример:
        >>> repository = ApprovalRepositoryImpl(db_session)
        >>> await repository.save_pending("req-123", "tool", ...)
    """
    
    def __init__(self, db: AsyncSession):
        """
        Инициализация репозитория.
        
        Args:
            db: Сессия БД SQLAlchemy
        """
        self._db = db
    
    async def get(self, id: str) -> Optional[PendingApprovalState]:
        """
        Получить approval по ID (request_id).
        
        Args:
            id: Request ID
            
        Returns:
            PendingApprovalState если найден, None иначе
        """
        return await self.get_pending(id)
    
    async def save(self, entity: PendingApprovalState) -> None:
        """
        Сохранить approval request.
        
        Args:
            entity: Доменная сущность approval
            
        Raises:
            RepositoryError: При ошибке сохранения
        """
        await self.save_pending(
            request_id=entity.request_id,
            request_type=entity.request_type,
            subject=entity.subject,
            session_id=entity.session_id,
            details=entity.details,
            reason=entity.reason
        )
    
    async def delete(self, id: str) -> bool:
        """
        Удалить approval request.
        
        Args:
            id: Request ID
            
        Returns:
            True если удален, False если не найден
        """
        return await self.delete_pending(id)
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[PendingApprovalState]:
        """
        Получить список approval requests с пагинацией.
        
        Args:
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список approval requests
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
            
            return [self._model_to_entity(model) for model in models]
            
        except Exception as e:
            logger.error(f"Error listing approvals: {e}", exc_info=True)
            raise RepositoryError(
                operation="list",
                entity_type="PendingApproval",
                reason=str(e)
            )
    
    async def exists(self, id: str) -> bool:
        """
        Проверить существование approval request.
        
        Args:
            id: Request ID
            
        Returns:
            True если существует
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(PendingApproval)
                .where(PendingApproval.request_id == id)
            )
            count = result.scalar()
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking approval existence {id}: {e}")
            return False
    
    async def count(self) -> int:
        """
        Подсчитать общее количество approval requests.
        
        Returns:
            Количество approval requests
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(PendingApproval)
                .where(PendingApproval.status == 'pending')
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error counting approvals: {e}")
            return 0
    
    # ==================== Approval-specific methods ====================
    
    async def save_pending(
        self,
        request_id: str,
        request_type: str,
        subject: str,
        session_id: str,
        details: dict,
        reason: Optional[str] = None
    ) -> None:
        """
        Сохранить pending approval request.
        
        Args:
            request_id: Уникальный идентификатор
            request_type: Тип запроса
            subject: Предмет запроса
            session_id: ID сессии
            details: Детали запроса
            reason: Причина одобрения
            
        Raises:
            RepositoryError: При ошибке сохранения
        """
        try:
            # Проверить, существует ли уже
            result = await self._db.execute(
                select(PendingApproval).where(PendingApproval.request_id == request_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.warning(f"Pending approval already exists for request_id={request_id}")
                return
            
            # Создать новый approval
            approval = PendingApproval(
                request_id=request_id,
                request_type=request_type,
                subject=subject,
                session_id=session_id,
                details=details,
                reason=reason,
                status='pending',
                # Legacy fields для backward compatibility
                call_id=request_id if request_type == "tool" else None,
                tool_name=subject if request_type == "tool" else None,
                arguments=details.get("arguments", {}) if request_type == "tool" else None
            )
            
            self._db.add(approval)
            await self._db.flush()  # Flush changes within transaction, don't commit
            
            logger.info(
                f"Saved pending approval: "
                f"request_id={request_id}, type={request_type}, subject={subject}"
            )
            
        except Exception as e:
            logger.error(f"Error saving pending approval: {e}", exc_info=True)
            raise RepositoryError(
                operation="save_pending",
                entity_type="PendingApproval",
                reason=str(e),
                details={"request_id": request_id}
            )
    
    async def get_pending(self, request_id: str) -> Optional[PendingApprovalState]:
        """
        Получить pending approval по request_id.
        
        Args:
            request_id: ID запроса
            
        Returns:
            PendingApprovalState если найден, None иначе
        """
        try:
            result = await self._db.execute(
                select(PendingApproval).where(
                    PendingApproval.request_id == request_id,
                    PendingApproval.status == 'pending'
                )
            )
            model = result.scalar_one_or_none()
            
            if not model:
                logger.debug(f"Pending approval not found: {request_id}")
                return None
            
            return self._model_to_entity(model)
            
        except Exception as e:
            logger.error(f"Error getting pending approval {request_id}: {e}", exc_info=True)
            raise RepositoryError(
                operation="get_pending",
                entity_type="PendingApproval",
                reason=str(e),
                details={"request_id": request_id}
            )
    
    async def get_all_pending(
        self,
        session_id: str,
        request_type: Optional[str] = None
    ) -> List[PendingApprovalState]:
        """
        Получить все pending approvals для сессии.
        
        Args:
            session_id: ID сессии
            request_type: Опциональный фильтр по типу
            
        Returns:
            Список pending approvals
        """
        try:
            query = select(PendingApproval).where(
                PendingApproval.session_id == session_id,
                PendingApproval.status == 'pending'
            )
            
            if request_type:
                query = query.where(PendingApproval.request_type == request_type)
            
            query = query.order_by(PendingApproval.created_at.asc())
            
            result = await self._db.execute(query)
            models = result.scalars().all()
            
            return [self._model_to_entity(model) for model in models]
            
        except Exception as e:
            logger.error(f"Error getting all pending approvals: {e}", exc_info=True)
            raise RepositoryError(
                operation="get_all_pending",
                entity_type="PendingApproval",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    async def update_status(
        self,
        request_id: str,
        status: str,
        decision_at: datetime,
        decision_reason: Optional[str] = None
    ) -> bool:
        """
        Обновить статус approval request.
        
        ВАЖНО: Эта операция делает commit для немедленного сохранения изменений,
        так как статус approval должен быть обновлен атомарно и сразу.
        Это соответствует поведению старой реализации (DatabaseService.delete_pending_approval).
        
        Args:
            request_id: ID запроса
            status: Новый статус
            decision_at: Время решения
            decision_reason: Причина отклонения
            
        Returns:
            True если обновлено, False если не найдено
        """
        try:
            logger.info(f"[DEBUG] ApprovalRepositoryImpl.update_status() called: request_id={request_id}, status={status}")
            
            result = await self._db.execute(
                select(PendingApproval).where(PendingApproval.request_id == request_id)
            )
            approval = result.scalar_one_or_none()
            
            if not approval:
                logger.warning(f"[DEBUG] Pending approval not found for update: {request_id}")
                return False
            
            logger.info(f"[DEBUG] Found approval in DB: request_id={request_id}, current_status={approval.status}")
            
            approval.status = status
            approval.decision_at = decision_at
            if decision_reason:
                approval.decision_reason = decision_reason
            
            logger.info(f"[DEBUG] Before commit: approval.status={approval.status}")
            # КРИТИЧНО: Делаем commit для немедленного сохранения (как в старой реализации)
            await self._db.commit()
            logger.info(f"[DEBUG] After commit: approval.status={approval.status} - CHANGES COMMITTED!")
            logger.info(f"Updated approval status: {request_id} -> {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating approval status: {e}", exc_info=True)
            raise RepositoryError(
                operation="update_status",
                entity_type="PendingApproval",
                reason=str(e),
                details={"request_id": request_id}
            )
    
    async def delete_pending(self, request_id: str) -> bool:
        """
        Удалить pending approval request.
        
        Args:
            request_id: ID запроса
            
        Returns:
            True если удален, False если не найден
        """
        try:
            result = await self._db.execute(
                select(PendingApproval).where(PendingApproval.request_id == request_id)
            )
            approval = result.scalar_one_or_none()
            
            if not approval:
                logger.warning(f"Pending approval not found for deletion: {request_id}")
                return False
            
            await self._db.delete(approval)
            await self._db.flush()  # Flush changes within transaction, don't commit
            logger.info(f"Deleted pending approval: {request_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting pending approval: {e}", exc_info=True)
            raise RepositoryError(
                operation="delete_pending",
                entity_type="PendingApproval",
                reason=str(e),
                details={"request_id": request_id}
            )
    
    async def count_pending(self, session_id: str) -> int:
        """
        Подсчитать количество pending approvals для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Количество pending approvals
        """
        try:
            result = await self._db.execute(
                select(func.count())
                .select_from(PendingApproval)
                .where(
                    PendingApproval.session_id == session_id,
                    PendingApproval.status == 'pending'
                )
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error counting pending approvals: {e}")
            return 0
    
    # ==================== Helper methods ====================
    
    def _model_to_entity(self, model: PendingApproval) -> PendingApprovalState:
        """
        Преобразовать DB модель в доменную сущность.
        
        Args:
            model: DB модель
            
        Returns:
            Доменная сущность
        """
        return PendingApprovalState(
            request_id=model.request_id,
            request_type=model.request_type,
            subject=model.subject,
            session_id=model.session_id,
            details=model.details,
            reason=model.reason,
            created_at=model.created_at,
            status=model.status
        )
