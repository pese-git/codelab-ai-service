import pprint
from typing import Optional, override

from app.core.agent.base_agent import BaseAgent
from app.core.agent.sgr import AgentStep, Reply
from app.core.config import AppConfig, logger
from app.services.llm_proxy_client import LLMProxyClient


class LLMProxyAgent(BaseAgent):
    name = "llm_proxy"
    description = "LLM Proxy AI Agent"
    tools = []

    def __init__(self, llm: LLMProxyClient, model: Optional[str] = None):
        super().__init__(llm=llm)
        self.model = model or getattr(AppConfig, "LLM_PROXY_MODEL", "gpt-3.5-turbo")

    @override
    async def decide(self, context: dict) -> AgentStep:
        history = context["history"]
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
        logger.info(
            f"[TRACE][LLMProxyAgent] LLM input: {pprint.pformat(messages, indent=2, width=120)}"
        )
        try:
            response = await self.llm.chat_completion(model=self.model, messages=messages)
            logger.info(
                f"[TRACE][LLMProxyAgent] LLM output: {pprint.pformat(response, indent=2, width=120)}"
            )
            reply_text = response["choices"][0]["message"]["content"][0]["content"]
            logger.info(f"[TRACE][LLMProxyAgent] reply_text: {reply_text}")
            return AgentStep.model_construct(
                step=Reply.model_construct(action="reply", content=reply_text)
            )
        except Exception as e:
            logger.error(f"[TRACE][LLMProxyAgent][ERROR] {e}", exc_info=True)
            raise
