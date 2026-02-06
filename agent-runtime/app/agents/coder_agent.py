"""
Coder Agent - specialized in writing and modifying code.

Handles all code-related tasks including creation, modification, and refactoring.
"""
import logging
from typing import AsyncGenerator, Dict, Any, TYPE_CHECKING
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.coder import CODER_PROMPT
from app.models.schemas import StreamChunk
from app.domain.session_context.entities.conversation import Conversation as Session
from app.domain.services.session_management import SessionManagementService
from app.core.config import AppConfig

if TYPE_CHECKING:
    from app.domain.interfaces.stream_handler import IStreamHandler

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
        context: Dict[str, Any],
        session: Session,
        session_service: SessionManagementService,
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process message through Coder agent.
        
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
        logger.info(f"Coder agent processing message for session {session_id}")
        
        # Get session history from domain entity
        history = session.get_history_for_llm()
        
        # Prepare system prompt with context
        system_prompt = self.system_prompt
        
        # Add subtask context if in subtask execution mode
        if context.get("execution_mode") == "subtask":
            subtask_context = self._format_subtask_context(context)
            system_prompt += subtask_context
            logger.info(f"Added subtask context for subtask {context.get('subtask_id')}")
        
        # Add system prompt at the beginning
        if history and history[0].get("role") == "system":
            history[0]["content"] = system_prompt
        else:
            history.insert(0, {"role": "system", "content": system_prompt})
        
        # Use new StreamLLMResponseHandler (passed as parameter)
        async for chunk in stream_handler.handle(
            session_id=session_id,
            history=history,
            model=AppConfig.LLM_MODEL,
            allowed_tools=self.allowed_tools,
            correlation_id=context.get("correlation_id")
        ):
            # Validate tool usage (domain logic)
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
    
    def _format_subtask_context(self, context: Dict[str, Any]) -> str:
        """
        Format subtask context for system prompt.
        
        Args:
            context: Agent context with subtask information
            
        Returns:
            Formatted context string to append to system prompt
        """
        subtask_context = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 SUBTASK EXECUTION MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are executing a subtask as part of a larger plan.

Plan Goal: {context.get('plan_goal', 'N/A')}
Subtask ID: {context.get('subtask_id', 'N/A')}

Dependencies completed:
{self._format_dependencies(context.get('dependencies', {}))}

⚠️ CRITICAL FOR SUBTASK EXECUTION:

1. You MUST use tools (write_file, create_directory, etc.) to complete this subtask
2. The task description tells you WHAT to do
3. You must use tools to ACTUALLY DO IT
4. DO NOT just respond with text explaining what should be done
5. ACTUALLY PERFORM THE ACTIONS using the available tools

Example workflow:
- Task: "Create file main.py with hello world"
- Action: Call write_file(path="main.py", content="print('Hello, World!')")
- NOT: "I will create a file main.py with hello world content"

When you finish all required actions, simply stop.
The orchestrator will handle task completion automatically.
"""
        return subtask_context
    
    def _format_dependencies(self, dependencies: Dict[str, Any]) -> str:
        """
        Format dependency results for system prompt.
        
        Args:
            dependencies: Dictionary of dependency results
            
        Returns:
            Formatted dependency information
        """
        if not dependencies:
            return "None"
        
        lines = []
        for dep_id, dep_data in dependencies.items():
            lines.append(f"- {dep_data.get('description', 'N/A')}")
            result = dep_data.get('result', '')
            if result:
                # Truncate long results
                result_preview = result[:200] + "..." if len(result) > 200 else result
                lines.append(f"  Result: {result_preview}")
        
        return "\n".join(lines) if lines else "None"
