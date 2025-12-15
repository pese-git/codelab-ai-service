from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import AppConfig, logger
from app.models.schemas import HealthResponse, Message, SessionState, ToolResult, MessageResponse
from app.services.llm_stream_service import get_sessions, llm_stream
from app.services.tool_manager import get_tool_tracker
import asyncio


SYSTEM_PROMPT = """
You are an expert AI programming assistant working together with a developer and their code editor (IDE).

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
- If the user requests to repeat or print a phrase, call the 'echo' tool with the phrase as the argument.

Do NOT answer as an assistant or attempt to generate file contents directly — you MUST use the provided tools for all matching requests.
If you need to perform an action not covered by these tools, politely inform the user that you can only assist via these tools.
When in doubt, prefer calling a tool.
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
    sessions = get_sessions()

    # Create SessionState if not exists
    if message.session_id not in sessions:
        sessions[message.session_id] = SessionState(
            session_id=message.session_id,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}]
        )
    
    # Append user message to session
    sessions[message.session_id].messages.append({"role": "user", "content": message.content})
    
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


@router.post("/agent/tool/result", response_model=MessageResponse)
async def receive_tool_result(result: ToolResult):
    logger.info(f"[Agent] Received tool_result: call_id={result.call_id}")
    tracker = get_tool_tracker()
    pending = await tracker.complete_tool_call(result.call_id, result)
    if not pending:
        logger.warning(f"[Agent] tool_result: call_id={result.call_id} not found or already completed")
        return MessageResponse(status="error", message=f"Tool call {result.call_id} not found or already completed.")
    # (опционально) инициировать продолжение диалога, разблокировать поток, др.
    # Пока просто подтверждаем успех
    return MessageResponse(status="ok", message=f"Result accepted for tool call {result.call_id}")
