import pprint
from typing import Optional, override

from app.core.agent.base_agent import BaseAgent
from app.core.agent.sgr import AgentStep, Finish, Reply
from app.core.config import AppConfig, logger
from app.services.llm_proxy_client import LLMProxyClient
from app.services.tool_registry import TOOLS


class LLMProxyAgent(BaseAgent):
    name = "llm_proxy"
    description = "LLM Proxy AI Agent"
    tools = list(TOOLS.keys())

    def __init__(
        self, llm: LLMProxyClient, model: Optional[str] = None, tools: Optional[dict] = None
    ):
        super().__init__(llm=llm)
        self.model = model or getattr(AppConfig, "LLM_PROXY_MODEL", "gpt-3.5-turbo")
        self.tools = tools or TOOLS

    def _tools_openai_spec(self):
        # Формируем OpenAI-compatible tools spec из self.tools
        spec = []
        for name, fn in self.tools.items():  # ty:ignore[possibly-missing-attribute]
            if name == "echo":
                spec.append(
                    {
                        "type": "function",
                        "function": {
                            "name": "echo",
                            "description": "Echo any text",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string", "description": "Text to echo"}
                                },
                                "required": ["text"],
                            },
                        },
                    }
                )
            if name == "calculator":
                spec.append(
                    {
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "description": "Calculate a math expression",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "expr": {
                                        "type": "string",
                                        "description": "Math expression to evaluate",
                                    }
                                },
                                "required": ["expr"],
                            },
                        },
                    }
                )
        return spec

    def _has_tool_call(self, llm_response) -> bool:
        choices = llm_response.get("choices", [])
        return bool(
            choices
            and "tool_calls" in choices[0]["message"]
            and choices[0]["message"]["tool_calls"]
        )

    def _call_tool(self, tool_call):
        name = tool_call.get("function", {}).get("name")
        arguments = tool_call.get("function", {}).get("arguments", {})
        tool_fn = self.tools.get(name)  # ty:ignore[possibly-missing-attribute]
        if tool_fn:
            return tool_fn(**arguments)
        return f"Unknown tool: {name}"

    @override
    async def decide(self, context: dict) -> AgentStep:
        history = context["history"]
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
        logger.info(
            f"[TRACE][LLMProxyAgent] LLM input: {pprint.pformat(messages, indent=2, width=120)}"
        )
        tools_spec = self._tools_openai_spec()
        logger.info(
            f"[TRACE][LLMProxyAgent] Sending tools: {pprint.pformat(tools_spec, indent=2, width=120)}"
        )
        try:
            response = await self.llm.chat_completion(  # ty:ignore[possibly-missing-attribute]
                model=self.model, messages=messages, tools=tools_spec
            )
            logger.info(
                f"[TRACE][LLMProxyAgent] LLM output: {pprint.pformat(response, indent=2, width=120)}"
            )
            if self._has_tool_call(response):
                tool_calls = response["choices"][0]["message"]["tool_calls"]
                result_chunks = []
                for tool_call in tool_calls:
                    tool_result = self._call_tool(tool_call)
                    result_chunks.append(
                        f"Tool `{tool_call['function']['name']}` result: {tool_result}"
                    )
                result = "\n".join(result_chunks)
                logger.info(f"[TRACE][LLMProxyAgent] tool_call results: {result}")
                return AgentStep.model_construct(
                    step=Reply.model_construct(action="reply", content=result)
                )
            else:
                reply_text = response["choices"][0]["message"]["content"][0]["content"]
                logger.info(f"[TRACE][LLMProxyAgent] reply_text: {reply_text}")
                return AgentStep.model_construct(step=Finish.model_construct(summary=reply_text))
        except Exception as e:
            logger.error(f"[TRACE][LLMProxyAgent][ERROR] {e}", exc_info=True)
            raise
