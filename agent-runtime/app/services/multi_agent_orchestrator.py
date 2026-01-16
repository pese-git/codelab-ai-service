"""
Multi-Agent Orchestrator - coordinates work between specialized agents.

Manages agent switching, context preservation, and message routing.
"""
import logging
from typing import AsyncGenerator, Optional, Any, TYPE_CHECKING
from app.agents.base_agent import AgentType
from app.models.schemas import StreamChunk
from app.services.agent_router import agent_router
from app.services.agent_context_async import agent_context_manager
from app.services.session_manager_async import session_manager

if TYPE_CHECKING:
    from app.services.session_manager_async import AsyncSessionManager

logger = logging.getLogger("agent-runtime.multi_agent_orchestrator")


class MultiAgentOrchestrator:
    """
    Orchestrates the multi-agent system.
    
    Responsibilities:
    - Route messages to appropriate agents
    - Handle agent switching
    - Preserve context across switches
    - Manage agent lifecycle
    """
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process message through the multi-agent system.
        
        Args:
            session_id: Session identifier
            message: User message to process
            agent_type: Explicitly requested agent type (optional)
            
        Yields:
            StreamChunk: Chunks for SSE streaming
        """
        logger.info(f"MultiAgentOrchestrator processing message for session {session_id}")
        
        # Get or create agent context (async)
        # Import here to avoid circular dependency and get initialized instance
        from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
        
        if async_ctx_mgr is None:
            raise RuntimeError("AgentContextManager not initialized")
        
        context = await async_ctx_mgr.get_or_create(session_id)
        
        # Get session manager for passing to agents
        from app.services.session_manager_async import session_manager as async_session_mgr
        
        if async_session_mgr is None:
            raise RuntimeError("SessionManager not initialized")
        
        # Check if there's an active execution plan
        if async_session_mgr.has_plan(session_id):
            plan = async_session_mgr.get_plan(session_id)
            
            # If plan requires approval but not yet approved, wait for plan_decision
            if plan.requires_approval and not plan.is_approved:
                logger.info(f"Session {session_id} has plan waiting for approval")
                # Don't process message, wait for plan_decision
                yield StreamChunk(
                    type="assistant_message",
                    content="Ожидаю подтверждения плана...",
                    is_final=True
                )
                return
            
            # Plan is approved, execute it
            if plan.is_approved and not plan.is_complete:
                logger.info(f"Session {session_id} has approved plan, continuing execution")
                async for chunk in self._execute_plan(session_id, async_session_mgr, context):
                    yield chunk
                return
        
        # Handle explicit agent switch request
        if agent_type:
            if context.current_agent != agent_type:
                context.switch_agent(agent_type, "User requested agent switch")
                logger.info(
                    f"Explicit agent switch for session {session_id}: "
                    f"{context.current_agent.value} -> {agent_type.value}"
                )
                
                # Notify about the switch
                yield StreamChunk(
                    type="agent_switched",
                    content=f"Switched to {agent_type.value} agent",
                    metadata={
                        "from_agent": context.current_agent.value,
                        "to_agent": agent_type.value,
                        "reason": "User requested"
                    },
                    is_final=False
                )
        
        # If current agent is Orchestrator and we have a message, let it route
        if context.current_agent == AgentType.ORCHESTRATOR and message:
            logger.debug("Current agent is Orchestrator, will route to specialist or create plan")
            orchestrator = agent_router.get_agent(AgentType.ORCHESTRATOR)
            
            # Orchestrator will analyze and return switch_agent chunk or create plan
            async for chunk in orchestrator.process(
                session_id=session_id,
                message=message,
                context=context.model_dump(),
                session_mgr=async_session_mgr
            ):
                if chunk.type == "plan_notification":
                    # Plan created, waiting for user confirmation
                    logger.info(f"Plan notification sent for session {session_id}, waiting for confirmation")
                    yield chunk
                    return  # Wait for user response
                elif chunk.type == "switch_agent":
                    # Extract target agent from metadata
                    target_agent_str = chunk.metadata.get("target_agent")
                    
                    # Check if this is plan execution request
                    if target_agent_str == "plan_executor":
                        logger.info(f"Starting plan execution for session {session_id}")
                        # Execute the plan
                        async for plan_chunk in self._execute_plan(session_id, async_session_mgr, context):
                            yield plan_chunk
                        return
                    
                    target_agent = AgentType(target_agent_str)
                    reason = chunk.metadata.get("reason", "Orchestrator routing")
                    
                    # Switch to target agent
                    context.switch_agent(target_agent, reason)
                    
                    logger.info(
                        f"Orchestrator routed to {target_agent.value} "
                        f"for session {session_id}"
                    )
                    
                    # Notify about the switch
                    yield StreamChunk(
                        type="agent_switched",
                        content=f"Switched to {target_agent.value} agent",
                        metadata={
                            "from_agent": AgentType.ORCHESTRATOR.value,
                            "to_agent": target_agent.value,
                            "reason": reason,
                            "confidence": chunk.metadata.get("confidence", "medium")
                        },
                        is_final=False
                    )
                    break
                else:
                    # Forward other chunks
                    yield chunk
        
        # Get current agent and process message
        current_agent = agent_router.get_agent(context.current_agent)
        
        logger.info(
            f"Processing with {context.current_agent.value} agent "
            f"for session {session_id}"
        )
        
        # Process message through current agent
        async for chunk in current_agent.process(
            session_id=session_id,
            message=message,
            context=context.model_dump(),
            session_mgr=async_session_mgr
        ):
            # Check for agent switch requests from the agent itself
            if chunk.type == "switch_agent":
                target_agent_str = chunk.metadata.get("target_agent")
                target_agent = AgentType(target_agent_str)
                reason = chunk.metadata.get("reason", "Agent requested switch")
                
                # Switch to new agent
                context.switch_agent(target_agent, reason)
                
                logger.info(
                    f"Agent switch requested: {context.current_agent.value} -> {target_agent.value}"
                )
                
                # Notify about the switch
                yield StreamChunk(
                    type="agent_switched",
                    content=f"Switched to {target_agent.value} agent",
                    metadata={
                        "from_agent": context.current_agent.value,
                        "to_agent": target_agent.value,
                        "reason": reason
                    },
                    is_final=False
                )
                
                # Continue processing with new agent
                new_agent = agent_router.get_agent(target_agent)
                async for new_chunk in new_agent.process(
                    session_id=session_id,
                    message=message,
                    context=context.model_dump(),
                    session_mgr=async_session_mgr
                ):
                    yield new_chunk
                
                return
            
            # Forward chunk
            yield chunk
    
    async def _execute_plan(
        self,
        session_id: str,
        session_mgr: "AsyncSessionManager",
        context: Any
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Execute an execution plan subtask by subtask.
        
        Args:
            session_id: Session identifier
            session_mgr: Session manager instance
            context: Agent context
            
        Yields:
            StreamChunk: Chunks from subtask execution
        """
        from app.models.schemas import SubtaskStatus
        
        plan = session_mgr.get_plan(session_id)
        if not plan:
            logger.error(f"No plan found for session {session_id}")
            yield StreamChunk(
                type="error",
                error="No execution plan found",
                is_final=True
            )
            return
        
        logger.info(
            f"Executing plan {plan.plan_id} for session {session_id}: "
            f"{len(plan.subtasks)} subtasks"
        )
        
        # Execute subtasks sequentially
        # NOTE: We execute ONE subtask at a time and exit if tool is called
        # When tool_result arrives, process_message will be called again to continue
        
        # Get next subtask
        subtask = session_mgr.get_next_subtask(session_id)
        
        if not subtask:
            # No more subtasks or all complete
            logger.info(f"No more subtasks to execute for session {session_id}")
        else:
            logger.info(
                f"Executing subtask {subtask.id}: {subtask.description} "
                f"(agent: {subtask.agent})"
            )
            
            # Notify about subtask start
            yield StreamChunk(
                type="assistant_message",
                content=f"\n\n**Subtask {plan.current_subtask_index + 1}/{len(plan.subtasks)}**: {subtask.description}",
                metadata={
                    "subtask_id": subtask.id,
                    "subtask_status": "in_progress",
                    "agent": subtask.agent
                },
                is_final=False
            )
            
            # Get appropriate agent
            try:
                agent_type = AgentType(subtask.agent)
                agent = agent_router.get_agent(agent_type)
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid agent type for subtask {subtask.id}: {subtask.agent}")
                session_mgr.mark_subtask_failed(
                    session_id,
                    subtask.id,
                    f"Invalid agent type: {subtask.agent}"
                )
                yield StreamChunk(
                    type="error",
                    error=f"Invalid agent type for subtask: {subtask.agent}",
                    is_final=False
                )
                # Continue with next subtask
                async for next_chunk in self._execute_plan(session_id, session_mgr, context):
                    yield next_chunk
                return
            
            # Switch context to appropriate agent
            context.switch_agent(agent_type, f"Executing subtask: {subtask.description}")
            
            # Execute subtask
            try:
                subtask_result = []
                tool_called = False
                
                async for chunk in agent.process(
                    session_id=session_id,
                    message=subtask.description,
                    context=context.model_dump(),
                    session_mgr=session_mgr
                ):
                    # Collect result for logging
                    if chunk.type == "assistant_message" and chunk.content:
                        subtask_result.append(chunk.content)
                    
                    # Check if tool was called
                    if chunk.type == "tool_call":
                        tool_called = True
                        logger.info(
                            f"Subtask {subtask.id} called tool {chunk.tool_name}, "
                            f"waiting for tool_result before continuing"
                        )
                    
                    # Forward chunk
                    yield chunk
                
                # Only mark as complete if no tool was called
                # If tool was called, we'll continue when tool_result arrives
                if not tool_called:
                    result_text = "".join(subtask_result) if subtask_result else "Completed"
                    session_mgr.mark_subtask_complete(
                        session_id,
                        subtask.id,
                        result_text[:500]  # Limit result size
                    )
                    
                    logger.info(f"Subtask {subtask.id} completed successfully")
                    
                    # Notify about subtask completion
                    yield StreamChunk(
                        type="assistant_message",
                        content=f"\n✓ Subtask {subtask.id} completed",
                        metadata={
                            "subtask_id": subtask.id,
                            "subtask_status": "completed"
                        },
                        is_final=False
                    )
                    
                    # Continue with next subtask immediately
                    # Recursively call _execute_plan to process next subtask
                    async for next_chunk in self._execute_plan(session_id, session_mgr, context):
                        yield next_chunk
                    return
                else:
                    # Tool called - exit and wait for tool_result
                    logger.info(
                        f"Exiting _execute_plan, waiting for tool_result for subtask {subtask.id}"
                    )
                    return
                
            except Exception as e:
                logger.error(f"Error executing subtask {subtask.id}: {e}", exc_info=True)
                session_mgr.mark_subtask_failed(
                    session_id,
                    subtask.id,
                    str(e)
                )
                
                yield StreamChunk(
                    type="error",
                    error=f"Subtask {subtask.id} failed: {str(e)}",
                    metadata={
                        "subtask_id": subtask.id,
                        "subtask_status": "failed"
                    },
                    is_final=False
                )
                
                # Continue with next subtask despite failure
                async for next_chunk in self._execute_plan(session_id, session_mgr, context):
                    yield next_chunk
                return
            
        # Plan execution complete (no more subtasks)
        logger.info(f"Plan execution complete for session {session_id}")
        
        # Count completed vs failed
        completed = sum(1 for st in plan.subtasks if st.status == SubtaskStatus.COMPLETED)
        failed = sum(1 for st in plan.subtasks if st.status == SubtaskStatus.FAILED)
        
        # Final summary
        yield StreamChunk(
            type="assistant_message",
            content=f"\n\n**Plan Execution Complete**\n- Total subtasks: {len(plan.subtasks)}\n- Completed: {completed}\n- Failed: {failed}",
            metadata={
                "plan_id": plan.plan_id,
                "plan_status": "complete",
                "total_subtasks": len(plan.subtasks),
                "completed": completed,
                "failed": failed
            },
            is_final=True
        )
        
        # Clear the plan
        session_mgr.clear_plan(session_id)
        
        # Reset to orchestrator
        context.switch_agent(AgentType.ORCHESTRATOR, "Plan execution complete")

    def get_current_agent(self, session_id: str) -> Optional[AgentType]:
        """
        Get current active agent for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Current agent type or None if session doesn't exist
        """
        # Import here to get initialized instance
        from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
        context = async_ctx_mgr.get(session_id) if async_ctx_mgr else None
        return context.current_agent if context else None
    
    def get_agent_history(self, session_id: str) -> list:
        """
        Get agent switch history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of agent switch records
        """
        # Import here to get initialized instance
        from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
        context = async_ctx_mgr.get(session_id) if async_ctx_mgr else None
        return context.get_agent_history() if context else []
    
    def reset_session(self, session_id: str) -> None:
        """
        Reset session to initial state (Orchestrator).
        
        Args:
            session_id: Session identifier
        """
        # Import here to get initialized instance
        from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
        context = async_ctx_mgr.get(session_id) if async_ctx_mgr else None
        if context:
            context.switch_agent(AgentType.ORCHESTRATOR, "Session reset")
            logger.info(f"Reset session {session_id} to Orchestrator agent")


# Singleton instance
multi_agent_orchestrator = MultiAgentOrchestrator()
