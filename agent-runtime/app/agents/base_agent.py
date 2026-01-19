"""
Base agent class for multi-agent system.

Defines the interface and common functionality for all specialized agents.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator, TYPE_CHECKING
from enum import Enum
import re
import logging

if TYPE_CHECKING:
    from app.services.session_manager_async import AsyncSessionManager
    from app.domain.entities.session import Session
    from app.domain.services.session_management import SessionManagementService

logger = logging.getLogger("agent-runtime.base_agent")


class AgentType(str, Enum):
    """Types of available agents in the system"""
    ORCHESTRATOR = "orchestrator"
    CODER = "coder"
    ARCHITECT = "architect"
    DEBUG = "debug"
    ASK = "ask"
    UNIVERSAL = "universal"


class BaseAgent(ABC):
    """
    Base class for all agents in the multi-agent system.
    
    Each agent has:
    - A unique type identifier
    - A system prompt defining its role and capabilities
    - A list of allowed tools it can use
    - Optional file restrictions for write operations
    """
    
    def __init__(
        self, 
        agent_type: AgentType,
        system_prompt: str,
        allowed_tools: List[str],
        file_restrictions: Optional[List[str]] = None
    ):
        """
        Initialize base agent.
        
        Args:
            agent_type: Type of the agent
            system_prompt: System prompt defining agent's role
            allowed_tools: List of tool names this agent can use
            file_restrictions: Optional regex patterns for file access restrictions
        """
        self.agent_type = agent_type
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools
        self.file_restrictions = file_restrictions or []
        
        logger.info(
            f"Initialized {agent_type.value} agent with "
            f"{len(allowed_tools)} tools and "
            f"{len(self.file_restrictions)} file restrictions"
        )
    
    @abstractmethod
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: "Session",
        session_service: "SessionManagementService"
    ) -> AsyncGenerator:
        """
        Process a message through this agent.
        
        Args:
            session_id: Session identifier
            message: User message to process
            context: Agent context with history and metadata
            session: Domain entity Session with message history
            session_service: Session management service for operations
            
        Yields:
            StreamChunk: Chunks for SSE streaming
        """
        pass
    
    def can_use_tool(self, tool_name: str) -> bool:
        """
        Check if this agent is allowed to use a specific tool.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if agent can use this tool
        """
        return tool_name in self.allowed_tools
    
    def can_edit_file(self, file_path: str) -> bool:
        """
        Check if this agent is allowed to edit a specific file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if agent can edit this file
        """
        # If no restrictions, allow all files
        if not self.file_restrictions:
            return True
        
        # Check if file matches any allowed pattern
        for pattern in self.file_restrictions:
            if re.match(pattern, file_path):
                return True
        
        return False
    
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent.
        
        Returns:
            System prompt string
        """
        return self.system_prompt
    
    def get_allowed_tools(self) -> List[str]:
        """
        Get list of tools this agent can use.
        
        Returns:
            List of tool names
        """
        return self.allowed_tools.copy()
    
    def __repr__(self) -> str:
        """String representation of the agent"""
        return (
            f"<{self.__class__.__name__} "
            f"type={self.agent_type.value} "
            f"tools={len(self.allowed_tools)}>"
        )
