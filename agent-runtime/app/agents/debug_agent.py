"""
Debug Agent - specialized in troubleshooting and error investigation.

Handles debugging, error analysis, and root cause investigation.
Cannot modify files - read-only access.
"""
import logging
from typing import AsyncGenerator, Dict, Any, TYPE_CHECKING
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.debug import DEBUG_PROMPT
from app.models.schemas import StreamChunk
from app.domain.entities.session import Session
from app.domain.services.session_management import SessionManagementService
from app.core.config import AppConfig

if TYPE_CHECKING:
    from app.domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.debug_agent")


class DebugAgent(BaseAgent):
    """
    Specialized agent for debugging and error investigation.
    
    Capabilities:
    - Analyze error messages and stack traces
    - Investigate bugs
    - Find root causes
    - Run diagnostic commands
    
    Restrictions:
    - Cannot modify files (read-only)
    - Can only analyze and suggest fixes
    """
    
    def __init__(self):
        """Initialize Debug agent"""
        super().__init__(
            agent_type=AgentType.DEBUG,
            system_prompt=DEBUG_PROMPT,
            allowed_tools=[
                "read_file",
                "list_files",
                "search_in_code",
                "execute_command",  # For running tests and diagnostics
                "attempt_completion",
                "ask_followup_question",
                "switch_mode"  # Allow switching to other agents
            ]
            # No file_restrictions needed - write_file is not in allowed_tools
        )
        logger.info("Debug agent initialized (read-only mode)")
    
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
        Process message through Debug agent.
        
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
        logger.info(f"Debug agent processing message for session {session_id}")
        
        # Get session history from domain entity
        history = session.get_history_for_llm()
        
        # Update system prompt
        if history and history[0].get("role") == "system":
            history[0]["content"] = self.system_prompt
        else:
            history.insert(0, {"role": "system", "content": self.system_prompt})
        
        # Use new StreamLLMResponseHandler (passed as parameter)
        async for chunk in stream_handler.handle(
            session_id=session_id,
            history=history,
            model=AppConfig.LLM_MODEL,
            allowed_tools=self.allowed_tools,
            correlation_id=context.get("correlation_id")
        ):
            # Handle switch_mode tool call - DON'T add tool_result to history!
            if chunk.type == "tool_call" and chunk.tool_name == "switch_mode":
                target_mode = chunk.arguments.get("mode", "orchestrator")
                reason = chunk.arguments.get("reason", "Agent requested switch")
                
                logger.info(
                    f"Debug agent requesting switch to {target_mode}: {reason}"
                )
                
                # ВАЖНО: НЕ добавляем tool_result в историю!
                # Это предотвращает ошибку "No tool call found" от OpenRouter API
                
                # Emit switch_agent chunk
                yield StreamChunk(
                    type="switch_agent",
                    content=f"Switching to {target_mode} agent",
                    metadata={
                        "target_agent": target_mode,
                        "reason": reason
                    },
                    is_final=True
                )
                return
            
            # Validate tool usage
            if chunk.type == "tool_call":
                if not self.can_use_tool(chunk.tool_name):
                    logger.warning(
                        f"Debug agent attempted to use forbidden tool: {chunk.tool_name}"
                    )
                    
                    # Special message for write_file attempts
                    if chunk.tool_name == "write_file":
                        error_msg = (
                            f"Debug agent cannot modify files. "
                            f"Debug agent can only analyze and suggest fixes. "
                            f"For code changes, please switch to Coder agent."
                        )
                    else:
                        error_msg = f"Tool '{chunk.tool_name}' is not allowed for Debug agent"
                    
                    yield StreamChunk(
                        type="error",
                        error=error_msg,
                        is_final=True
                    )
                    return
            
            yield chunk
