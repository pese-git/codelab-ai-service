"""
Architect Agent - specialized in system design and planning.

Handles architecture design, technical specifications, and documentation.
Can only edit markdown (.md) files.
"""
import logging
from typing import AsyncGenerator, Dict, Any, TYPE_CHECKING
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.architect import ARCHITECT_PROMPT
from app.models.schemas import StreamChunk
from app.domain.entities.session import Session
from app.domain.services.session_management import SessionManagementService
from app.core.config import AppConfig

if TYPE_CHECKING:
    from app.domain.interfaces.stream_handler import IStreamHandler

logger = logging.getLogger("agent-runtime.architect_agent")


class ArchitectAgent(BaseAgent):
    """
    Specialized agent for system design and planning.
    
    Capabilities:
    - Design system architecture
    - Create technical specifications
    - Plan implementation strategies
    - Create documentation and diagrams
    
    Restrictions:
    - Can only create/edit markdown (.md) files
    - Cannot modify code files
    """
    
    def __init__(self):
        """Initialize Architect agent"""
        super().__init__(
            agent_type=AgentType.ARCHITECT,
            system_prompt=ARCHITECT_PROMPT,
            allowed_tools=[
                "read_file",
                "write_file",  # Only for .md files
                "list_files",
                "search_in_code",
                "attempt_completion",
                "ask_followup_question",
                "create_plan"  # For creating execution plans
            ],
            file_restrictions=[r".*\.md$"]  # Only markdown files
        )
        logger.info("Architect agent initialized with .md file restrictions")
    
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
        Process message through Architect agent.
        
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
        logger.info(f"Architect agent processing message for session {session_id}")
        
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
            # Validate tool usage
            if chunk.type == "tool_call":
                if not self.can_use_tool(chunk.tool_name):
                    logger.warning(
                        f"Architect agent attempted to use forbidden tool: {chunk.tool_name}"
                    )
                    yield StreamChunk(
                        type="error",
                        error=f"Tool '{chunk.tool_name}' is not allowed for Architect agent",
                        is_final=True
                    )
                    return
                
                # Validate file editing - only .md files allowed
                if chunk.tool_name == "write_file":
                    file_path = chunk.arguments.get("path", "")
                    if not self.can_edit_file(file_path):
                        logger.warning(
                            f"Architect agent can only edit .md files, attempted: {file_path}"
                        )
                        yield StreamChunk(
                            type="error",
                            error=(
                                f"Architect agent can only create/edit markdown (.md) files. "
                                f"File '{file_path}' is not allowed. "
                                f"For code changes, please switch to Coder agent."
                            ),
                            is_final=True
                        )
                        return
            
            yield chunk
