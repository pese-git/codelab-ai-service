"""
Multi-Agent Orchestrator - coordinates work between specialized agents.

Manages agent switching, context preservation, and message routing.
"""
import logging
from typing import AsyncGenerator, Optional
from app.agents.base_agent import AgentType
from app.models.schemas import StreamChunk
from app.services.agent_router import agent_router
from app.services.agent_context import agent_context_manager
from app.services.session_manager import session_manager

logger = logging.getLogger("agent-runtime.multi_agent_orchestrator")


class MultiAgentOrchestrator:
    """
    Orchestrates the multi-agent system.
    
    Responsibilities:
    - Route messages to appropriate agents
    - Handle agent switching
    - Preserve context across switches
    - Manage agent lifecycle
    """
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process message through the multi-agent system.
        
        Args:
            session_id: Session identifier
            message: User message to process
            agent_type: Explicitly requested agent type (optional)
            
        Yields:
            StreamChunk: Chunks for SSE streaming
        """
        logger.info(f"MultiAgentOrchestrator processing message for session {session_id}")
        
        # Get or create agent context
        context = agent_context_manager.get_or_create(session_id)
        
        # Handle explicit agent switch request
        if agent_type:
            if context.current_agent != agent_type:
                context.switch_agent(agent_type, "User requested agent switch")
                logger.info(
                    f"Explicit agent switch for session {session_id}: "
                    f"{context.current_agent.value} -> {agent_type.value}"
                )
                
                # Notify about the switch
                yield StreamChunk(
                    type="agent_switched",
                    content=f"Switched to {agent_type.value} agent",
                    metadata={
                        "from_agent": context.current_agent.value,
                        "to_agent": agent_type.value,
                        "reason": "User requested"
                    },
                    is_final=False
                )
        
        # If current agent is Orchestrator and we have a message, let it route
        if context.current_agent == AgentType.ORCHESTRATOR and message:
            logger.debug("Current agent is Orchestrator, will route to specialist")
            orchestrator = agent_router.get_agent(AgentType.ORCHESTRATOR)
            
            # Orchestrator will analyze and return switch_agent chunk
            async for chunk in orchestrator.process(
                session_id=session_id,
                message=message,
                context=context.model_dump()
            ):
                if chunk.type == "switch_agent":
                    # Extract target agent from metadata
                    target_agent_str = chunk.metadata.get("target_agent")
                    target_agent = AgentType(target_agent_str)
                    reason = chunk.metadata.get("reason", "Orchestrator routing")
                    
                    # Switch to target agent
                    context.switch_agent(target_agent, reason)
                    
                    logger.info(
                        f"Orchestrator routed to {target_agent.value} "
                        f"for session {session_id}"
                    )
                    
                    # Notify about the switch
                    yield StreamChunk(
                        type="agent_switched",
                        content=f"Switched to {target_agent.value} agent",
                        metadata={
                            "from_agent": AgentType.ORCHESTRATOR.value,
                            "to_agent": target_agent.value,
                            "reason": reason,
                            "confidence": chunk.metadata.get("confidence", "medium")
                        },
                        is_final=False
                    )
                    break
                else:
                    # Forward other chunks (shouldn't happen with Orchestrator)
                    yield chunk
        
        # Get current agent and process message
        current_agent = agent_router.get_agent(context.current_agent)
        
        logger.info(
            f"Processing with {context.current_agent.value} agent "
            f"for session {session_id}"
        )
        
        # Process message through current agent
        async for chunk in current_agent.process(
            session_id=session_id,
            message=message,
            context=context.model_dump()
        ):
            # Check for agent switch requests from the agent itself
            if chunk.type == "switch_agent":
                target_agent_str = chunk.metadata.get("target_agent")
                target_agent = AgentType(target_agent_str)
                reason = chunk.metadata.get("reason", "Agent requested switch")
                
                # Switch to new agent
                context.switch_agent(target_agent, reason)
                
                logger.info(
                    f"Agent switch requested: {context.current_agent.value} -> {target_agent.value}"
                )
                
                # Notify about the switch
                yield StreamChunk(
                    type="agent_switched",
                    content=f"Switched to {target_agent.value} agent",
                    metadata={
                        "from_agent": context.current_agent.value,
                        "to_agent": target_agent.value,
                        "reason": reason
                    },
                    is_final=False
                )
                
                # Continue processing with new agent
                new_agent = agent_router.get_agent(target_agent)
                async for new_chunk in new_agent.process(
                    session_id=session_id,
                    message=message,
                    context=context.model_dump()
                ):
                    yield new_chunk
                
                return
            
            # Forward chunk
            yield chunk
    
    def get_current_agent(self, session_id: str) -> Optional[AgentType]:
        """
        Get current active agent for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Current agent type or None if session doesn't exist
        """
        context = agent_context_manager.get(session_id)
        return context.current_agent if context else None
    
    def get_agent_history(self, session_id: str) -> list:
        """
        Get agent switch history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of agent switch records
        """
        context = agent_context_manager.get(session_id)
        return context.get_agent_history() if context else []
    
    def reset_session(self, session_id: str) -> None:
        """
        Reset session to initial state (Orchestrator).
        
        Args:
            session_id: Session identifier
        """
        context = agent_context_manager.get(session_id)
        if context:
            context.switch_agent(AgentType.ORCHESTRATOR, "Session reset")
            logger.info(f"Reset session {session_id} to Orchestrator agent")


# Singleton instance
multi_agent_orchestrator = MultiAgentOrchestrator()
