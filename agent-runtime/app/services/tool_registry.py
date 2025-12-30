import json
import logging
from typing import Callable, Dict

from app.models.schemas import ToolCall
# DEPRECATED: ToolCallHandler не используется в текущей архитектуре
# from app.services.tool_call_handler import tool_call_handler

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
# get_tool_registry теперь в app/core/dependencies.py

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
            "description": "Read content from a file on disk. Supports partial reading by line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file relative to project workspace"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (default: utf-8)",
                        "default": "utf-8"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-based, inclusive)",
                        "minimum": 1
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (1-based, inclusive)",
                        "minimum": 1
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Requires user confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file relative to project workspace"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (default: utf-8)",
                        "default": "utf-8"
                    },
                    "create_dirs": {
                        "type": "boolean",
                        "description": "Create parent directories if they don't exist",
                        "default": False
                    },
                    "backup": {
                        "type": "boolean",
                        "description": "Create backup before overwriting existing file",
                        "default": True
                    }
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in the specified path within workspace. Returns file names, types (file/directory), sizes, and modification times.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to directory within workspace. Use '.' for workspace root."
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "If true, list files recursively in subdirectories. Default: false",
                        "default": False
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "If true, include hidden files (starting with .). Default: false",
                        "default": False
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g., '*.dart', '**/*.yaml')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a new directory at the specified path within workspace. Can create parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path for the new directory within workspace"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "If true, create parent directories as needed. Default: true",
                        "default": True
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command in the workspace. Supports Flutter, Dart, Git, and other development tools. Dangerous commands require user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute (e.g., 'flutter pub get', 'git status')"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory relative to workspace root. Default: workspace root"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds. Default: 60, Max: 300",
                        "default": 60
                    },
                    "shell": {
                        "type": "boolean",
                        "description": "Run command through shell. Default: false",
                        "default": False
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_code",
            "description": "Search for text patterns in code files using grep. Supports regex patterns and file filtering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (text or regex pattern)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory path to search in. Default: workspace root",
                        "default": "."
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.dart', '*.yaml')"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Case-sensitive search. Default: false",
                        "default": False
                    },
                    "regex": {
                        "type": "boolean",
                        "description": "Treat query as regex pattern. Default: false",
                        "default": False
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results. Default: 100, Max: 1000",
                        "default": 100
                    }
                },
                "required": ["query"]
            }
        }
    },
]


async def execute_tool(
    session_id: str,
    tool_call: ToolCall,
    use_gateway: bool = False,
):
    """
    DEPRECATED: В текущей архитектуре инструменты выполняются на стороне IDE через WebSocket.
    
    Эта функция оставлена для обратной совместимости, но не должна использоваться.
    Tool calls отправляются в SSE stream и обрабатываются IDE.
    """
    import pprint

    logger.warning(
        f"[TOOL_REGISTRY] DEPRECATED: execute_tool called for {tool_call.tool_name}. "
        "Tools should be executed on IDE side via WebSocket."
    )
    
    logger.info(f"[TOOL_REGISTRY] Executing tool_id: {tool_call.id}")
    logger.info(f"[TOOL_REGISTRY] Executing tool: {tool_call.tool_name}")
    logger.info(
        f"[TOOL_REGISTRY] Arguments: {pprint.pformat(tool_call.arguments, indent=2, width=120)}"
    )
    
    # DEPRECATED: Gateway forwarding не используется в текущей архитектуре
    # if use_gateway or tool_call.tool_name not in TOOLS:
    #     try:
    #         logger.info(
    #             f"[TOOL_REGISTRY] Forwarding to gateway (session={session_id}):\n"
    #             f"{pprint.pformat(tool_call.model_dump(), indent=2, width=120)}"
    #         )
    #         result = await tool_call_handler.execute(session_id or "none", tool_call)
    #         logger.info(
    #             f"[TOOL_REGISTRY] Gateway result: {pprint.pformat(result, indent=2, width=120)}"
    #         )
    #         return (
    #             result
    #             if result is not None
    #             else f"Tool `{tool_call.tool_name}` failed via gateway!"
    #         )
    #     except Exception as ex:
    #         logger.error(f"[TOOL_REGISTRY][ERROR] Gateway exception: {ex}", exc_info=True)
    #         return f"Tool `{tool_call.tool_name}` gateway error: {ex}"
    
    # Локальный вызов (только для echo и calculator)
    tool_fn = TOOLS.get(tool_call.tool_name)
    if tool_fn:
        try:
            logger.info(f"[TOOL_REGISTRY] Calling local tool function: {tool_fn.__name__}")  # ty:ignore[unresolved-attribute]
            args = tool_call.arguments.model_dump() if hasattr(tool_call.arguments, "model_dump") else dict(tool_call.arguments)
            result = tool_fn(**args)
            logger.info(
                f"[TOOL_REGISTRY] Local result: {pprint.pformat(result, indent=2, width=120)}"
            )
            return result
        except Exception as e:
            logger.error(f"[TOOL_REGISTRY][ERROR] Local tool error: {e}", exc_info=True)
            return f"Tool `{tool_call.tool_name}` local error: {e}"
    
    logger.warning(
        f"[TOOL_REGISTRY] Tool `{tool_call.tool_name}` not found in local registry. "
        "Should be executed on IDE side."
    )
    return f"Tool `{tool_call.tool_name}` should be executed on IDE side"


# Однократно — трейсы наличных tools и их спецификаций
if TOOLS:
    logger.info(f"[TOOL_REGISTRY] Registered local tools: {list(TOOLS.keys())}")
logger.info(
    f"[TOOL_REGISTRY] TOOLS_SPEC for LLM:\n{json.dumps(TOOLS_SPEC, indent=2, ensure_ascii=False)}"
)
