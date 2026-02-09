"""
Architect Agent - specialized in system design and planning.

Handles architecture design, technical specifications, and documentation.
Can only edit markdown (.md) files.
"""
import logging
import json
import uuid
from typing import AsyncGenerator, Dict, Any, Optional, List, TYPE_CHECKING
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.architect import ARCHITECT_PROMPT
from app.models.schemas import StreamChunk
from app.domain.session_context.entities.conversation import Conversation as Session
from app.domain.execution_context.entities.execution_plan import ExecutionPlan
from app.domain.execution_context.entities.subtask import Subtask
from app.domain.execution_context.value_objects import PlanId, SubtaskId
from app.domain.session_context.value_objects import ConversationId
from app.domain.agent_context.value_objects import AgentId
from app.domain.session_context.services import ConversationManagementService
from app.core.config import AppConfig

if TYPE_CHECKING:
    from app.domain.interfaces.stream_handler import IStreamHandler
    from app.domain.execution_context.repositories.execution_plan_repository import ExecutionPlanRepository as PlanRepository

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
    
    def __init__(self, plan_repository: Optional["PlanRepository"] = None):
        """
        Initialize Architect agent.
        
        Args:
            plan_repository: Repository for saving plans (optional for testing)
        """
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
                "create_plan"  # Virtual tool - handled specially in agent-runtime
            ],
            file_restrictions=[r".*\.md$"]  # Only markdown files
        )
        self.plan_repository = plan_repository
        logger.info("Architect agent initialized with .md file restrictions")
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: Session,
        session_service: ConversationManagementService,
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
    
    async def create_plan(
        self,
        session_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        llm_client: Optional[Any] = None
    ) -> str:
        """
        Create execution plan for complex task.
        
        This method is called directly by OrchestratorAgent (not via LLM tool).
        Uses LLM to analyze task and decompose into subtasks.
        
        Args:
            session_id: Session ID
            task: Task description to plan
            context: Additional context (optional)
            llm_client: LLM client for task analysis (optional, uses heuristic if None)
            
        Returns:
            plan_id: ID of created and approved plan
            
        Raises:
            ValueError: If plan creation fails or validation errors
            
        Example:
            >>> architect = ArchitectAgent(plan_repository)
            >>> plan_id = await architect.create_plan(
            ...     session_id="session-123",
            ...     task="Create Flutter login form with validation",
            ...     llm_client=llm_client
            ... )
        """
        logger.info(f"Architect creating plan for task: {task[:100]}...")
        
        if not self.plan_repository:
            raise ValueError("PlanRepository not configured for ArchitectAgent")
        
        context = context or {}
        
        try:
            # 1. Analyze task with LLM to get subtasks
            analysis = await self._analyze_task_for_planning(
                session_id=session_id,
                task=task,
                context=context,
                llm_client=llm_client
            )
            
            # 2. Validate analysis
            self._validate_plan_analysis(analysis)
            
            # 3. Create ExecutionPlan entity with generated ID
            plan = ExecutionPlan(
                id=PlanId(str(uuid.uuid4())),
                conversation_id=ConversationId(session_id),
                goal=task,
                metadata={
                    "created_by": "architect",
                    "analysis": analysis.get("reasoning", ""),
                    "context": context
                }
            )
            
            # 4. Create subtasks with generated IDs first (to map indices to IDs)
            subtask_ids = [str(uuid.uuid4()) for _ in analysis["subtasks"]]
            
            # 5. Add subtasks from analysis, converting dependency indices to IDs
            for i, subtask_data in enumerate(analysis["subtasks"]):
                # Get dependency indices from LLM response
                dep_indices = subtask_data.get("dependencies", [])
                
                # Convert dependency indices to subtask IDs for ExecutionEngine
                dep_ids = []
                for dep_idx in dep_indices:
                    if isinstance(dep_idx, int) and 0 <= dep_idx < len(subtask_ids):
                        dep_ids.append(subtask_ids[dep_idx])
                    elif isinstance(dep_idx, str):
                        # Already an ID, keep as is
                        dep_ids.append(dep_idx)
                    else:
                        logger.warning(
                            f"Invalid dependency index {dep_idx} for subtask {i}, skipping"
                        )
                
                subtask = Subtask(
                    id=SubtaskId(subtask_ids[i]),
                    description=subtask_data["description"],
                    agent_id=AgentId(subtask_data["agent"]),
                    dependencies=[SubtaskId(dep_id) for dep_id in dep_ids],
                    estimated_time=subtask_data.get("estimated_time", "5 min"),
                    metadata={
                        "index": i,
                        "dependency_indices": dep_indices  # Store original indices for display
                    }
                )
                plan.add_subtask(subtask)
            
            # 5. Save plan in DRAFT status (approval happens later via PlanApprovalHandler)
            # NOTE: Plan is created in 'draft' status by default
            # User approval will be requested in Orchestrator via plan_approval_required chunk
            # After user approves, PlanApprovalHandler will call plan.approve()
            #
            # ВАЖНО: Используем commit=True для немедленной видимости в других транзакциях
            # Это критично, т.к. план будет читаться в другой транзакции при approval
            await self.plan_repository.save(plan, commit=True)
            
            logger.info(
                f"Plan {plan.id} created and committed successfully with "
                f"{len(plan.subtasks)} subtasks"
            )
            
            return plan.id
            
        except Exception as e:
            logger.error(f"Failed to create plan: {e}", exc_info=True)
            raise ValueError(f"Plan creation failed: {str(e)}") from e
    
    async def _analyze_task_for_planning(
        self,
        session_id: str,
        task: str,
        context: Dict[str, Any],
        llm_client: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze task using LLM to decompose into subtasks.
        
        Args:
            session_id: Session ID
            task: Task description
            context: Additional context
            llm_client: LLM client for analysis (optional)
            
        Returns:
            Analysis dict with subtasks structure:
            {
                "reasoning": "Why this decomposition...",
                "subtasks": [
                    {
                        "description": "Concrete action",
                        "agent": "coder|debug|ask",
                        "dependencies": [0, 1],  # indices
                        "estimated_time": "5 min"
                    }
                ]
            }
        """
        # If no LLM client provided, use heuristic fallback
        if not llm_client:
            logger.warning(
                "No LLM client provided for task analysis. "
                "Using heuristic fallback."
            )
            return self._simple_task_decomposition(task)
        
        try:
            # Construct planning prompt for LLM
            prompt = self._build_planning_prompt(task, context)
            
            # Call LLM for task analysis
            logger.info(f"Calling LLM for task decomposition: {task[:100]}...")
            
            response = await llm_client.chat_completion(
                model=AppConfig.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert software architect."},
                    {"role": "user", "content": prompt}
                ],
                tools=[],  # No tools needed for planning
                temperature=0.7  # Slightly creative for better decomposition
            )
            
            # Parse JSON response
            content = response.content.strip()
            
            # Try to extract JSON from response (handle markdown code blocks)
            if "```json" in content:
                # Extract JSON from markdown code block
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                # Extract from generic code block
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            try:
                analysis = json.loads(content)
                logger.info(
                    f"LLM task analysis successful: "
                    f"{len(analysis.get('subtasks', []))} subtasks identified"
                )
                return analysis
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse LLM response as JSON: {e}. "
                    f"Response: {content[:200]}..."
                )
                logger.warning("Falling back to heuristic decomposition")
                return self._simple_task_decomposition(task)
                
        except Exception as e:
            logger.error(
                f"Error calling LLM for task analysis: {e}",
                exc_info=True
            )
            logger.warning("Falling back to heuristic decomposition")
            return self._simple_task_decomposition(task)
    
    def _build_planning_prompt(
        self,
        task: str,
        context: Dict[str, Any]
    ) -> str:
        """Build prompt for LLM to analyze and decompose task."""
        return f"""You are an expert software architect. Analyze this task and break it down into concrete, executable subtasks.

Task: {task}

Context: {json.dumps(context, indent=2) if context else "None"}

Requirements:
1. Each subtask must be concrete and actionable
2. Assign each subtask to the appropriate agent:
   - "coder": For code changes, file creation, implementation
   - "debug": For troubleshooting, fixing bugs, investigating issues
   - "ask": For answering questions, providing explanations
3. NEVER assign subtasks to "architect" - architect only creates plans
4. Specify dependencies by index (0-based) if subtasks depend on each other
5. Provide realistic time estimates

Respond with JSON only:
{{
  "reasoning": "Brief explanation of the decomposition strategy",
  "subtasks": [
    {{
      "description": "Clear description of what to do",
      "agent": "coder",
      "dependencies": [],
      "estimated_time": "5 min"
    }}
  ]
}}

JSON response:"""
    
    def _simple_task_decomposition(self, task: str) -> Dict[str, Any]:
        """
        Simple heuristic task decomposition.
        
        This is a placeholder until full LLM integration.
        Provides basic decomposition based on keywords.
        """
        task_lower = task.lower()
        subtasks = []
        
        # Heuristic: if task mentions "create", "implement", "add"
        if any(word in task_lower for word in ["create", "implement", "add", "build"]):
            subtasks.append({
                "description": f"Implement: {task}",
                "agent": "coder",
                "dependencies": [],
                "estimated_time": "10 min"
            })
        
        # Heuristic: if task mentions "test", "verify"
        if any(word in task_lower for word in ["test", "verify", "check"]):
            subtasks.append({
                "description": f"Test and verify: {task}",
                "agent": "debug",
                "dependencies": [0] if subtasks else [],
                "estimated_time": "5 min"
            })
        
        # Default: single coder subtask
        if not subtasks:
            subtasks.append({
                "description": task,
                "agent": "coder",
                "dependencies": [],
                "estimated_time": "10 min"
            })
        
        return {
            "reasoning": "Simple heuristic decomposition (LLM integration pending)",
            "subtasks": subtasks
        }
    
    def _validate_plan_analysis(self, analysis: Dict[str, Any]) -> None:
        """
        Validate LLM analysis for plan creation.
        
        Args:
            analysis: Analysis dict from LLM
            
        Raises:
            ValueError: If validation fails
        """
        # Check required fields
        if "subtasks" not in analysis:
            raise ValueError("Analysis missing 'subtasks' field")
        
        if not analysis["subtasks"]:
            raise ValueError("Analysis has no subtasks")
        
        if not isinstance(analysis["subtasks"], list):
            raise ValueError("'subtasks' must be a list")
        
        # Validate each subtask
        for i, subtask in enumerate(analysis["subtasks"]):
            # Required fields
            if "description" not in subtask:
                raise ValueError(f"Subtask {i} missing 'description'")
            
            if "agent" not in subtask:
                raise ValueError(f"Subtask {i} missing 'agent'")
            
            # Validate agent (NOT architect)
            if subtask["agent"] == "architect":
                raise ValueError(
                    f"Subtask {i} assigned to 'architect'. "
                    "Architect cannot execute subtasks, only create plans."
                )
            
            # Validate agent type
            valid_agents = ["coder", "debug", "ask"]
            if subtask["agent"] not in valid_agents:
                raise ValueError(
                    f"Subtask {i} has invalid agent: '{subtask['agent']}'. "
                    f"Must be one of: {valid_agents}"
                )
            
            # Validate dependencies if present
            if "dependencies" in subtask:
                if not isinstance(subtask["dependencies"], list):
                    raise ValueError(
                        f"Subtask {i} dependencies must be a list"
                    )
                
                # Check dependency indices are valid
                for dep_idx in subtask["dependencies"]:
                    if not isinstance(dep_idx, int):
                        raise ValueError(
                            f"Subtask {i} dependency index must be integer"
                        )
                    if dep_idx < 0 or dep_idx >= len(analysis["subtasks"]):
                        raise ValueError(
                            f"Subtask {i} has invalid dependency index: {dep_idx}"
                        )
                    if dep_idx >= i:
                        raise ValueError(
                            f"Subtask {i} cannot depend on future subtask {dep_idx}"
                        )
        
        logger.debug(f"Plan analysis validated: {len(analysis['subtasks'])} subtasks")
