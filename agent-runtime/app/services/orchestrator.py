import logging
from typing import List, Dict, Any

from app.core.agent.base_agent import BaseAgent
from app.core.agent.sgr import AgentStep, UseTool, Reply, Finish

logger = logging.getLogger("agent-runtime")

class AgentOrchestrator:
    def __init__(self, agent: BaseAgent, tools: dict):
        self.agent = agent
        self.tools = tools

    async def run(self, history: List[Dict[str, Any]], max_steps: int = 8):
        trace = []
        for _ in range(max_steps):
            step: AgentStep = await self.agent.decide({"history": history})
            step_value = getattr(step, "step", step)
            step_type = type(step_value).__name__
            trace.append({"type": step_type, "value": step_value.dict() if hasattr(step_value, 'dict') else str(step_value)})
            if step_type == "Reply":
                reply = getattr(step_value, "content", "")
                history.append({"role": "assistant", "content": reply})
            elif step_type == "UseTool":
                tool_name = getattr(step_value, "tool_name", "")
                args = getattr(step_value, "args", {})
                tool_fn = self.tools.get(tool_name)
                if tool_fn:
                    try:
                        tool_result = tool_fn(**args)
                    except Exception as e:
                        tool_result = f"Tool error: {e}"
                else:
                    tool_result = f"No such tool: {tool_name}"
                history.append({"role": "tool", "name": tool_name, "content": tool_result})
                logger.info(f"[ORCHESTRATOR] Tool '{tool_name}' result: {tool_result}")
            elif step_type == "AskAgent":
                history.append({"role": "assistant", "content": f"AskAgent not supported in this scenario."})
            elif step_type == "Finish":
                answer = getattr(step_value, "summary", "")
                logger.info(f"[ORCHESTRATOR] Reasoning finished with summary: {answer}")
                return {"result": answer, "trace": trace}
        logger.warning("[ORCHESTRATOR] Max reasoning steps exceeded; stopping loop.")
        return {"result": "Max reasoning steps exceeded", "trace": trace}
