"""
Agent router for multi-agent system.

Manages registration and routing between different agents.
"""
from typing import Dict, List
import logging

from app.agents.base_agent import BaseAgent, AgentType

logger = logging.getLogger("agent-runtime.agent_router")


class AgentRouter:
    """
    Routes requests to appropriate agents.
    
    Responsibilities:
    - Register agents
    - Retrieve agents by type
    - Manage agent lifecycle
    """
    
    def __init__(self):
        """Initialize the agent router"""
        self._agents: Dict[AgentType, BaseAgent] = {}
        logger.info("AgentRouter initialized")
    
    def register_agent(self, agent: BaseAgent) -> None:
        """
        Register an agent in the router.
        
        Args:
            agent: Agent instance to register
            
        Raises:
            ValueError: If agent type is already registered
        """
        if agent.agent_type in self._agents:
            logger.warning(
                f"Agent {agent.agent_type.value} is already registered, "
                "replacing with new instance"
            )
        
        self._agents[agent.agent_type] = agent
        logger.info(
            f"Registered agent: {agent.agent_type.value} "
            f"({agent.__class__.__name__})"
        )
    
    def get_agent(self, agent_type: AgentType) -> BaseAgent:
        """
        Get an agent by type.
        
        Args:
            agent_type: Type of agent to retrieve
            
        Returns:
            Agent instance
            
        Raises:
            ValueError: If agent type is not registered
        """
        agent = self._agents.get(agent_type)
        
        if not agent:
            available = ", ".join(a.value for a in self._agents.keys())
            raise ValueError(
                f"Agent '{agent_type.value}' not found. "
                f"Available agents: {available}"
            )
        
        return agent
    
    def has_agent(self, agent_type: AgentType) -> bool:
        """
        Check if an agent type is registered.
        
        Args:
            agent_type: Type of agent to check
            
        Returns:
            True if agent is registered
        """
        return agent_type in self._agents
    
    def list_agents(self) -> List[AgentType]:
        """
        Get list of all registered agent types.
        
        Returns:
            List of agent types
        """
        return list(self._agents.keys())
    
    def get_agent_count(self) -> int:
        """
        Get number of registered agents.
        
        Returns:
            Number of agents
        """
        return len(self._agents)
    
    def unregister_agent(self, agent_type: AgentType) -> bool:
        """
        Unregister an agent.
        
        Args:
            agent_type: Type of agent to unregister
            
        Returns:
            True if agent was unregistered, False if not found
        """
        if agent_type in self._agents:
            del self._agents[agent_type]
            logger.info(f"Unregistered agent: {agent_type.value}")
            return True
        
        logger.warning(
            f"Attempted to unregister non-existent agent: {agent_type.value}"
        )
        return False
    
    def clear_all(self) -> None:
        """Clear all registered agents"""
        count = len(self._agents)
        self._agents.clear()
        logger.info(f"Cleared all {count} registered agents")
    
    def get_agent_info(self, agent_type: AgentType) -> Dict[str, any]:
        """
        Get information about an agent.
        
        Args:
            agent_type: Type of agent
            
        Returns:
            Dictionary with agent information
            
        Raises:
            ValueError: If agent not found
        """
        agent = self.get_agent(agent_type)
        
        return {
            "type": agent.agent_type.value,
            "class": agent.__class__.__name__,
            "allowed_tools": agent.get_allowed_tools(),
            "has_file_restrictions": bool(agent.file_restrictions),
            "file_restriction_count": len(agent.file_restrictions)
        }
    
    def get_all_agents_info(self) -> List[Dict[str, any]]:
        """
        Get information about all registered agents.
        
        Returns:
            List of agent information dictionaries
        """
        return [
            self.get_agent_info(agent_type)
            for agent_type in self.list_agents()
        ]


# Singleton instance
agent_router = AgentRouter()
