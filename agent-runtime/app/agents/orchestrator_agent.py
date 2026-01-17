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
    from app.services.session_manager_async import AsyncSessionManager

logger = logging.getLogger("agent-runtime.orchestrator_agent")


# Classification prompt template for LLM
CLASSIFICATION_PROMPT_TEMPLATE = """You are a task classifier for a multi-agent system. Analyze the user's request and determine which specialized agent should handle it.

Available agents:
{available_agents}

IMPORTANT CLASSIFICATION RULES:
- If the task involves CREATING, ADDING, MODIFYING, WRITING, or IMPLEMENTING code/files → use "coder"
- If the task involves DESIGNING, PLANNING architecture, or creating specifications → use "architect"
- If the task involves DEBUGGING, FIXING errors, or investigating problems → use "debug"
- If the task is asking for EXPLANATION, DOCUMENTATION, or LEARNING → use "ask"

Examples:
- "Add constant to file" → coder
- "Create new component" → coder
- "Fix bug in code" → debug
- "Design system architecture" → architect
- "Explain how X works" → ask

Analyze the user's request and respond with ONLY a JSON object in this format:
{{{{
  "agent": "{agent_options}",
  "confidence": "high|medium|low",
  "reasoning": "brief explanation of why this agent was chosen"
}}}}

User request: {{user_message}}

Response (JSON only):"""

