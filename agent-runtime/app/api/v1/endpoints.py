import pprint
import traceback

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.agent.llm_proxy_agent import LLMProxyAgent
from app.core.agent.prompts import SYSTEM_PROMPT
from app.core.config import AppConfig, logger
from app.models.schemas import HealthResponse, Message
from app.services.llm_proxy_client import llm_proxy_client
from app.services.orchestrator import AgentOrchestrator
from app.services.session_manager import session_manager
from app.services.tool_registry import TOOLS

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    logger.info("[Agent] Health check called")
    return HealthResponse.model_construct(
        status="healthy", service="agent-runtime", version=AppConfig.VERSION
    )


@router.post("/agent/message/stream")
async def message_stream(message: Message):
    logger.info(
        f"[TRACE] Incoming message stream: session_id={message.session_id}, content={message.content}"
    )
    try:
        session_manager.get_or_create(message.session_id, system_prompt=SYSTEM_PROMPT)
        session_manager.append_message(message.session_id, "user", message.content)
        history = session_manager.get(message.session_id).messages
        logger.debug(
            f"[TRACE] Chat history for {message.session_id}: {pprint.pformat(history, indent=2, width=120)}"
        )
        agent = LLMProxyAgent(llm=llm_proxy_client)
        orchestrator = AgentOrchestrator(agent=agent, tools=TOOLS, session_id=message.session_id)
        result = await orchestrator.run(history)
        final_answer = result.get("result", "No response from agent.")
        trace = result.get("trace", [])
        # Сохраняем ответ в историю
        session_manager.append_message(message.session_id, "assistant", final_answer)
        logger.info(f"[TRACE] Orchestrator finished. Final answer: {final_answer}")
        return JSONResponse(
            content={
                "token": final_answer,
                "is_final": True,
                "type": "assistant_message",
                "trace": trace,
            }
        )
    except Exception:
        logger.error(f"[TRACE][ERROR] Exception in /agent/message/stream\n{traceback.format_exc()}")
        return JSONResponse(content={"error": "Internal server error"}, status_code=500)
