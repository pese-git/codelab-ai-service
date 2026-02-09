"""
Tool registry for agent runtime.

Defines available tools and their specifications for LLM.

Tool Categories:
1. Local tools (echo, calculator, switch_mode) - executed in agent-runtime
2. IDE-side tools (file operations, commands) - executed on IDE side via WebSocket
3. Virtual tools (attempt_completion, ask_followup_question, create_plan) -
   handled specially in agent-runtime, not executed as regular tools
"""
import logging
from typing import Any, Callable, Dict, List, Optional

from app.models.schemas import ToolCall

logger = logging.getLogger("agent-runtime.tool_registry")


# ===== Local Tool Implementations =====

def echo_tool(text: str) -> str:
    """Echo any text string"""
    return text


def calculator_tool(expr: str) -> str:
    """
    Calculate a math expression using eval.
    
    WARNING: Not safe for production use with untrusted input.
    """
    try:
        result = eval(expr)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def switch_mode_tool(mode: str, reason: str = "Agent requested switch") -> str:
    """
    Request to switch to a different agent mode.
    
    This is a special tool that returns a marker for agent switching.
    The actual switch is handled by the orchestrator.
    
    Args:
        mode: Target agent mode (orchestrator, coder, architect, debug, ask)
        reason: Reason for switching
        
    Returns:
        Special marker string that will be processed by the agent
    """
    # Return a special marker that will be detected by the agent
    # The agent will then emit a switch_agent chunk
    return f"__SWITCH_MODE__|{mode}|{reason}"


# ===== Tool Registry =====

# Local tools that can be executed in agent-runtime
LOCAL_TOOLS: Dict[str, Callable] = {
    "echo": echo_tool,
    "calculator": calculator_tool,
    "switch_mode": switch_mode_tool
}

# Virtual tools that are handled specially in agent-runtime
# These tools are not executed as regular tools, but trigger special behavior
VIRTUAL_TOOLS = {
    "attempt_completion",  # Marks task as complete, returns result to user
    "ask_followup_question",  # Requests clarification from user
    "create_plan"  # Creates execution plan (architect agent only)
}


# ===== Tool Specifications for LLM =====

