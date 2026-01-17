"""
Architect Agent - specialized in system design and planning.

Handles architecture design, technical specifications, and documentation.
Can only edit markdown (.md) files.
"""
import logging
from typing import AsyncGenerator, Dict, Any
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.architect import ARCHITECT_PROMPT
from app.models.schemas import StreamChunk
from app.services.llm_stream_service import stream_response
from app.services.session_manager_async import AsyncSessionManager

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
                "create_plan",  # For complex task planning
                "attempt_completion",
                "ask_followup_question",
                "switch_mode"  # Allow switching to other agents
                # NOTE: execute_command, create_directory are NOT allowed
                # Architect should create plans, not execute implementation tasks
            ],
            file_restrictions=[r".*\.md$"]  # Only markdown files
        )
        logger.info("Architect agent initialized with .md file restrictions and planning-only tools")
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session_mgr: AsyncSessionManager
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process message through Architect agent.
        
        Args:
            session_id: Session identifier
            message: User message to process
            context: Agent context with history
            session_mgr: Async session manager for session operations
            
        Yields:
            StreamChunk: Chunks for SSE streaming
        """
        logger.info(f"Architect agent processing message for session {session_id}")
        
        # Check if there's an approved plan - don't process, let orchestrator handle it
        if session_mgr.has_plan(session_id):
            plan = session_mgr.get_plan(session_id)
            if plan and plan.is_approved and not plan.is_complete:
                logger.info(
                    f"Architect: Plan {plan.plan_id} already approved, "
                    f"should not be processing messages. Delegating to orchestrator."
                )
                # Don't process - the orchestrator should handle plan execution
                yield StreamChunk(
                    type="assistant_message",
                    content="План уже подтвержден и выполняется...",
                    is_final=True
                )
                return
        
        # Get session history
        history = session_mgr.get_history(session_id)
        
        # Update system prompt
        if history and history[0].get("role") == "system":
            history[0]["content"] = self.system_prompt
        else:
            history.insert(0, {"role": "system", "content": self.system_prompt})
        
        # Delegate to LLM stream service with allowed tools
        async for chunk in stream_response(session_id, history, self.allowed_tools, session_mgr):
            # Handle create_plan tool call directly
            if chunk.type == "tool_call" and chunk.tool_name == "create_plan":
                logger.info(f"Architect creating execution plan for session {session_id}")

                # Execute create_plan tool locally
                from app.services.tool_registry import execute_local_tool
                from app.models.schemas import ToolCall

                tool_call = ToolCall(
                    id=chunk.call_id,
                    tool_name="create_plan",
                    arguments=chunk.arguments
                )

                result = await execute_local_tool(tool_call)

                # Check if result is a plan marker
                if result.startswith("__CREATE_PLAN__|"):
                    import json
                    import uuid
                    from app.models.schemas import ExecutionPlan, Subtask, SubtaskStatus

                    # Parse subtasks from result
                    subtasks_json = result.split("__CREATE_PLAN__|")[1]
                    subtasks_data = json.loads(subtasks_json)

                    # Create ExecutionPlan
                    subtasks = [
                        Subtask(
                            id=st.get("id", f"subtask_{i+1}"),
                            description=st["description"],
                            agent=st["agent"],
                            estimated_time=st.get("estimated_time"),
                            status=SubtaskStatus.PENDING,
                            dependencies=st.get("dependencies", [])
                        )
                        for i, st in enumerate(subtasks_data)
                    ]

                    plan = ExecutionPlan(
                        plan_id=f"plan_{uuid.uuid4().hex[:8]}",
                        session_id=session_id,
                        original_task=message,
                        subtasks=subtasks,
                        requires_approval=True,
                        is_approved=False
                    )

                    # Store plan in session manager
                    session_mgr.set_plan(session_id, plan)

                    logger.info(
                        f"Architect created execution plan with {len(subtasks)} subtasks "
                        f"for session {session_id}"
                    )

                    # Add tool result to history
                    await session_mgr.append_tool_result(
                        session_id=session_id,
                        call_id=chunk.call_id,
                        tool_name="create_plan",
                        result=f"Plan created with {len(subtasks)} subtasks"
                    )

                    # Set pending confirmation state
                    session_mgr.set_pending_plan_confirmation(session_id)

                    # Emit detailed plan notification to user
                    plan_summary = f"**План выполнения задачи:** {len(subtasks)} подзадач\n\n"
                    for i, st in enumerate(subtasks, 1):
                        plan_summary += f"{i}. **{st.description}**\n"
                        plan_summary += f"   - Агент: {st.agent}\n"
                        if st.estimated_time:
                            plan_summary += f"   - Время: {st.estimated_time}\n"
                        if st.dependencies:
                            deps = [d for d in st.dependencies if d]
                            if deps:
                                plan_summary += f"   - Зависимости: {', '.join(deps)}\n"
                        plan_summary += "\n"

                    plan_summary += (
                        "**Требуется подтверждение:**\n"
                        "Отправьте `plan_decision` с решением (approve/edit/reject)"
                    )

                    yield StreamChunk(
                        type="plan_notification",
                        content=plan_summary,
                        metadata={
                            "plan_id": plan.plan_id,
                            "subtask_count": len(subtasks),
                            "subtasks": [
                                {
                                    "id": st.id,
                                    "description": st.description,
                                    "agent": st.agent,
                                    "estimated_time": st.estimated_time,
                                    "dependencies": st.dependencies
                                }
                                for st in subtasks
                            ],
                            "requires_approval": True
                        },
                        is_final=True
                    )
                    return

            # Handle switch_mode tool call directly (don't send to IDE)
            elif chunk.type == "tool_call" and chunk.tool_name == "switch_mode":
                target_mode = chunk.arguments.get("mode", "orchestrator")
                reason = chunk.arguments.get("reason", "Agent requested switch")
                
                logger.info(
                    f"Architect agent requesting switch to {target_mode}: {reason}"
                )
                
                # Add tool result to history before switching
                await session_mgr.append_tool_result(
                    session_id=session_id,
                    call_id=chunk.call_id,
                    tool_name="switch_mode",
                    result=f"Switching to {target_mode} agent"
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
