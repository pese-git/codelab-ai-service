"""
Ask Agent - specialized in answering questions and explaining concepts.

Handles Q&A, explanations, and documentation.
Read-only access - cannot modify any files.
"""
import logging
from typing import AsyncGenerator, Dict, Any
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.ask import ASK_PROMPT
from app.models.schemas import StreamChunk
from app.services.llm_stream_service import stream_response
from app.services.session_manager import session_manager

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
        context: Dict[str, Any]
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process message through Ask agent.
        
        Args:
            session_id: Session identifier
            message: User message to process
            context: Agent context with history
            
        Yields:
            StreamChunk: Chunks for SSE streaming
        """
        logger.info(f"Ask agent processing message for session {session_id}")
        
        # Get session history
        history = session_manager.get_history(session_id)
        
        # Update system prompt
        if history and history[0].get("role") == "system":
            history[0]["content"] = self.system_prompt
        else:
            history.insert(0, {"role": "system", "content": self.system_prompt})
        
        # Delegate to LLM stream service
        async for chunk in stream_response(session_id, history):
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
            
            # Check for switch_mode tool result
            if chunk.type == "tool_result" and chunk.tool_name == "switch_mode":
                # Parse the switch mode marker
                if chunk.content and chunk.content.startswith("__SWITCH_MODE__|"):
                    parts = chunk.content.split("|")
                    if len(parts) >= 3:
                        target_mode = parts[1]
                        reason = parts[2] if len(parts) > 2 else "Agent requested switch"
                        
                        logger.info(
                            f"Ask agent requesting switch to {target_mode}: {reason}"
                        )
                        
                        # Emit switch_agent chunk
                        yield StreamChunk(
                            type="switch_agent",
                            content=f"Switching to {target_mode} agent",
                            metadata={
                                "target_agent": target_mode,
                                "reason": reason
                            }
                        )
                        return
            
            yield chunk
