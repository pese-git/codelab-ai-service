"""
Ask Agent - specialized in answering questions and explaining concepts.

Handles Q&A, explanations, and documentation.
Read-only access - cannot modify any files.
"""
import logging
from typing import AsyncGenerator, Dict, Any, TYPE_CHECKING
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.ask import ASK_PROMPT
from app.models.schemas import StreamChunk
from app.domain.entities.session import Session
from app.domain.services.session_management import SessionManagementService
from app.core.config import AppConfig

if TYPE_CHECKING:
    from app.domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.ask_agent")


class AskAgent(BaseAgent):
    """
    Specialized agent for Q&A and explanations.
    
    Capabilities:
    - Answer technical questions
    - Explain programming concepts
    - Provide documentation
    - Give recommendations
    
    Restrictions:
    - Read-only access
    - Cannot modify any files
    - Cannot execute commands
    """
    
    def __init__(self):
        """Initialize Ask agent"""
        super().__init__(
            agent_type=AgentType.ASK,
            system_prompt=ASK_PROMPT,
            allowed_tools=[
                "read_file",
                "search_in_code",
                "list_files",
                "attempt_completion",
                "switch_mode"  # Allow switching to other agents
            ]
            # Minimal tools - only for reading and context
        )
        logger.info("Ask agent initialized (read-only mode)")
    
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
        Process message through Ask agent.
        
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
        logger.info(f"Ask agent processing message for session {session_id}")
        
        # Get session history from domain entity
        history = session.get_history_for_llm()
        
        # DEBUG: Log history to see what we're getting
        logger.info(f"Ask agent got history with {len(history)} messages")
        for i, msg in enumerate(history):
            logger.debug(f"  Message {i}: role={msg.get('role')}, content={msg.get('content', '')[:50]}...")
        
        # Update system prompt
        if history and history[0].get("role") == "system":
            history[0]["content"] = self.system_prompt
        else:
            history.insert(0, {"role": "system", "content": self.system_prompt})
        
        logger.debug(f"After adding system prompt, history has {len(history)} messages")
        
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
                    f"Ask agent requesting switch to {target_mode}: {reason}"
                )
                
                # ВАЖНО: НЕ добавляем tool_result в историю!
                # Это предотвращает ошибку "No tool call found" от OpenRouter API
                # Просто отправляем switch_agent chunk
                
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
                        f"Ask agent attempted to use forbidden tool: {chunk.tool_name}"
                    )
                    
                    # Provide helpful error messages
                    if chunk.tool_name == "write_file":
                        error_msg = (
                            f"Ask agent cannot modify files. "
                            f"Ask agent can only read and explain. "
                            f"For code changes, please switch to Coder agent."
                        )
                    elif chunk.tool_name == "execute_command":
                        error_msg = (
                            f"Ask agent cannot execute commands. "
                            f"For running commands, please switch to Coder or Debug agent."
                        )
                    else:
                        error_msg = f"Tool '{chunk.tool_name}' is not allowed for Ask agent"
                    
                    yield StreamChunk(
                        type="error",
                        error=error_msg,
                        is_final=True
                    )
                    return
            
            yield chunk
