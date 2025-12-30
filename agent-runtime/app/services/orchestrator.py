"""
Agent Orchestrator for legacy endpoint.

DEPRECATED: Used only in legacy /agent/message/stream/legacy endpoint.
New architecture uses stream_response() directly without orchestrator.
"""
import logging
from typing import Any, Dict, List, Optional

from app.core.agent.base_agent import BaseAgent
from app.models.agents import AgentStep, UseTool
from app.models.schemas import ToolCall
from app.services.tool_registry import execute_local_tool

logger = logging.getLogger("agent-runtime.orchestrator")


class AgentOrchestrator:
    """
    Orchestrates agent decision-making and tool execution.
    
    DEPRECATED: This class is only used in the legacy endpoint.
    New architecture handles tool calls via SSE streaming.
    """

    def __init__(self, agent: BaseAgent, tools: dict, session_id: str):
        """
        Initialize orchestrator.
        
        Args:
            agent: Agent instance for decision making
            tools: Available tools registry
            session_id: Session identifier
        """
        self.agent = agent
        self.tools = tools
        self.session_id = session_id

    async def run(
        self, 
        history: List[Dict[str, Any]], 
        max_steps: int = 8
    ) -> Dict[str, Any]:
        """
        Run agent orchestration loop.
        
        Args:
            history: Message history
            max_steps: Maximum number of reasoning steps
            
        Returns:
            Dictionary with result and trace
        """
        trace = []
        
        for step_num in range(max_steps):
            # Get agent decision
            step: AgentStep = await self.agent.decide({"history": history})
            step_value = getattr(step, "step", None)
            step_type = type(step_value).__name__
            
            # Record step in trace
            trace.append({
                "type": step_type,
                "value": (
                    step_value.dict() 
                    if hasattr(step_value, "dict") 
                    else str(step_value)
                ),
            })
            
            logger.debug(
                f"Step {step_num + 1}/{max_steps}: {step_type}"
            )
            
            # Handle different step types
            if step_type == "Reply":
                reply = getattr(step_value, "content", "")
                history.append({"role": "assistant", "content": reply})
                
            elif step_type == "UseTool":
                tool: Optional[UseTool] = step_value
                
                if tool is not None:
                    logger.info(
                        f"Executing tool: {tool.tool_name} "
                        f"(id={tool.tool_id})"
                    )
                    
                    # Create tool call
                    tool_call = ToolCall.model_construct(
                        id=tool.tool_id,
                        tool_name=tool.tool_name,
                        arguments=tool.args,
                    )
                    
                    # Execute tool locally
                    try:
                        tool_result = await execute_local_tool(tool_call)
                    except ValueError as e:
                        # Tool not found locally - should be executed on IDE side
                        tool_result = str(e)
                        logger.warning(f"Tool execution failed: {e}")
                    
                    # Add result to history
                    history.append({
                        "role": "user",
                        "name": tool_call.tool_name,
                        "content": tool_result
                    })
                    
                    logger.info(
                        f"Tool '{tool_call.tool_name}' result: "
                        f"{tool_result[:100]}..."
                    )
                    
            elif step_type == "AskAgent":
                logger.warning("AskAgent not supported in this scenario")
                history.append({
                    "role": "assistant",
                    "content": "AskAgent not supported in this scenario."
                })
                
            elif step_type == "Finish":
                answer = getattr(step_value, "summary", "")
                logger.info(f"Reasoning finished: {answer[:100]}...")
                return {"result": answer, "trace": trace}
        
        # Max steps exceeded
        logger.warning(
            f"Max reasoning steps ({max_steps}) exceeded; stopping loop"
        )
        return {
            "result": "Max reasoning steps exceeded",
            "trace": trace
        }
