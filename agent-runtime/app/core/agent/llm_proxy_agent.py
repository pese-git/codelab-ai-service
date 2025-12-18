import json
import pprint
from typing import Optional, override

from app.core.agent.base_agent import BaseAgent
from app.core.agent.sgr import AgentStep, Finish, UseTool
from app.core.config import AppConfig, logger
from app.services.llm_proxy_client import LLMProxyClient
from app.services.tool_registry import TOOLS_SPEC


class LLMProxyAgent(BaseAgent):
    name = "llm_proxy"
    description = "LLM Proxy AI Agent"

    def __init__(self, llm: LLMProxyClient, model: Optional[str] = None, tools_spec=None):
        super().__init__(llm=llm)
        self.model = model or getattr(AppConfig, "LLM_PROXY_MODEL", "gpt-4.1")
        self.tools_spec = tools_spec or TOOLS_SPEC

    @override
    async def decide(self, context: dict) -> AgentStep:
        history = context["history"]
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
        logger.info(
            f"[TRACE][LLMProxyAgent] LLM input: {pprint.pformat(messages, indent=2, width=120)}"
        )
        logger.info(
            f"[TRACE][LLMProxyAgent] Sending tools: {pprint.pformat(self.tools_spec, indent=2, width=120)}"
        )
        try:
            response = await self.llm.chat_completion(
                model=self.model, messages=messages, tools=self.tools_spec
            )
            logger.info(
                f"[TRACE][LLMProxyAgent] LLM output: {pprint.pformat(response, indent=2, width=120)}"
            )
            message = response["choices"][0]["message"]
            # --- Improved logic for tool handling ---
            content_items = message.get("content")
            if content_items:
                # Defensive: OpenAI/LLM content typically as a list of dict(s)
                item = content_items[0]
                if item.get("tool_calls"):
                    tc = item["tool_calls"][0]
                    return AgentStep.model_construct(
                        step=UseTool.model_construct(
                            action="use_tool",
                            tool_id=tc["id"],
                            tool_name=tc["function"]["name"],
                            args=json.loads(tc["function"].get("arguments", "{}")),
                        )
                    )
                elif item.get("function_call"):
                    tc = item["function_call"]
                    return AgentStep.model_construct(
                        step=UseTool.model_construct(
                            action="use_tool",
                            tool_id=tc["id"],
                            tool_name=tc["name"],
                            args=json.loads(tc.get("arguments", "{}")),
                        )
                    )
                elif item.get("content"):
                    logger.info(
                        f"[TRACE][LLMProxyAgent] LLM content: {pprint.pformat(item['content'], indent=2, width=120)}"
                    )
                    return AgentStep.model_construct(
                        step=Finish.model_construct(action="finish", summary=item["content"])
                    )
                else:
                    return AgentStep.model_construct(
                        step=Finish.model_construct(
                            action="finish", summary="No answer (empty content item)"
                        )
                    )
            elif "tool_calls" in message and message["tool_calls"]:
                tc = message["tool_calls"][0]
                return AgentStep.model_construct(
                    step=UseTool.model_construct(
                        action="use_tool",
                        tool_id=tc["id"],
                        tool_name=tc["function"]["name"],
                        args=json.loads(tc["function"].get("arguments", "{}")),
                    )
                )
            elif message.get("content"):
                logger.info(
                    f"[TRACE][LLMProxyAgent] LLM content (plain): {pprint.pformat(message['content'], indent=2, width=120)}"
                )
                return AgentStep.model_construct(
                    step=Finish.model_construct(action="finish", summary=message["content"])
                )
            else:
                return AgentStep.model_construct(
                    step=Finish.model_construct(action="finish", summary="No answer")
                )
        except Exception as e:
            logger.error(f"[TRACE][LLMProxyAgent][ERROR] {e}", exc_info=True)
            raise