# Agent descriptions for dynamic prompt building
AGENT_DESCRIPTIONS = {
    "coder": """**coder** - for WRITING, MODIFYING, CREATING, ADDING, IMPLEMENTING code and files
   - Creating new files, components, or constants
   - Modifying existing code (add/remove/change lines)
   - Implementing features and functionality
   - Adding imports, dependencies, or configurations
   - Refactoring and code improvements
   - Running commands and tests
   Keywords: create, add, write, implement, modify, update, change, build, develop""",
    
    "architect": """**architect** - for PLANNING, DESIGNING architecture and creating specifications
   - Designing system architecture and structure
   - Creating technical specifications and documentation
   - Planning complex multi-step implementations
   - Designing data models, APIs, or system flows
   - Creating diagrams and architectural documents
   Keywords: design, plan, architecture, structure, specification, blueprint, strategy""",
    
    "debug": """**debug** - for TROUBLESHOOTING, INVESTIGATING errors and debugging issues
   - Analyzing error messages and stack traces
   - Investigating bugs and unexpected behavior
   - Finding root causes of problems
   - Troubleshooting runtime or compilation issues
   - Analyzing logs and diagnostic information
   Keywords: debug, error, bug, issue, problem, crash, exception, fail, investigate, troubleshoot""",
    
    "ask": """**ask** - for ANSWERING questions, EXPLAINING concepts, and providing information
   - Explaining programming concepts and patterns
   - Answering "what is", "how does", "why" questions
   - Providing documentation and learning resources
   - Teaching concepts without code changes
   - General knowledge and information queries
   Keywords: explain, what is, how does, why, tell me, describe, understand, learn, help me understand""",
    
    "universal": """**universal** - universal agent that can handle any task (used in single-agent mode)
   - All of the above capabilities combined
   - Used when only one agent is available"""
}


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
        logger.info("Orchestrator agent initialized with LLM-based classification and planning")
    
    async def process(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session_mgr: "AsyncSessionManager"
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Analyze request and either route to agent or create execution plan.
        
        Args:
            session_id: Session identifier
            message: User message to analyze
            context: Agent context with history
            session_mgr: Async session manager for session operations
            
        Yields:
            StreamChunk: Switch agent chunk or plan creation notification
        """
        logger.info(f"Orchestrator analyzing request for session {session_id}")
        logger.debug(f"Message: {message[:100]}...")
        
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
            
            # Send switch_agent chunk
            yield StreamChunk(
                type="switch_agent",
                content=f"Routing to {target_agent.value} agent",
                metadata={
                    "target_agent": target_agent.value,
                    "reason": classification_info.get("reasoning"),
                    "confidence": classification_info.get("confidence", "medium"),
                    "classification_method": "llm"
                },
                is_final=True
            )
            return
        
        # Multi-agent mode: Let LLM decide whether to route to Architect or route directly
        # For complex tasks, LLM should route to Architect for planning
        from app.services.llm_stream_service import stream_response
        
        # Get session history
        history = session_mgr.get_history(session_id)
        
        # Update system prompt
        if history and history[0].get("role") == "system":
            history[0]["content"] = self.system_prompt
        else:
            history.insert(0, {"role": "system", "content": self.system_prompt})
        
        # Stream LLM response - it will route to appropriate agent
        async for chunk in stream_response(session_id, history, self.allowed_tools, session_mgr):
            # Check if it's a routing decision
            if chunk.type == "assistant_message" and chunk.is_final:
                # LLM decided on routing - classify and route
                target_agent, classification_info = await self.classify_task_with_llm(message)

                logger.info(
                    f"Orchestrator routing to {target_agent.value} agent "
                    f"for session {session_id}"
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
                return

            # Forward other chunks
            yield chunk
    
    async def classify_task_with_llm(self, message: str) -> tuple[AgentType, Dict[str, Any]]:
        """
        Classify task type using LLM for more accurate routing.
        
        Args:
            message: User message to classify
            
        Returns:
            Tuple of (AgentType, classification_info dict)
        """
        try:
            # Get available agents dynamically
            from app.services.agent_router import agent_router
            available_agents = agent_router.list_agents()
            
            # Build dynamic agent list for prompt (exclude ORCHESTRATOR)
            agent_list_parts = []
            agent_names = []
            counter = 1
            
            # Map AgentType to description keys
            agent_type_to_key = {
                AgentType.CODER: "coder",
                AgentType.ARCHITECT: "architect",
                AgentType.DEBUG: "debug",
                AgentType.ASK: "ask",
                AgentType.UNIVERSAL: "universal"
            }
            
            for agent_type in available_agents:
                if agent_type == AgentType.ORCHESTRATOR:
                    continue  # Skip orchestrator itself
                
                key = agent_type_to_key.get(agent_type)
                if key and key in AGENT_DESCRIPTIONS:
                    agent_list_parts.append(f"{counter}. {AGENT_DESCRIPTIONS[key]}")
                    agent_names.append(key)
                    counter += 1
            
            # Build final prompt
            available_agents_text = "\n\n".join(agent_list_parts)
            agent_options = "|".join(agent_names)
            
            classification_prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(
                available_agents=available_agents_text,
                agent_options=agent_options,
                user_message=message
            )
            
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
            
            # Map to AgentType (only include agents that are actually available)
            from app.services.agent_router import agent_router
            available_agents = agent_router.list_agents()
            
            agent_mapping = {
                "coder": AgentType.CODER,
                "architect": AgentType.ARCHITECT,
                "debug": AgentType.DEBUG,
                "ask": AgentType.ASK,
                "universal": AgentType.UNIVERSAL
            }
            
            target_agent = agent_mapping.get(agent_str, AgentType.CODER)
            
            # Validate that target agent is registered
            if target_agent not in available_agents:
                logger.warning(
                    f"LLM suggested '{target_agent.value}' but it's not registered. "
                    f"Falling back to CODER"
                )
                target_agent = AgentType.CODER
                classification["agent"] = "coder"
                classification["reasoning"] = f"Fallback to coder (original: {agent_str} not available)"
            
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
        Supports both English and Russian keywords.
        
        Args:
            message: User message to classify
            
        Returns:
            AgentType: Type of agent that should handle this task
        """
        message_lower = message.lower()
        
        # Keyword matching for CODER (English + Russian)
        coder_keywords = [
            "create", "write", "implement", "add", "build", "develop", "code",
            "refactor", "modify", "update", "change", "file", "component", "constant",
            "создать", "создай", "добавить", "добавь", "написать", "напиши",
            "реализовать", "реализуй", "изменить", "измени", "файл", "константу"
        ]
        
        # Keyword matching for ARCHITECT (English + Russian)
        architect_keywords = [
            "design", "architecture", "plan", "spec", "blueprint", "structure",
            "дизайн", "архитектур", "план", "спецификац", "структур"
        ]
        
        # Keyword matching for DEBUG (English + Russian)
        debug_keywords = [
            "debug", "error", "bug", "problem", "why", "investigate", "crash", "fix",
            "дебаг", "ошибк", "баг", "проблем", "почему", "исследовать", "крэш", "исправ"
        ]
        
        # Keyword matching for ASK (English + Russian)
        ask_keywords = [
            "explain", "what is", "how does", "help", "understand", "tell me",
            "объясни", "что такое", "как работает", "помоги понять", "расскажи"
        ]
        
        # Check keywords in order of priority
        if any(kw in message_lower for kw in coder_keywords):
            return AgentType.CODER
        elif any(kw in message_lower for kw in architect_keywords):
            return AgentType.ARCHITECT
        elif any(kw in message_lower for kw in debug_keywords):
            return AgentType.DEBUG
        elif any(kw in message_lower for kw in ask_keywords):
            return AgentType.ASK
        else:
            # Default to Coder for implementation tasks
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
