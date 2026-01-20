"""
Multi-agent system initialization.

Registers all specialized agents in the agent router.
Supports both multi-agent and single-agent (Universal) modes.
"""
import logging
from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.coder_agent import CoderAgent
from app.agents.architect_agent import ArchitectAgent
from app.agents.debug_agent import DebugAgent
from app.agents.ask_agent import AskAgent
from app.agents.universal_agent import UniversalAgent
from app.core.config import AppConfig

logger = logging.getLogger("agent-runtime.agents")


def initialize_agents():
    """
    Initialize and register agents based on configuration.
    
    - Multi-agent mode (MULTI_AGENT_MODE=true): Registers Orchestrator + 4 specialists
    - Single-agent mode (MULTI_AGENT_MODE=false): Registers only Orchestrator + Universal
    
    This function should be called once during application startup.
    """
    # Import here to avoid circular dependency
    from app.domain.services.agent_registry import agent_router
    
    try:
        if AppConfig.MULTI_AGENT_MODE:
            # Multi-agent mode: register all specialized agents
            logger.info("Initializing multi-agent system...")
            
            agent_router.register_agent(OrchestratorAgent())
            agent_router.register_agent(CoderAgent())
            agent_router.register_agent(ArchitectAgent())
            agent_router.register_agent(DebugAgent())
            agent_router.register_agent(AskAgent())
            
            registered = agent_router.list_agents()
            logger.info(f"Successfully registered {len(registered)} agents: {[a.value for a in registered]}")
            logger.info("Multi-agent system initialized successfully")
            
        else:
            # Single-agent mode: register only Orchestrator and Universal agent
            logger.info("Initializing single-agent system (Universal mode)...")
            
            agent_router.register_agent(OrchestratorAgent())
            agent_router.register_agent(UniversalAgent())
            
            registered = agent_router.list_agents()
            logger.info(f"Successfully registered {len(registered)} agents: {[a.value for a in registered]}")
            logger.info("Single-agent system initialized successfully")
            logger.info("Orchestrator will always route to Universal agent")
        
    except Exception as e:
        logger.error(f"Failed to initialize agent system: {e}", exc_info=True)
        raise


# NOTE: initialize_agents() should be called explicitly from main.py
# to avoid circular import issues. Do not call it automatically on module import.


__all__ = [
    "OrchestratorAgent",
    "CoderAgent",
    "ArchitectAgent",
    "DebugAgent",
    "AskAgent",
    "UniversalAgent",
    "initialize_agents",
]
