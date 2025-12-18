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
        self.model = model or getattr(AppConfig, "LLM_PROXY_MODEL", "gpt-3.5-turbo")
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
            if "tool_calls" in message and message["tool_calls"]:
                tc = message["tool_calls"][0]
                return AgentStep.model_construct(
                    step=UseTool.model_construct(
                        action="use_tool",
                        tool_name=tc["function"]["name"],
                        args=tc["function"].get("arguments", {}),
                    )
                )
            elif message.get("content"):
                logger.info(
                    f"[TRACE][LLMProxyAgent] LLM content: {pprint.pformat(message['content'], indent=2, width=120)}"
                )
                content = message["content"][0]["content"]
                return AgentStep.model_construct(
                    step=Finish.model_construct(action="finish", summary=content)
                )
                # return AgentStep.model_construct(
                #    step=Reply.model_construct(action="reply", content=content)
                # )
            else:
                return AgentStep.model_construct(
                    step=Finish.model_construct(action="finish", summary="No answer")
                )
        except Exception as e:
            logger.error(f"[TRACE][LLMProxyAgent][ERROR] {e}", exc_info=True)
            raise