def _create_tool_spec(
    name: str, 
    description: str, 
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Create OpenAI-compatible tool specification"""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters
        }
    }


TOOLS_SPEC: List[Dict[str, Any]] = [
    # Local tools
    _create_tool_spec(
        name="echo",
        description="Echo any text string",
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to echo"
                }
            },
            "required": ["text"]
        }
    ),
    _create_tool_spec(
        name="calculator",
        description="Calculate a math expression",
        parameters={
            "type": "object",
            "properties": {
                "expr": {
                    "type": "string",
                    "description": "Math expression to evaluate"
                }
            },
            "required": ["expr"]
        }
    ),
    _create_tool_spec(
        name="switch_mode",
        description=(
            "Switch to a different agent mode when the current agent cannot handle the task. "
            "Use this when you need capabilities that are outside your scope. "
            "Available modes: orchestrator (task routing), coder (code changes), "
            "architect (planning), debug (troubleshooting), ask (Q&A only)"
        ),
        parameters={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["orchestrator", "coder", "architect", "debug", "ask"],
                    "description": "Target agent mode to switch to"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for switching modes",
                    "default": "Task requires different agent capabilities"
                }
            },
            "required": ["mode"]
        }
    ),
    
    # IDE-side tools
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
                "required": ["path"]
            }
        }
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
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in the specified path within workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to directory within workspace. Use '.' for workspace root."
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "If true, list files recursively in subdirectories",
                        "default": False
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "If true, include hidden files (starting with .)",
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
            "description": "Create a new directory at the specified path within workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path for the new directory within workspace"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "If true, create parent directories as needed",
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
            "name": "execute_command",
            "description": "Execute a shell command in the workspace. Dangerous commands require user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute (e.g., 'flutter pub get', 'git status')"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory relative to workspace root"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 60, max: 300)",
                        "default": 60
                    },
                    "shell": {
                        "type": "boolean",
                        "description": "Run command through shell",
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
            "description": "Search for text patterns in code files using grep.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (text or regex pattern)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory path to search in (default: workspace root)",
                        "default": "."
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.dart', '*.yaml')"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Case-sensitive search",
                        "default": False
                    },
                    "regex": {
                        "type": "boolean",
                        "description": "Treat query as regex pattern",
                        "default": False
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 100, max: 1000)",
                        "default": 100
                    }
                },
                "required": ["query"]
            }
        }
    },
    
    # ===== Virtual Tools (Agent-Runtime Only) =====
    # These tools are not executed on IDE side, but handled specially in agent-runtime
    
    {
        "type": "function",
        "function": {
            "name": "attempt_completion",
            "description": (
                "Present the final result of the task to the user. "
                "Use this when you have completed the task and want to show the result. "
                "This is a terminal operation - the conversation will be marked as complete."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "string",
                        "description": "Concise summary of what was accomplished. Be direct and conclusive."
                    }
                },
                "required": ["result"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_followup_question",
            "description": (
                "Ask the user a clarifying question when you need additional information to proceed. "
                "Use this only when necessary information is missing and cannot be inferred from context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Clear, specific question to ask the user"
                    },
                    "suggestions": {
                        "type": "array",
                        "description": "2-4 suggested answers to help the user respond quickly",
                        "items": {
                            "type": "string"
                        },
                        "minItems": 2,
                        "maxItems": 4
                    }
                },
                "required": ["question", "suggestions"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_plan",
            "description": (
                "Create an execution plan with subtasks for implementation. "
                "Use this when the task requires code changes or implementation work. "
                "Each subtask will be executed by a specialized agent (coder, debug, or ask)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Brief title describing the plan"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of what will be implemented"
                    },
                    "subtasks": {
                        "type": "array",
                        "description": "List of concrete, actionable subtasks",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "Brief title of the subtask"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Detailed description of what needs to be done"
                                },
                                "agent": {
                                    "type": "string",
                                    "enum": ["coder", "debug", "ask"],
                                    "description": "Agent responsible for executing this subtask"
                                },
                                "estimated_time_minutes": {
                                    "type": "integer",
                                    "description": "Estimated time in minutes",
                                    "minimum": 1
                                },
                                "dependencies": {
                                    "type": "array",
                                    "description": "Indices of subtasks that must complete before this one",
                                    "items": {
                                        "type": "integer"
                                    }
                                }
                            },
                            "required": ["title", "description", "agent", "estimated_time_minutes"]
                        },
                        "minItems": 1
                    }
                },
                "required": ["title", "description", "subtasks"]
            }
        }
    }
]


# ===== Tool Execution =====

async def execute_local_tool(tool_call: ToolCall) -> str:
    """
    Execute a local tool (echo, calculator).
    
    Args:
        tool_call: Tool call to execute
        
    Returns:
        Tool execution result as string
        
    Raises:
        ValueError: If tool is not found in local registry
    """
    tool_fn = LOCAL_TOOLS.get(tool_call.tool_name)
    
    if not tool_fn:
        raise ValueError(
            f"Tool '{tool_call.tool_name}' not found in local registry. "
            "Should be executed on IDE side."
        )
    
    try:
        logger.info(f"Executing local tool: {tool_call.tool_name}")
        
        # Convert arguments to dict if needed
        args = (
            tool_call.arguments.model_dump() 
            if hasattr(tool_call.arguments, "model_dump") 
            else dict(tool_call.arguments)
        )
        
        result = tool_fn(**args)
        logger.info(f"Local tool '{tool_call.tool_name}' executed successfully")
        return result
        
    except Exception as e:
        error_msg = f"Error executing tool '{tool_call.tool_name}': {e}"
        logger.error(error_msg, exc_info=True)
        return error_msg


class ToolRegistry:
    """
    Реестр инструментов для агентов.
    
    Предоставляет доступ к спецификациям инструментов
    и функциям для их выполнения.
    
    Содержит три категории инструментов:
    1. Локальные (3): echo, calculator, switch_mode
    2. IDE-side (6): read_file, write_file, list_files, create_directory,
                     execute_command, search_in_code
    3. Виртуальные (3): attempt_completion, ask_followup_question, create_plan
    
    Пример:
        >>> registry = ToolRegistry()
        >>> all_tools = registry.get_all_tools()
        >>> len(all_tools)
        12
    """
    
    def __init__(self):
        """Инициализация реестра"""
        self._tools_spec = TOOLS_SPEC
        self._local_tools = LOCAL_TOOLS
        logger.info(f"ToolRegistry initialized with {len(self._tools_spec)} tools")
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        Получить все доступные инструменты.
        
        Returns:
            Список спецификаций инструментов в формате OpenAI
        """
        return self._tools_spec.copy()
    
    def get_tool_spec(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Получить спецификацию конкретного инструмента.
        
        Args:
            tool_name: Имя инструмента
            
        Returns:
            Спецификация инструмента или None если не найден
        """
        for tool in self._tools_spec:
            if tool["function"]["name"] == tool_name:
                return tool
        return None
    
    def is_local_tool(self, tool_name: str) -> bool:
        """
        Проверить, является ли инструмент локальным.
        
        Локальные инструменты выполняются в agent-runtime,
        остальные - на стороне IDE.
        
        Args:
            tool_name: Имя инструмента
            
        Returns:
            True если инструмент локальный
        """
        return tool_name in self._local_tools
    
    def get_local_tool_function(self, tool_name: str) -> Optional[Callable]:
        """
        Получить функцию локального инструмента.
        
        Args:
            tool_name: Имя инструмента
            
        Returns:
            Функция инструмента или None если не локальный
        """
        return self._local_tools.get(tool_name)
    
    def is_virtual_tool(self, tool_name: str) -> bool:
        """
        Проверить, является ли инструмент виртуальным.
        
        Виртуальные инструменты не выполняются как обычные инструменты,
        а обрабатываются специальным образом в agent-runtime:
        - attempt_completion: завершает задачу и возвращает результат
        - ask_followup_question: запрашивает уточнение у пользователя
        - create_plan: создает план выполнения (только для architect)
        
        Args:
            tool_name: Имя инструмента
            
        Returns:
            True если инструмент виртуальный
        """
        return tool_name in VIRTUAL_TOOLS


# Singleton instance
tool_registry = ToolRegistry()

# Log registered tools on module load
logger.info(f"Registered local tools: {list(LOCAL_TOOLS.keys())}")
logger.debug(f"Total tool specifications: {len(TOOLS_SPEC)}")
