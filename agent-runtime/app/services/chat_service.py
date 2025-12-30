from typing import List
# from fastapi import Depends

from app.models.schemas import Message
from app.core.config import logger
from app.services.session_manager import session_manager
from app.core.agent.prompts import SYSTEM_PROMPT
from app.core.agent.llm_proxy_agent import LLMProxyAgent
from app.services.llm_proxy_client import LLMProxyClient
from app.services.orchestrator import AgentOrchestrator
# get_llm_proxy_client и get_tool_registry теперь только в app/core/dependencies.py

class ChatService:
    def __init__(self, llm_proxy_client: LLMProxyClient, tools):
        self.llm_proxy_client = llm_proxy_client
        self.tools = tools

    def get_history(self, session_id: str) -> List[Message]:
        session = session_manager.get(session_id)
        return session.messages if session else []

    async def stream_message(self, input_message: Message) -> dict:
        logger.info(
            f"[TRACE] Incoming message stream: session_id={getattr(input_message, 'session_id', '-')}, content={input_message.content}"
        )
        session_manager.get_or_create(getattr(input_message, 'session_id', '-'), system_prompt=SYSTEM_PROMPT)
        session_manager.append_message(
            getattr(input_message, 'session_id', '-'),
            role=input_message.role,
            content=input_message.content,
            name=input_message.name if hasattr(input_message, 'name') else None,
        )
        history = self.get_history(getattr(input_message, 'session_id', '-'))
        logger.debug(
            f"[TRACE] Chat history for {getattr(input_message, 'session_id', '-')}: {[h.model_dump() for h in history]}"
        )
        agent = LLMProxyAgent(llm=self.llm_proxy_client)
        orchestrator = AgentOrchestrator(agent=agent, tools=self.tools, session_id=getattr(input_message, 'session_id', '-'))
        result = await orchestrator.run([m.model_dump() for m in history])
        final_answer = result.get("result", "No response from agent.")
        trace = result.get("trace", [])
        session_manager.append_message(
            getattr(input_message, 'session_id', '-'),
            role="assistant",
            content=final_answer
        )
        logger.info(f"[TRACE] Orchestrator finished. Final answer: {final_answer}")
        return {
            "token": final_answer,
            "is_final": True,
            "type": "assistant_message",
            "trace": trace,
        }

# get_chat_service теперь в app/core/dependencies.py