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
from app.infrastructure.llm.client import llm_proxy_client
from app.core.config import AppConfig
from app.domain.services.task_classifier import TaskClassifier
from app.domain.services.fsm_orchestrator import FSMOrchestrator
from app.domain.entities.fsm_state import FSMState, FSMEvent

if TYPE_CHECKING:
    from app.domain.entities.session import Session
    from app.domain.services.session_management import SessionManagementService
    from app.domain.interfaces.stream_handler import IStreamHandler

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
        fsm_orchestrator: Optional[FSMOrchestrator] = None
    ):
        """
        Initialize Orchestrator agent with Planning System integration.
        
        Args:
            task_classifier: Optional TaskClassifier instance for dependency injection.
                           If not provided, creates a new instance.
            fsm_orchestrator: Optional FSMOrchestrator instance for state management.
                            If not provided, creates a new instance.
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
        
        logger.info(
            "Orchestrator agent initialized with Planning System "
            "(TaskClassifier + FSMOrchestrator)"
        )
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: "Session",
        session_service: "SessionManagementService",
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
        current_state = self.fsm_orchestrator.get_current_state(session_id)
        logger.debug(f"Current FSM state for session {session_id}: {current_state.value}")
        
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
        
        # Get final FSM state after transitions
        final_state = self.fsm_orchestrator.get_current_state(session_id)
        
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
