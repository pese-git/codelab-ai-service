"""
Orchestrator Agent - main coordinator for multi-agent system.

Analyzes user requests using LLM and routes them to appropriate specialized agents.
Integrated with Planning System for complex task handling with FSM state management.
"""
import json
import logging
from typing import AsyncGenerator, Dict, Any, TYPE_CHECKING, Optional
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.orchestrator import ORCHESTRATOR_PROMPT
from app.models.schemas import StreamChunk
from app.infrastructure.llm.llm_client import LLMProxyClient
from app.core.config import AppConfig
from app.domain.services.task_classifier import TaskClassifier
from app.domain.services.fsm_orchestrator import FSMOrchestrator
from app.domain.entities.fsm_state import FSMState, FSMEvent

if TYPE_CHECKING:
    from app.domain.session_context.entities.conversation import Conversation as Session
    from app.domain.session_context.services import ConversationManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler
    from app.agents.architect_agent import ArchitectAgent
    from app.application.coordinators.execution_coordinator import ExecutionCoordinator

logger = logging.getLogger("agent-runtime.orchestrator_agent")


# Classification prompt for LLM
CLASSIFICATION_PROMPT = """Classify the task strictly.

Definitions:

A task is ATOMIC only if ALL conditions are met:
- Single clear step
- Can be completed by ONE agent
- Does NOT require studying or exploring an existing project
- Does NOT involve building an application or system
- Does NOT require architectural or design decisions
- Does NOT involve multiple components or files

If ANY condition is false, the task is NON-ATOMIC.

Routing rules:
- NON-ATOMIC tasks MUST be routed to "plan" (Architect)
- ATOMIC tasks may be routed to "code", "debug", or "explain"

Respond with JSON ONLY:

{{
  "is_atomic": true | false,
  "agent": "code | plan | debug | explain",
  "confidence": "high | medium | low",
  "reason": "short explanation"
}}

Task: {user_message}
"""

