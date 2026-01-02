"""
Coder Agent - specialized in writing and modifying code.

Handles all code-related tasks including creation, modification, and refactoring.
"""
import logging
from typing import AsyncGenerator, Dict, Any
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.coder import CODER_PROMPT
from app.models.schemas import StreamChunk
from app.services.llm_stream_service import stream_response
from app.services.session_manager import session_manager

logger = logging.getLogger("agent-runtime.coder_agent")


class CoderAgent(BaseAgent):
    """
    Specialized agent for code writing and modification.
    
    Capabilities:
    - Create new files and components
    - Modify existing code
    - Refactor code
    - Fix bugs
    - Run tests and commands
    """
    
    def __init__(self):
        """Initialize Coder agent"""
        super().__init__(
            agent_type=AgentType.CODER,
            system_prompt=CODER_PROMPT,
            allowed_tools=[
                "read_file",
                "write_file",
                "list_files",
                "search_in_code",
                "create_directory",
                "execute_command",
                "attempt_completion",
                "ask_followup_question"
            ]
        )
        logger.info("Coder agent initialized")
    
    async def process(
        self, 
        session_id: str,
        message: str,
        context: Dict[str, Any]
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process message through Coder agent.
        
        Args:
            session_id: Session identifier
            message: User message to process
            context: Agent context with history
            
        Yields:
            StreamChunk: Chunks for SSE streaming
        """
        logger.info(f"Coder agent processing message for session {session_id}")
        
        # Get session history
        history = session_manager.get_history(session_id)
        
        # Update system prompt
        if history and history[0].get("role") == "system":
            history[0]["content"] = self.system_prompt
        else:
            history.insert(0, {"role": "system", "content": self.system_prompt})
        
        # Delegate to LLM stream service with allowed tools
        async for chunk in stream_response(session_id, history, self.allowed_tools):
            # Validate tool usage
            if chunk.type == "tool_call":
                if not self.can_use_tool(chunk.tool_name):
                    logger.warning(
                        f"Coder agent attempted to use forbidden tool: {chunk.tool_name}"
                    )
                    yield StreamChunk(
                        type="error",
                        error=f"Tool '{chunk.tool_name}' is not allowed for Coder agent",
                        is_final=True
                    )
                    return
                
                # Validate file editing (Coder can edit any files)
                if chunk.tool_name == "write_file":
                    file_path = chunk.arguments.get("path", "")
                    if not self.can_edit_file(file_path):
                        logger.warning(
                            f"Coder agent attempted to edit restricted file: {file_path}"
                        )
                        yield StreamChunk(
                            type="error",
                            error=f"File '{file_path}' editing is restricted for Coder agent",
                            is_final=True
                        )
                        return
            
            yield chunk
