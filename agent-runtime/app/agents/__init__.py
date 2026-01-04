"""
Multi-agent system initialization.

Registers all specialized agents in the agent router.
"""
import logging
from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.coder_agent import CoderAgent
from app.agents.architect_agent import ArchitectAgent
from app.agents.debug_agent import DebugAgent
from app.agents.ask_agent import AskAgent
from app.services.agent_router import agent_router

logger = logging.getLogger("agent-runtime.agents")


def initialize_agents():
    """
    Initialize and register all agents in the system.
    
    This function should be called once during application startup.
    """
    logger.info("Initializing multi-agent system...")
    
    try:
        # Create and register all agents
        agent_router.register_agent(OrchestratorAgent())
        agent_router.register_agent(CoderAgent())
        agent_router.register_agent(ArchitectAgent())
        agent_router.register_agent(DebugAgent())
        agent_router.register_agent(AskAgent())
        
        # Log registered agents
        registered = agent_router.list_agents()
        logger.info(f"Successfully registered {len(registered)} agents: {[a.value for a in registered]}")
        logger.info("Multi-agent system initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize multi-agent system: {e}", exc_info=True)
        raise


# Automatically initialize agents when module is imported
initialize_agents()


__all__ = [
    "OrchestratorAgent",
    "CoderAgent",
    "ArchitectAgent",
    "DebugAgent",
    "AskAgent",
    "initialize_agents",
]
