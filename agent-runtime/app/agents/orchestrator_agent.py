"""
Orchestrator Agent - main coordinator for multi-agent system.

Analyzes user requests using LLM and routes them to appropriate specialized agents.
"""
import json
import logging
from typing import AsyncGenerator, Dict, Any, TYPE_CHECKING
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.prompts.orchestrator import ORCHESTRATOR_PROMPT
from app.models.schemas import StreamChunk
from app.services.llm_proxy_client import llm_proxy_client
from app.core.config import AppConfig

if TYPE_CHECKING:
    from app.domain.entities.session import Session
    from app.domain.services.session_management import SessionManagementService

logger = logging.getLogger("agent-runtime.orchestrator_agent")


# Classification prompt for LLM
CLASSIFICATION_PROMPT = """You are a task classifier for a multi-agent system. Analyze the user's request and determine which specialized agent should handle it.

Available agents:
1. **coder** - for writing, modifying, and refactoring code
   - Creating new files or components
   - Modifying existing code
   - Implementing features
   - Fixing bugs in code
   - Refactoring code

2. **architect** - for planning, designing, and creating technical specifications
   - Designing system architecture
   - Creating technical specifications
   - Planning implementation strategies
   - Designing data models or APIs
   - Creating documentation and diagrams

3. **debug** - for troubleshooting, investigating errors, and debugging
   - Analyzing error messages
   - Investigating bugs
   - Finding root causes
   - Troubleshooting issues
   - Analyzing logs or stack traces

4. **ask** - for answering questions, explaining concepts, and providing documentation
   - Explaining programming concepts
   - Answering technical questions
   - Providing documentation
   - Teaching or learning
   - General knowledge queries

5. **universal** - universal agent that can handle any task (used in single-agent mode)
   - All of the above capabilities combined
   - Used when only one agent is available

Analyze the user's request and respond with ONLY a JSON object in this format:
{{
  "agent": "coder|architect|debug|ask|universal",
  "confidence": "high|medium|low",
  "reasoning": "brief explanation of why this agent was chosen"
}}

User request: {user_message}

Response (JSON only):"""


class OrchestratorAgent(BaseAgent):
    """
    Main coordinator agent that analyzes requests using LLM and routes to specialists.
    
    Uses LLM-based classification for more accurate and context-aware routing.
    """
    
    def __init__(self):
        """Initialize Orchestrator agent"""
        super().__init__(
            agent_type=AgentType.ORCHESTRATOR,
            system_prompt=ORCHESTRATOR_PROMPT,
            allowed_tools=[
                "read_file",
                "list_files",
                "search_in_code"
            ]
        )
        logger.info("Orchestrator agent initialized with LLM-based classification")
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session: "Session",
        session_service: "SessionManagementService"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Analyze request using LLM and determine which agent should handle it.
        
        Args:
            session_id: Session identifier
            message: User message to analyze
            context: Agent context with history
            session: Domain entity Session (not used by orchestrator)
            session_service: Session management service (not used by orchestrator)
            
        Yields:
            StreamChunk: Switch agent chunk with routing decision
        """
        logger.info(f"Orchestrator analyzing request for session {session_id}")
        if message:
            logger.debug(f"Message: {message[:100]}...")
        else:
            logger.debug(f"Message: None (continuing after tool_result)")
        
        # Check if only Universal agent is available (single-agent mode)
        from app.services.agent_router import agent_router
        available_agents = agent_router.list_agents()
        
        # If only Orchestrator and Universal are registered, route to Universal
        if AgentType.UNIVERSAL in available_agents and len(available_agents) == 2:
            logger.info("Single-agent mode detected, routing to Universal agent")
            target_agent = AgentType.UNIVERSAL
            classification_info = {
                "agent": "universal",
                "confidence": "high",
                "reasoning": "Single-agent mode: only Universal agent available"
            }
        else:
            # Multi-agent mode: classify the task type using LLM
            target_agent, classification_info = await self.classify_task_with_llm(message)
        
        logger.info(
            f"Orchestrator routing to {target_agent.value} agent "
            f"for session {session_id} "
            f"(confidence: {classification_info.get('confidence', 'unknown')})"
        )
        
        # Send switch_agent chunk
        yield StreamChunk(
            type="switch_agent",
            content=f"Routing to {target_agent.value} agent",
            metadata={
                "target_agent": target_agent.value,
                "reason": classification_info.get("reasoning", f"Task classified as {target_agent.value}"),
                "confidence": classification_info.get("confidence", "medium"),
                "classification_method": "llm"
            },
            is_final=True
        )
    
    async def classify_task_with_llm(self, message: str) -> tuple[AgentType, Dict[str, Any]]:
        """
        Classify task type using LLM for more accurate routing.
        
        Args:
            message: User message to classify
            
        Returns:
            Tuple of (AgentType, classification_info dict)
        """
        try:
            # Prepare classification prompt
            classification_prompt = CLASSIFICATION_PROMPT.format(user_message=message)
            
            # Call LLM for classification
            logger.debug("Calling LLM for task classification")
            response = await llm_proxy_client.chat_completion(
                model=AppConfig.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a task classifier. Respond only with JSON."},
                    {"role": "user", "content": classification_prompt}
                ],
                stream=False,
                extra_params={"temperature": 0.3}  # Lower temperature for more consistent classification
            )
            
            # Extract response content
            content = response["choices"][0]["message"]["content"]
            logger.debug(f"LLM classification response: {content}")
            
            # Parse JSON response
            try:
                classification = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code block
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                    classification = json.loads(json_str)
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                    classification = json.loads(json_str)
                else:
                    raise
            
            # Extract agent type
            agent_str = classification.get("agent", "coder").lower()
            
            # Map to AgentType
            agent_mapping = {
                "coder": AgentType.CODER,
                "architect": AgentType.ARCHITECT,
                "debug": AgentType.DEBUG,
                "ask": AgentType.ASK,
                "universal": AgentType.UNIVERSAL
            }
            
            target_agent = agent_mapping.get(agent_str, AgentType.CODER)
            
            logger.info(
                f"LLM classified task as '{agent_str}' "
                f"(confidence: {classification.get('confidence', 'unknown')})"
            )
            
            return target_agent, classification
            
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}", exc_info=True)
            logger.warning("Falling back to keyword-based classification")
            
            # Fallback to simple keyword matching
            target_agent = self._fallback_classify(message)
            return target_agent, {
                "agent": target_agent.value,
                "confidence": "low",
                "reasoning": "Fallback classification due to LLM error",
                "error": str(e)
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
        For production, use classify_task_with_llm() instead.
        
        Args:
            message: User message to classify
            
        Returns:
            AgentType: Type of agent that should handle this task
        """
        return self._fallback_classify(message)
