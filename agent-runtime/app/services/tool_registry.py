import json
import logging
from typing import Callable, Dict

from app.models.schemas import ToolCall
from app.services.tool_call_handler import tool_call_handler

logger = logging.getLogger("agent-runtime.tool_registry")


# ==== Локальные реализации инструментов ====
def echo_tool(text: str) -> str:
    """Echo any text string"""
    return text


def math_tool(expr: str) -> str:
    """Calculate a math expression (string: expr) using eval (NOT safe for prod)."""
    try:
        return str(eval(expr))
    except Exception as e:
        return f"error: {e}"


def tool_spec(fn, name: str, description: str, parameters: dict):
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": parameters},
    }


TOOLS: Dict[str, Callable] = {"echo": echo_tool, "calculator": math_tool}

TOOLS_SPEC = [
    tool_spec(
        echo_tool,
        name="echo",
        description="Echo any text string",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to echo"}},
            "required": ["text"],
        },
    ),
    tool_spec(
        math_tool,
        name="calculator",
        description="Calculate a math expression",
        parameters={
            "type": "object",
            "properties": {
                "expr": {"type": "string", "description": "Math expression to evaluate"}
            },
            "required": ["expr"],
        },
    ),
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read any file from disk.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path"}},
                "required": ["path"],
            },
        },
    },
]


async def execute_tool(
    session_id: str,
    tool_call: ToolCall,
    use_gateway: bool = False,
):
    """
    Унифицированный вызов инструмента: локально или через Gateway (если use_gateway или отсутствует в TOOLS).
    """
    import pprint

    logger.info(f"[TOOL_REGISTRY] Executing tool_id: {tool_call.id}")
    logger.info(f"[TOOL_REGISTRY] Executing tool: {tool_call.tool_name}")
    logger.info(
        f"[TOOL_REGISTRY] Arguments: {pprint.pformat(tool_call.arguments, indent=2, width=120)}"
    )
    if use_gateway or tool_call.tool_name not in TOOLS:
        try:
            logger.info(
                f"[TOOL_REGISTRY] Forwarding to gateway (session={session_id}):\n"
                f"{pprint.pformat(tool_call.model_dump(), indent=2, width=120)}"
            )
            result = await tool_call_handler.execute(session_id or "none", tool_call)
            logger.info(
                f"[TOOL_REGISTRY] Gateway result: {pprint.pformat(result, indent=2, width=120)}"
            )
            return (
                result
                if result is not None
                else f"Tool `{tool_call.tool_name}` failed via gateway!"
            )
        except Exception as ex:
            logger.error(f"[TOOL_REGISTRY][ERROR] Gateway exception: {ex}", exc_info=True)
            return f"Tool `{tool_call.tool_name}` gateway error: {ex}"
    # Локальный вызов
    tool_fn = TOOLS.get(tool_call.tool_name)
    if tool_fn:
        try:
            logger.info(f"[TOOL_REGISTRY] Calling local tool function: {tool_fn.__name__}")  # ty:ignore[unresolved-attribute]
            args = tool_call.arguments
            result = tool_fn(**args)
            logger.info(
                f"[TOOL_REGISTRY] Local result: {pprint.pformat(result, indent=2, width=120)}"
            )
            return result
        except Exception as e:
            logger.error(f"[TOOL_REGISTRY][ERROR] Local tool error: {e}", exc_info=True)
            return f"Tool `{tool_call.tool_name}` local error: {e}"
    logger.warning(
        f"[TOOL_REGISTRY] Tool `{tool_call.tool_name}` not found in registry or as gateway tool"
    )
    return f"Tool `{tool_call.tool_name}` not found"


# Однократно — трейсы наличных tools и их спецификаций
if TOOLS:
    logger.info(f"[TOOL_REGISTRY] Registered local tools: {list(TOOLS.keys())}")
logger.info(
    f"[TOOL_REGISTRY] TOOLS_SPEC for LLM:\n{json.dumps(TOOLS_SPEC, indent=2, ensure_ascii=False)}"
)
