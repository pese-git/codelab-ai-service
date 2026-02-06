"""
Universal Agent for Single-Agent mode (baseline for POC).
Has access to all tools and a universal prompt.
"""
import logging
from typing import AsyncGenerator, Dict, Any, TYPE_CHECKING
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.universal import UNIVERSAL_SYSTEM_PROMPT
from app.models.schemas import StreamChunk
from app.domain.session_context.entities.conversation import Conversation as Session
from app.domain.services.session_management import SessionManagementService
from app.core.config import AppConfig

if TYPE_CHECKING:
    from app.domain.interfaces.stream_handler import IStreamHandler

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
        session: Session,
        session_service: SessionManagementService,
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process message through Universal agent.
        
        Args:
            session_id: Session identifier
            message: User message to process
            context: Agent context with history
            session: Domain entity Session with message history
            session_service: Session management service for operations
            stream_handler: Handler для LLM стриминга (интерфейс из Domain слоя)
            
        Yields:
            StreamChunk: Chunks for SSE streaming
        """
        logger.info(f"Universal agent processing message for session {session_id}")
        logger.debug(f"Single-agent mode: handling all tasks without delegation")
        
        # Get session history from domain entity
        history = session.get_history_for_llm()
        
        # Update system prompt
        if history and history[0].get("role") == "system":
            history[0]["content"] = self.system_prompt
        else:
            history.insert(0, {"role": "system", "content": self.system_prompt})
        
        # Use new StreamLLMResponseHandler (passed as parameter)
        # Universal agent has access to all tools (None = all tools)
        async for chunk in stream_handler.handle(
            session_id=session_id,
            history=history,
            model=AppConfig.LLM_MODEL,
            allowed_tools=None,  # All tools allowed
            correlation_id=context.get("correlation_id")
        ):
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
