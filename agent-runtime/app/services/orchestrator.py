import logging
import pprint
from typing import Any, Dict, List, Optional

from app.core.agent.base_agent import BaseAgent
from app.models.agents import AgentStep, UseTool
from app.models.schemas import ToolCall
from app.services.tool_registry import execute_tool

logger = logging.getLogger("agent-runtime")


class AgentOrchestrator:
    def __init__(self, agent: BaseAgent, tools: dict, session_id: str):
        self.agent = agent
        self.tools = tools
        self.session_id = session_id

    async def run(self, history: List[Dict[str, Any]], max_steps: int = 8):
        trace = []
        for _ in range(max_steps):
            step: AgentStep = await self.agent.decide({"history": history})
            step_value = getattr(step, "step", None)
            step_type = type(step_value).__name__
            trace.append(
                {
                    "type": step_type,
                    "value": step_value.dict() if hasattr(step_value, "dict") else str(step_value),
                }
            )
            if step_type == "Reply":
                reply = getattr(step_value, "content", "")
                history.append({"role": "assistant", "content": reply})
            elif step_type == "UseTool":
                tool: Optional[UseTool] = step_value
                logger.info(
                    f"[ORCHESTRATOR] Parsing tool_calls from UseTool: {pprint.pformat(tool, indent=2, width=120)}"
                )
                if tool is not None:
                    tool_call = ToolCall.model_construct(
                        id=tool.tool_id,
                        tool_name=tool.tool_name,
                        arguments=tool.args,
                    )

                    logger.info(
                        f"[ORCHESTRATOR] Parsed tool_call {tool_call.tool_name} args: {pprint.pformat(tool_call, indent=2, width=120)}"
                    )
                    tool_result = await execute_tool(
                        session_id=self.session_id, tool_call=tool_call, use_gateway=False
                    )
                    history.append(
                        {"role": "user", "name": tool_call.tool_name, "content": tool_result}
                    )
                    logger.info(
                        f"[ORCHESTRATOR] Tool '{tool_call.tool_name}' result: {tool_result}"
                    )
            elif step_type == "AskAgent":
                history.append(
                    {"role": "assistant", "content": "AskAgent not supported in this scenario."}
                )
            elif step_type == "Finish":
                answer = getattr(step_value, "summary", "")
                logger.info(f"[ORCHESTRATOR] Reasoning finished with summary: {answer}")
                return {"result": answer, "trace": trace}
        logger.warning("[ORCHESTRATOR] Max reasoning steps exceeded; stopping loop.")
        return {"result": "Max reasoning steps exceeded", "trace": trace}
