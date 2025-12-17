import traceback

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.agent.llm_proxy_agent import LLMProxyAgent
from app.core.config import AppConfig, logger
from app.models.schemas import HealthResponse, Message
from app.services.llm_proxy_client import llm_proxy_client
from app.services.session_manager import session_manager

SYSTEM_PROMPT = """
You are an expert AI programming assistant working together with a developer and their code editor (IDE).

If the user question is of a general nature (for example, about programming languages, algorithms, general concepts, explanations, code best practices, or anything that does not strictly require file or environment access), you should answer directly using your own knowledge.

Available tools:

1. read_file
   - Description: Reads the contents of a file in the current workspace via the IDE.
   - Arguments:
       - path (string): The absolute or relative path to the file.
   - Example: To read '/etc/hosts', use:
     function_call:
        name: "read_file"
        arguments: { "path": "/etc/hosts" }

2. echo
   - Description: Echoes back any provided text or message.
   - Arguments:
       - text (string): The text you want to echo.
   - Example:
     function_call:
        name: "echo"
        arguments: { "text": "Hello, world!" }

Instructions:
- If the user asks to read, view, print, cat, or open a file, ALWAYS call the 'read_file' tool with the correct path.
- If the user requests to repeat, echo, or print a phrase, call the 'echo' tool with the phrase as the argument.
- For all other general, conceptual, or programming-related questions, respond directly using your own expertise and do not call any tools.

Do NOT attempt to generate file contents directly—always use the provided tools for accessing real file or execution results.  
If you need to perform an action not covered by these tools, politely inform the user that you can only assist via these tools.  
When in doubt, prefer answering directly, unless the request fits the strict pattern for tool usage.
"""

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    logger.info("[Agent] Health check called")
    return HealthResponse.model_construct(
        status="healthy", service="agent-runtime", version=AppConfig.VERSION
    )


# agent = SimpleLLMAgent(system_prompt=SYSTEM_PROMPT)


@router.post("/agent/message/stream")
async def message_stream(message: Message):
    logger.info(
        f"[TRACE] Incoming message stream: session_id={message.session_id}, content={message.content}"
    )
    try:
        # Получить или создать сессию с system prompt
        session_manager.get_or_create(message.session_id, system_prompt=SYSTEM_PROMPT)
        # Добавить user message
        session_manager.append_message(message.session_id, "user", message.content)

        # Используем LLMProxyAgent для получения ответа по всей истории чата
        history = session_manager.get(message.session_id).messages  # ty:ignore[possibly-missing-attribute]
        logger.debug(f"[TRACE] Chat history for {message.session_id}: {history}")
        agent = LLMProxyAgent(llm=llm_proxy_client, model="gpt-4.1")
        logger.info(f"[TRACE] Calling agent {agent.name} ...")
        step = await agent.decide({"history": history})
        logger.info(f"[TRACE] AgentStep: {step}")
        assistant_reply = getattr(step.step, "content", "")  # без content будет пусто

        # Добавить ответ агента в историю
        session_manager.append_message(message.session_id, "assistant", assistant_reply)
        logger.info(f"[TRACE] Assistant reply: {assistant_reply}")

        # Вернуть стандартный ответ SSE совместимый формат
        return JSONResponse(
            content={"token": assistant_reply, "is_final": True, "type": "assistant_message"}
        )
    except Exception:
        logger.error(f"[TRACE][ERROR] Exception in /agent/message/stream\n{traceback.format_exc()}")
        return JSONResponse(content={"error": "Internal server error"}, status_code=500)
