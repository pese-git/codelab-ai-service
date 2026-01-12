"""
Universal Agent for Single-Agent mode (baseline for POC).
Has access to all tools and a universal prompt.
"""
import logging
from typing import AsyncGenerator, Dict, Any
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.universal import UNIVERSAL_SYSTEM_PROMPT
from app.models.schemas import StreamChunk
from app.services.llm_stream_service import stream_response
from app.services.session_manager_async import AsyncSessionManager

logger = logging.getLogger("agent-runtime.universal_agent")


class UniversalAgent(BaseAgent):
    """
    Universal agent for single-agent mode.
    Used as baseline for comparison with multi-agent approach.
    
    Capabilities:
    - All code operations (create, modify, refactor)
    - Architecture design and documentation
    - Debugging and troubleshooting
    - Answering questions and explanations
    - Full access to all tools without restrictions
    """
    
    def __init__(self):
        """Initialize Universal agent with all tools and no restrictions"""
        super().__init__(
            agent_type=AgentType.UNIVERSAL,
            system_prompt=UNIVERSAL_SYSTEM_PROMPT,
            allowed_tools=[
                "read_file",
                "write_file",
                "list_files",
                "search_in_code",
                "create_directory",
                "execute_command",
                "attempt_completion",
                "ask_followup_question"
            ],
            file_restrictions=None  # No file restrictions
        )
        logger.info("Universal agent initialized with full tool access")
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session_mgr: AsyncSessionManager
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process message through Universal agent.
        
        Args:
            session_id: Session identifier
            message: User message to process
            context: Agent context with history
            session_mgr: Async session manager for session operations
            
        Yields:
            StreamChunk: Chunks for SSE streaming
        """
        logger.info(f"Universal agent processing message for session {session_id}")
        logger.debug(f"Single-agent mode: handling all tasks without delegation")
        
        # Get session history
        history = session_mgr.get_history(session_id)
        
        # Update system prompt
        if history and history[0].get("role") == "system":
            history[0]["content"] = self.system_prompt
        else:
            history.insert(0, {"role": "system", "content": self.system_prompt})
        
        # Delegate to LLM stream service with all tools
        async for chunk in stream_response(session_id, history, self.allowed_tools, session_mgr):
            # Validate tool usage (should always pass since all tools are allowed)
            if chunk.type == "tool_call":
                if not self.can_use_tool(chunk.tool_name):
                    logger.warning(
                        f"Universal agent attempted to use unknown tool: {chunk.tool_name}"
                    )
                    yield StreamChunk(
                        type="error",
                        error=f"Tool '{chunk.tool_name}' is not available",
                        is_final=True
                    )
                    return
                
                # Log tool usage for metrics
                logger.debug(f"Universal agent using tool: {chunk.tool_name}")
            
            yield chunk
