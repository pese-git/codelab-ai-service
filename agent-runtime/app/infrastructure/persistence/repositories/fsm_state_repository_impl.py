"""
Implementation of FSM state repository using SQLAlchemy.

Provides persistent storage for FSM states in PostgreSQL.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ....domain.repositories.fsm_state_repository import FSMStateRepository
from ....domain.entities.fsm_state import FSMState
from ....core.errors import RepositoryError
from ..models.fsm_state import FSMStateModel

logger = logging.getLogger("agent-runtime.infrastructure.fsm_state_repository")


class FSMStateRepositoryImpl(FSMStateRepository):
    """
    SQLAlchemy implementation of FSM state repository.
    
    Stores FSM states in PostgreSQL for persistence across requests.
    
    Attributes:
        _db: SQLAlchemy async session
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize repository.
        
        Args:
            db: SQLAlchemy async session
        """
        self._db = db
    
    async def save_state(
        self,
        session_id: str,
        current_state: FSMState,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save or update FSM state for a session.
        
        Args:
            session_id: Session identifier
            current_state: Current FSM state
            metadata: Optional metadata dictionary
            
        Raises:
            RepositoryError: If save operation fails
        """
        try:
            # Check if state already exists
            result = await self._db.execute(
                select(FSMStateModel).where(FSMStateModel.session_id == session_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing state
                existing.current_state = current_state.value
                if metadata is not None:
                    # Merge metadata
                    existing_meta = existing.context_metadata or {}
                    existing_meta.update(metadata)
                    existing.context_metadata = existing_meta
                existing.updated_at = datetime.now(timezone.utc)
                
                logger.debug(
                    f"Updated FSM state for session {session_id}: {current_state.value}"
                )
            else:
                # Create new state
                fsm_state = FSMStateModel(
                    session_id=session_id,
                    current_state=current_state.value,
                    context_metadata=metadata or {}
                )
                self._db.add(fsm_state)
                
                logger.debug(
                    f"Created FSM state for session {session_id}: {current_state.value}"
                )
            
            await self._db.flush()
            
        except Exception as e:
            logger.error(f"Error saving FSM state: {e}", exc_info=True)
            raise RepositoryError(
                operation="save_state",
                entity_type="FSMState",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    async def get_state(self, session_id: str) -> Optional[FSMState]:
        """
        Get current FSM state for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            FSMState if found, None otherwise (caller should default to IDLE)
        """
        try:
            result = await self._db.execute(
                select(FSMStateModel).where(FSMStateModel.session_id == session_id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                logger.debug(f"No FSM state found for session {session_id}")
                return None
            
            # Convert string to FSMState enum
            try:
                state = FSMState(model.current_state)
                logger.debug(f"Retrieved FSM state for session {session_id}: {state.value}")
                return state
            except ValueError:
                logger.warning(
                    f"Invalid FSM state value in DB: {model.current_state}, "
                    f"defaulting to IDLE"
                )
                return FSMState.IDLE
            
        except Exception as e:
            logger.error(f"Error getting FSM state: {e}", exc_info=True)
            raise RepositoryError(
                operation="get_state",
                entity_type="FSMState",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    async def delete_state(self, session_id: str) -> bool:
        """
        Delete FSM state for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        try:
            result = await self._db.execute(
                select(FSMStateModel).where(FSMStateModel.session_id == session_id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                logger.debug(f"No FSM state to delete for session {session_id}")
                return False
            
            await self._db.delete(model)
            await self._db.flush()
            
            logger.debug(f"Deleted FSM state for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting FSM state: {e}", exc_info=True)
            raise RepositoryError(
                operation="delete_state",
                entity_type="FSMState",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    async def get_metadata(self, session_id: str) -> Dict[str, Any]:
        """
        Get FSM metadata for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Metadata dictionary (empty dict if not found)
        """
        try:
            result = await self._db.execute(
                select(FSMStateModel).where(FSMStateModel.session_id == session_id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                return {}
            
            return model.context_metadata or {}
            
        except Exception as e:
            logger.error(f"Error getting FSM metadata: {e}", exc_info=True)
            return {}
    
    async def update_metadata(
        self,
        session_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Update FSM metadata for a session.
        
        Args:
            session_id: Session identifier
            metadata: Metadata dictionary to merge with existing
            
        Returns:
            True if updated, False if session not found
        """
        try:
            result = await self._db.execute(
                select(FSMStateModel).where(FSMStateModel.session_id == session_id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                logger.warning(f"No FSM state found to update metadata for session {session_id}")
                return False
            
            # Merge metadata
            existing_meta = model.context_metadata or {}
            existing_meta.update(metadata)
            model.context_metadata = existing_meta
            model.updated_at = datetime.now(timezone.utc)
            
            await self._db.flush()
            
            logger.debug(f"Updated FSM metadata for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating FSM metadata: {e}", exc_info=True)
            raise RepositoryError(
                operation="update_metadata",
                entity_type="FSMState",
                reason=str(e),
                details={"session_id": session_id}
            )
    
    # Base Repository methods (required by interface)
    
    async def get(self, id: str) -> Optional[FSMState]:
        """Get FSM state by session ID"""
        return await self.get_state(id)
    
    async def save(self, entity: Any) -> None:
        """Not used - use save_state instead"""
        raise NotImplementedError("Use save_state() instead")
    
    async def delete(self, id: str) -> bool:
        """Delete FSM state by session ID"""
        return await self.delete_state(id)
    
    async def list(self, limit: int = 100, offset: int = 0):
        """Not implemented for FSM states"""
        return []
    
    async def exists(self, id: str) -> bool:
        """Check if FSM state exists for session"""
        state = await self.get_state(id)
        return state is not None
    
    async def count(self) -> int:
        """Not implemented for FSM states"""
        return 0