class OrchestratorAgent(BaseAgent):
    """
    Main coordinator agent that analyzes requests using LLM and routes to specialists.
    
    Uses Planning System components:
    - TaskClassifier: For accurate task classification (atomic vs complex)
    - FSMOrchestrator: For state management throughout task lifecycle
    
    Supports both atomic tasks (direct execution) and complex tasks (planning phase).
    """
    
    def __init__(
        self,
        task_classifier: Optional[TaskClassifier] = None,
        fsm_orchestrator: Optional[FSMOrchestrator] = None,
        architect_agent: Optional["ArchitectAgent"] = None,
        execution_coordinator: Optional["ExecutionCoordinator"] = None,
        approval_manager: Optional[Any] = None
    ):
        """
        Initialize Orchestrator agent with Planning System integration.
        
        Args:
            task_classifier: Optional TaskClassifier instance for dependency injection.
                           If not provided, creates a new instance.
            fsm_orchestrator: Optional FSMOrchestrator instance for state management.
                            If not provided, creates a new instance.
            architect_agent: Optional ArchitectAgent for plan creation (Option 2).
                           Required for complex task handling.
            execution_coordinator: Optional ExecutionCoordinator for plan execution (Option 2).
                                 Required for complex task handling.
            approval_manager: Optional ApprovalManager for plan approvals.
                            Required for user approval flow.
        """
        super().__init__(
            agent_type=AgentType.ORCHESTRATOR,
            system_prompt=ORCHESTRATOR_PROMPT,
            allowed_tools=[
                "read_file",
                "list_files",
                "search_in_code"
            ]
        )
        
        # Initialize Planning System components
        self.task_classifier = task_classifier or TaskClassifier()
        self.fsm_orchestrator = fsm_orchestrator or FSMOrchestrator()
        
        # Option 2: Plan coordination components
        self.architect_agent = architect_agent
        self.execution_coordinator = execution_coordinator
        self.approval_manager = approval_manager
        
        logger.info(
            "Orchestrator agent initialized with Planning System "
            "(TaskClassifier + FSMOrchestrator) "
            f"and Option 2 coordination (architect={'yes' if architect_agent else 'no'}, "
            f"executor={'yes' if execution_coordinator else 'no'}, "
            f"approval={'yes' if approval_manager else 'no'})"
        )
    
    def set_planning_dependencies(
        self,
        architect_agent: "ArchitectAgent",
        execution_coordinator: "ExecutionCoordinator",
        approval_manager: Optional[Any] = None
    ) -> None:
        """
        Set planning dependencies for Option 2 support.
        
        This method allows injecting dependencies after agent creation,
        enabling proper dependency injection without circular dependencies.
        
        Args:
            architect_agent: ArchitectAgent instance for plan creation
            execution_coordinator: ExecutionCoordinator for plan execution
            approval_manager: Optional ApprovalManager for plan approvals
        """
        self.architect_agent = architect_agent
        self.execution_coordinator = execution_coordinator
        if approval_manager is not None:
            self.approval_manager = approval_manager
        logger.info(
            "Planning dependencies set for OrchestratorAgent "
            f"(Option 2 support enabled, approval_manager={'yes' if approval_manager else 'no'})"
        )
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: "Session",
        session_service: "ConversationManagementService",
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process request with FSM state management and task classification.
        
        Flow:
        1. FSM: IDLE -> CLASSIFY (on RECEIVE_MESSAGE)
        2. Classify task (atomic vs complex)
        3. FSM: CLASSIFY -> EXECUTION (atomic) or PLAN_REQUIRED (complex)
        4. Route to appropriate agent
        
        Args:
            session_id: Session identifier
            message: User message to analyze
            context: Agent context with history
            session: Domain entity Session (not used by orchestrator)
            session_service: Session management service (not used by orchestrator)
            stream_handler: Handler для LLM стриминга (интерфейс из Domain слоя)
            
        Yields:
            StreamChunk: Switch agent chunk with routing decision
        """
        logger.info(f"Orchestrator processing request for session {session_id}")
        if message:
            logger.debug(f"Message: {message[:100]}...")
        else:
            logger.debug(f"Message: None (continuing after tool_result)")
        
        # Get current FSM state
        current_state = await self.fsm_orchestrator.get_current_state(session_id)
        logger.debug(f"Current FSM state for session {session_id}: {current_state.value}")
        
        # Reset FSM if in terminal state or non-IDLE states that shouldn't process new messages
        # This allows processing new messages in the same session
        if current_state in [FSMState.COMPLETED, FSMState.ERROR_HANDLING, FSMState.EXECUTION, FSMState.PLAN_REVIEW, FSMState.PLAN_EXECUTION]:
            logger.info(
                f"Resetting FSM from {current_state.value} to IDLE for new message "
                f"in session {session_id}"
            )
            if current_state == FSMState.COMPLETED:
                await self.fsm_orchestrator.transition(
                    session_id=session_id,
                    event=FSMEvent.RESET,
                    metadata={"reason": "new_message"}
                )
            elif current_state == FSMState.PLAN_REVIEW:
                # User sent new message instead of approving - treat as rejection
                await self.fsm_orchestrator.transition(
                    session_id=session_id,
                    event=FSMEvent.PLAN_REJECTED,
                    metadata={"reason": "new_message_received"}
                )
                await self.fsm_orchestrator.reset(session_id)
            else:
                # For EXECUTION, ERROR_HANDLING, PLAN_EXECUTION - reset directly
                await self.fsm_orchestrator.reset(session_id)
            
            current_state = FSMState.IDLE
        
        # FSM Transition: IDLE -> CLASSIFY
        if current_state == FSMState.IDLE:
            await self.fsm_orchestrator.transition(
                session_id=session_id,
                event=FSMEvent.RECEIVE_MESSAGE,
                metadata={"message": message}
            )
            logger.info(f"FSM transition: IDLE -> CLASSIFY for session {session_id}")
        
        # Check if only Universal agent is available (single-agent mode)
        from app.domain.services.agent_registry import agent_router
        available_agents = agent_router.list_agents()
        
        # If only Orchestrator and Universal are registered, route to Universal
        if AgentType.UNIVERSAL in available_agents and len(available_agents) == 2:
            logger.info("Single-agent mode detected, routing to Universal agent")
            target_agent = AgentType.UNIVERSAL
            classification_info = {
                "agent": "universal",
                "confidence": "high",
                "is_atomic": True,
                "reason": "Single-agent mode: only Universal agent available"
            }
            
            # FSM: CLASSIFY -> EXECUTION (treat as atomic)
            await self.fsm_orchestrator.transition(
                session_id=session_id,
                event=FSMEvent.IS_ATOMIC_TRUE,
                metadata=classification_info
            )
        else:
            # Multi-agent mode: classify the task using Planning System
            target_agent, classification_info = await self._classify_with_planning_system(message)
            
            # FSM Transition based on classification
            is_atomic = classification_info.get("is_atomic", True)
            
            if is_atomic:
                # FSM: CLASSIFY -> EXECUTION
                await self.fsm_orchestrator.transition(
                    session_id=session_id,
                    event=FSMEvent.IS_ATOMIC_TRUE,
                    metadata=classification_info
                )
                logger.info(
                    f"FSM transition: CLASSIFY -> EXECUTION (atomic task) "
                    f"for session {session_id}"
                )
            else:
                # FSM: CLASSIFY -> PLAN_REQUIRED
                await self.fsm_orchestrator.transition(
                    session_id=session_id,
                    event=FSMEvent.IS_ATOMIC_FALSE,
                    metadata=classification_info
                )
                logger.info(
                    f"FSM transition: CLASSIFY -> PLAN_REQUIRED (complex task) "
                    f"for session {session_id}"
                )
                
                # FSM: PLAN_REQUIRED -> ARCHITECT_PLANNING
                await self.fsm_orchestrator.transition(
                    session_id=session_id,
                    event=FSMEvent.ROUTE_TO_ARCHITECT,
                    metadata={"target_agent": target_agent.value}
                )
                logger.info(
                    f"FSM transition: PLAN_REQUIRED -> ARCHITECT_PLANNING "
                    f"for session {session_id}"
                )
                
                # Option 2: Coordinate plan creation and execution
                if self.architect_agent and self.execution_coordinator:
                    logger.info(
                        f"Option 2: Coordinating plan execution for session {session_id}"
                    )
                    async for chunk in self._coordinate_plan_execution(
                        session_id=session_id,
                        message=message,
                        context=context,
                        session=session,
                        session_service=session_service,
                        stream_handler=stream_handler
                    ):
                        yield chunk
                    return
        
        # Get final FSM state after transitions
        final_state = await self.fsm_orchestrator.get_current_state(session_id)
        
        logger.info(
            f"Orchestrator routing to {target_agent.value} agent "
            f"for session {session_id} "
            f"(FSM state: {final_state.value}, "
            f"confidence: {classification_info.get('confidence', 'unknown')}, "
            f"is_atomic: {classification_info.get('is_atomic', 'unknown')})"
        )
        
        # Send switch_agent chunk
        yield StreamChunk(
            type="switch_agent",
            content=f"Routing to {target_agent.value} agent",
            metadata={
                "target_agent": target_agent.value,
                "reason": classification_info.get("reason", f"Task classified as {target_agent.value}"),
                "confidence": classification_info.get("confidence", "medium"),
                "is_atomic": classification_info.get("is_atomic", True),
                "fsm_state": final_state.value,
                "classification_method": "planning_system"
            },
            is_final=True
        )
    
    async def _classify_with_planning_system(
        self,
        message: str
    ) -> tuple[AgentType, Dict[str, Any]]:
        """
        Classify task using Planning System's TaskClassifier.
        
        This replaces the old classify_task_with_llm() method with a more robust
        implementation from the Planning System that includes:
        - Proper atomic vs complex task detection
        - Automatic routing of complex tasks to planning phase
        - Built-in fallback strategy
        
        Args:
            message: User message to classify
            
        Returns:
            Tuple of (AgentType, classification_info dict)
        """
        try:
            # Use Planning System's TaskClassifier
            classification = await self.task_classifier.classify(message)
            
            # Map agent string to AgentType
            agent_mapping = {
                "code": AgentType.CODER,
                "plan": AgentType.ARCHITECT,
                "debug": AgentType.DEBUG,
                "explain": AgentType.ASK,
            }
            
            target_agent = agent_mapping.get(
                classification.agent,
                AgentType.CODER
            )
            
            logger.info(
                f"Planning System classified task: "
                f"is_atomic={classification.is_atomic}, "
                f"agent={classification.agent}, "
                f"confidence={classification.confidence}"
            )
            
            # Convert to dict for metadata
            classification_info = classification.to_dict()
            
            return target_agent, classification_info
            
        except Exception as e:
            logger.error(
                f"Error in Planning System classification: {e}",
                exc_info=True
            )
            logger.warning("Falling back to keyword-based classification")
            
            # Fallback to simple keyword matching
            target_agent = self._fallback_classify(message)
            return target_agent, {
                "agent": target_agent.value,
                "confidence": "low",
                "is_atomic": True,  # Assume atomic for fallback
                "reason": f"Fallback classification due to error: {str(e)}"
            }
    
    def _fallback_classify(self, message: str) -> AgentType:
        """
        Fallback classification using simple keyword matching.
        
        Used when LLM classification fails or for testing.
        
        Args:
            message: User message to classify
            
        Returns:
            AgentType: Type of agent that should handle this task
        """
        message_lower = message.lower()
        
        # Simple keyword matching as fallback
        if any(kw in message_lower for kw in ["create", "write", "implement", "fix", "code", "refactor", "modify"]):
            return AgentType.CODER
        elif any(kw in message_lower for kw in ["design", "architecture", "plan", "spec", "blueprint"]):
            return AgentType.ARCHITECT
        elif any(kw in message_lower for kw in ["debug", "error", "bug", "problem", "why", "investigate", "crash"]):
            return AgentType.DEBUG
        elif any(kw in message_lower for kw in ["explain", "what is", "how does", "help", "understand"]):
            return AgentType.ASK
        else:
            # Default to Coder
            return AgentType.CODER
    
    def classify_task(self, message: str) -> AgentType:
        """
        Synchronous classification for testing purposes.
        
        Uses fallback keyword matching.
        For production, use _classify_with_planning_system() instead.
        
        Args:
            message: User message to classify
            
        Returns:
            AgentType: Type of agent that should handle this task
        """
        return self._fallback_classify(message)
    
    # Legacy method kept for backward compatibility
    async def classify_task_with_llm(self, message: str) -> tuple[AgentType, Dict[str, Any]]:
        """
        Legacy method - redirects to Planning System classifier.
        
        Kept for backward compatibility. New code should use
        _classify_with_planning_system() directly.
        
        Args:
            message: User message to classify
            
        Returns:
            Tuple of (AgentType, classification_info dict)
        """
        logger.warning(
            "classify_task_with_llm() is deprecated. "
            "Use _classify_with_planning_system() instead."
        )
        return await self._classify_with_planning_system(message)
    
    async def _coordinate_plan_execution(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: "Session",
        session_service: "ConversationManagementService",
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Coordinate plan creation and execution for complex tasks (Option 2).
        
        Flow:
        1. PLAN_REQUIRED → ARCHITECT_PLANNING: Request Architect to create plan
        2. ARCHITECT_PLANNING → PLAN_REVIEW: Show plan to user
        3. PLAN_REVIEW → PLAN_EXECUTION: Execute approved plan
        4. PLAN_EXECUTION → COMPLETED: Present results
        
        Args:
            session_id: Session ID
            message: User message (task description)
            context: Agent context
            session: Domain Session entity
            session_service: Session management service
            stream_handler: Stream handler
            
        Yields:
            StreamChunk: Progress updates and results
        """
        logger.info(
            f"Starting plan coordination for session {session_id}"
        )
        
        # Check if Option 2 components are available
        if not self.architect_agent:
            logger.error("ArchitectAgent not configured for plan coordination")
            yield StreamChunk(
                type="error",
                error="Plan coordination not available: ArchitectAgent not configured",
                is_final=True
            )
            return
        
        if not self.execution_coordinator:
            logger.error("ExecutionCoordinator not configured for plan coordination")
            yield StreamChunk(
                type="error",
                error="Plan coordination not available: ExecutionCoordinator not configured",
                is_final=True
            )
            return
        
        try:
            # Notify user about routing to Architect for planning
            # NOTE: Using 'status' type instead of 'switch_agent' to avoid MessageProcessor
            # intercepting and switching agents. Orchestrator coordinates the plan internally.
            yield StreamChunk(
                type="status",
                content="🔄 Routing to Architect agent for planning...",
                metadata={
                    "routing_to": "architect",
                    "reason": "Complex task requires planning phase",
                    "fsm_state": FSMState.ARCHITECT_PLANNING.value
                }
            )
            
            # Step 1: Create plan through Architect
            yield StreamChunk(
                type="status",
                content="🏗️ Architect is creating execution plan...",
                metadata={"fsm_state": FSMState.ARCHITECT_PLANNING.value}
            )
            
            # Get LLM client from stream_handler if available
            llm_client = None
            if hasattr(stream_handler, '_llm_client'):
                llm_client = stream_handler._llm_client
                logger.debug("Using LLM client from stream_handler for plan creation")
            else:
                logger.warning("No LLM client available, using heuristic decomposition")
            
            plan_id = await self.architect_agent.create_plan(
                session_id=session_id,
                task=message,
                context=context,
                llm_client=llm_client
            )
            
            logger.info(f"Plan {plan_id} created by Architect")
            
            # FSM: ARCHITECT_PLANNING → PLAN_REVIEW
            await self.fsm_orchestrator.transition(
                session_id=session_id,
                event=FSMEvent.PLAN_CREATED,
                metadata={"plan_id": plan_id}
            )
            
            # Step 2: Show plan to user for review
            plan_summary = await self.execution_coordinator.get_plan_summary(plan_id)
            
            yield StreamChunk(
                type="plan_created",
                content=self._format_plan_for_user(plan_summary),
                metadata={
                    "plan_id": plan_id,
                    "fsm_state": FSMState.PLAN_REVIEW.value,
                    "plan_summary": plan_summary,
                    "requires_approval": True
                }
            )
            
            # Step 3: Request user approval for plan
            logger.info(f"Plan {plan_id} requesting user approval")
            
            # Get approval_manager from stream_handler (uses DI, not singleton)
            approval_manager = None
            if hasattr(stream_handler, '_approval_manager'):
                approval_manager = stream_handler._approval_manager
                logger.debug("Using ApprovalManager from stream_handler (DI)")
            elif self.approval_manager:
                approval_manager = self.approval_manager
                logger.warning("Using singleton ApprovalManager (deprecated)")
            
            # Create approval request if ApprovalManager available
            if approval_manager:
                approval_request_id = f"plan-approval-{plan_id}"
                
                # Add to pending approvals
                await approval_manager.add_pending(
                    request_id=approval_request_id,
                    request_type="plan",
                    subject=plan_summary['goal'][:100],  # Truncate for subject
                    session_id=session_id,
                    details={
                        "plan_id": plan_id,
                        "goal": plan_summary['goal'],
                        "subtasks_count": plan_summary['subtasks_count'],
                        "total_estimated_time": plan_summary['total_estimated_time'],
                        "subtasks": plan_summary['subtasks']
                    },
                    reason="Complex plan requires user approval before execution"
                )
                
                logger.info(
                    f"Plan approval request created: {approval_request_id}, "
                    f"awaiting user decision"
                )
                
                # Yield approval required chunk
                chunk = StreamChunk(
                    type="plan_approval_required",
                    content="Plan requires your approval before execution",
                    approval_request_id=approval_request_id,
                    plan_id=plan_id,
                    plan_summary=plan_summary,
                    metadata={
                        "fsm_state": FSMState.PLAN_REVIEW.value
                    },
                    is_final=True  # Orchestrator завершил обработку, ждем approval
                )
                logger.info(
                    f"Sending plan_approval_required chunk: "
                    f"approval_request_id={approval_request_id}, "
                    f"plan_id={plan_id}, "
                    f"plan_summary keys={list(plan_summary.keys())}"
                )
                logger.debug(f"Full chunk data: {chunk.model_dump()}")
                yield chunk
                
                # NOTE: Execution will continue when user sends approval decision
                # via POST /sessions/{session_id}/plan-decision endpoint
                # For now, we return here and wait for user decision
                logger.info(
                    f"Waiting for user approval for plan {plan_id}. "
                    f"Execution paused in PLAN_REVIEW state."
                )
                return
            else:
                # No ApprovalManager - auto-approve for backward compatibility
                logger.warning(
                    "ApprovalManager not configured, auto-approving plan "
                    "(backward compatibility mode)"
                )
                
                # FSM: PLAN_REVIEW → PLAN_EXECUTION
                await self.fsm_orchestrator.transition(
                    session_id=session_id,
                    event=FSMEvent.PLAN_APPROVED,
                    metadata={"approved_by": "auto"}
                )
            
            # Step 4: Execute plan
            yield StreamChunk(
                type="status",
                content=f"⚙️ Executing plan with {plan_summary['subtasks_count']} subtasks...",
                metadata={"fsm_state": FSMState.PLAN_EXECUTION.value}
            )
            
            # ИСПРАВЛЕНИЕ: Пересылать все chunks от ExecutionCoordinator
            execution_result_metadata = None
            async for chunk in self.execution_coordinator.execute_plan(
                plan_id=plan_id,
                session_id=session_id,
                session_service=session_service,
                stream_handler=stream_handler
            ):
                # Пересылать chunk дальше (включая tool_call!)
                yield chunk
                
                # Сохранить metadata из финального chunk
                if chunk.type == "execution_completed" and chunk.metadata:
                    execution_result_metadata = chunk.metadata
            
            # Логировать результат
            if execution_result_metadata:
                logger.info(
                    f"Plan {plan_id} execution completed: "
                    f"{execution_result_metadata.get('completed_subtasks')}/"
                    f"{execution_result_metadata.get('total_subtasks')} successful"
                )
                
                # FSM: PLAN_EXECUTION → COMPLETED
                await self.fsm_orchestrator.transition(
                    session_id=session_id,
                    event=FSMEvent.PLAN_EXECUTION_COMPLETED,
                    metadata={"execution_result": execution_result_metadata}
                )
            
        except Exception as e:
            logger.error(
                f"Plan coordination error for session {session_id}: {e}",
                exc_info=True
            )
            
            # FSM: * → ERROR_HANDLING
            try:
                current_state = await self.fsm_orchestrator.get_current_state(session_id)
                if current_state == FSMState.PLAN_EXECUTION:
                    await self.fsm_orchestrator.transition(
                        session_id=session_id,
                        event=FSMEvent.PLAN_EXECUTION_FAILED,
                        metadata={"error": str(e)}
                    )
                elif current_state == FSMState.ARCHITECT_PLANNING:
                    await self.fsm_orchestrator.transition(
                        session_id=session_id,
                        event=FSMEvent.PLANNING_FAILED,
                        metadata={"error": str(e)}
                    )
            except Exception as fsm_error:
                logger.error(f"FSM transition error: {fsm_error}")
            
            yield StreamChunk(
                type="error",
                error=f"Plan coordination failed: {str(e)}",
                metadata={"fsm_state": FSMState.ERROR_HANDLING.value},
                is_final=True
            )
    
    def _format_plan_for_user(self, plan_summary: Dict[str, Any]) -> str:
        """
        Format plan summary for user presentation.
        
        Args:
            plan_summary: Plan summary dict from ExecutionCoordinator
            
        Returns:
            Formatted string for display
        """
        lines = [
            f"📋 **Execution Plan Created**",
            f"",
            f"**Goal:** {plan_summary['goal']}",
            f"**Subtasks:** {plan_summary['subtasks_count']}",
            f"**Estimated Time:** {plan_summary['total_estimated_time']}",
            f"",
            f"**Subtasks:**"
        ]
        
        for i, subtask in enumerate(plan_summary['subtasks'], 1):
            # Use dependency_indices from metadata if available, otherwise empty
            dep_indices = subtask.get('metadata', {}).get('dependency_indices', [])
            if dep_indices:
                # Convert 0-based indices to 1-based for display
                deps = f" (depends on: {', '.join(str(d + 1) for d in dep_indices)})"
            else:
                deps = ""
            
            lines.append(
                f"{i}. [{subtask['agent'].upper()}] {subtask['description']} "
                f"({subtask['estimated_time']}){deps}"
            )
        
        lines.append("")
        lines.append("✅ Plan ready for execution. Awaiting approval...")
        
        return "\n".join(lines)
    
