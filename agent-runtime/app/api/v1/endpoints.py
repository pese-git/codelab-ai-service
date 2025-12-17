import pprint
import traceback

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.agent.llm_proxy_agent import LLMProxyAgent
from app.core.agent.prompts import SYSTEM_PROMPT
from app.core.config import AppConfig, logger
from app.models.schemas import HealthResponse, Message
from app.services.llm_proxy_client import llm_proxy_client
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
        history = session_manager.get(message.session_id).messages  # ty:ignore[possibly-missing-attribute]
        logger.debug(
            f"[TRACE] Chat history for {message.session_id}: {pprint.pformat(history, indent=2, width=120)}"
        )
        agent = LLMProxyAgent(llm=llm_proxy_client, model=None)
        logger.info(f"[TRACE] Starting reasoning loop for agent: {agent.name}")
        max_steps = 8
        answer = None
        for _ in range(max_steps):
            step = await agent.decide({"history": history})
            logger.info(f"[TRACE] AgentStep: {step}")
            step_type = type(step.step).__name__
            if step_type == "Reply":
                reply = getattr(step.step, "content", "")
                history.append({"role": "assistant", "content": reply})
            elif step_type == "UseTool":
                tool_name = getattr(step.step, "tool_name", "")
                args = getattr(step.step, "args", {})
                tool_fn = TOOLS.get(tool_name)
                if tool_fn:
                    tool_result = tool_fn(**args)
                else:
                    tool_result = f"No such tool: {tool_name}"
                history.append({"role": "tool", "name": tool_name, "content": tool_result})
                logger.info(f"[TRACE] Tool '{tool_name}' result: {tool_result}")
            elif step_type == "AskAgent":
                history.append(
                    {"role": "assistant", "content": "AskAgent not supported in this endpoint."}
                )
            elif step_type == "Finish":
                answer = getattr(step.step, "summary", "")
                session_manager.append_message(message.session_id, "assistant", answer)
                logger.info(f"[TRACE] Reasoning finished with summary: {answer}")
                return JSONResponse(
                    content={"token": answer, "is_final": True, "type": "assistant_message"}
                )
        logger.warning("[TRACE] Max reasoning steps exceeded; stopping loop.")
        return JSONResponse(
            content={
                "token": "Max reasoning steps exceeded",
                "is_final": True,
                "type": "assistant_message",
            }
        )
    except Exception:
        logger.error(f"[TRACE][ERROR] Exception in /agent/message/stream\n{traceback.format_exc()}")
        return JSONResponse(content={"error": "Internal server error"}, status_code=500)
