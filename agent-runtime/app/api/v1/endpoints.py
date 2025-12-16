from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import AppConfig, logger
from app.models.schemas import HealthResponse, Message, SessionState, ToolResult, MessageResponse
from app.services.llm_stream_service import llm_stream
from app.services.session_manager import session_manager
import asyncio


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


@router.post("/agent/message/stream")
async def message_stream(message: Message):
    logger.info(
        f"[Agent] Incoming message stream: session_id={message.session_id}, content={message.content}"
    )
    # Получить или создать сессию с system prompt
    session_manager.get_or_create(message.session_id, system_prompt=SYSTEM_PROMPT)
    # Добавить user message
    session_manager.append_message(message.session_id, "user", message.content)
    
    # collect first item from llm_stream and return as JSON
    event = None
    async for ev in llm_stream(message.session_id):
        event = ev
        break
    data = event["data"]
    if isinstance(data, str):
        import json as _json
        data = _json.loads(data)
    return JSONResponse(content=data)
