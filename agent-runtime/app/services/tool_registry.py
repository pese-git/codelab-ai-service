"""
Tool registry for agent runtime.

Defines available tools and their specifications for LLM.
Local tools (echo, calculator) can be executed directly.
Other tools (file operations, commands) are executed on IDE side via WebSocket.
"""
import logging
from typing import Any, Callable, Dict, List

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


def create_plan_tool(subtasks: List[Dict[str, Any]]) -> str:
    """
    Create an execution plan for complex tasks.
    
    This tool allows the Orchestrator to break down complex tasks into
    manageable subtasks that will be executed sequentially by specialized agents.
    
    Args:
        subtasks: List of subtask definitions, each containing:
            - id: Unique identifier (e.g., "subtask_1")
            - description: What needs to be done
            - agent: Which agent should handle it (coder, architect, debug, ask)
            - estimated_time: Optional time estimate (e.g., "2 min")
            - dependencies: Optional list of subtask IDs that must complete first
    
    Returns:
        Special marker string that will be processed by the orchestrator
    """
    import json
    # Return a special marker with the plan data
    return f"__CREATE_PLAN__|{json.dumps(subtasks)}"


# ===== Tool Registry =====

# Local tools that can be executed in agent-runtime
LOCAL_TOOLS: Dict[str, Callable] = {
    "echo": echo_tool,
    "calculator": calculator_tool,
    "switch_mode": switch_mode_tool,
    "create_plan": create_plan_tool
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
    _create_tool_spec(
        name="create_plan",
        description=(
            "Create an execution plan for complex tasks by breaking them down into subtasks. "
            "Use this when a task requires multiple steps, coordination between different agents, "
            "or when the task is too complex to handle in a single agent session. "
            "Each subtask will be executed sequentially by the appropriate specialized agent."
        ),
        parameters={
            "type": "object",
            "properties": {
                "subtasks": {
                    "type": "array",
                    "description": "List of subtasks to execute in order",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Unique identifier for the subtask (e.g., 'subtask_1', 'subtask_2')"
                            },
                            "description": {
                                "type": "string",
                                "description": "Clear description of what needs to be done in this subtask"
                            },
                            "agent": {
                                "type": "string",
                                "enum": ["coder", "architect", "debug", "ask"],
                                "description": "Which specialized agent should handle this subtask"
                            },
                            "estimated_time": {
                                "type": "string",
                                "description": "Optional estimated time to complete (e.g., '2 min', '5 min')"
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of subtask IDs that must complete before this one",
                                "default": []
                            }
                        },
                        "required": ["id", "description", "agent"]
                    }
                }
            },
            "required": ["subtasks"]
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


# Log registered tools on module load
logger.info(f"Registered local tools: {list(LOCAL_TOOLS.keys())}")
logger.debug(f"Total tool specifications: {len(TOOLS_SPEC)}")
