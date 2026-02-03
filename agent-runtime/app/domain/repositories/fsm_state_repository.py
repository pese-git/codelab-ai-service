"""
Repository interface for FSM state persistence.

Defines contract for storing and retrieving FSM states.
"""
from abc import abstractmethod
from typing import Optional, Dict, Any

from .base import Repository
from ..entities.fsm_state import FSMState


class FSMStateRepository(Repository):
    """
    Repository interface for FSM state persistence.
    
    Provides methods for storing and retrieving FSM states from persistent storage.
    This allows FSM state to survive across HTTP requests and service restarts.
    
    Methods:
        save_state: Save or update FSM state for a session
        get_state: Get current FSM state for a session
        delete_state: Delete FSM state for a session
        get_metadata: Get FSM metadata for a session
        update_metadata: Update FSM metadata for a session
    """
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def get_state(self, session_id: str) -> Optional[FSMState]:
        """
        Get current FSM state for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            FSMState if found, None otherwise (defaults to IDLE)
        """
        pass
    
    @abstractmethod
    async def delete_state(self, session_id: str) -> bool:
        """
        Delete FSM state for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    async def get_metadata(self, session_id: str) -> Dict[str, Any]:
        """
        Get FSM metadata for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Metadata dictionary (empty dict if not found)
        """
        pass
    
    @abstractmethod
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
        pass
