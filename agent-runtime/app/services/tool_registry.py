# app/services/tool_registry.py

import inspect
import json

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
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters
        }
    }

TOOLS = {
    "echo": echo_tool,
    "calculator": math_tool
}

TOOLS_SPEC = [
    tool_spec(
        echo_tool,
        name="echo",
        description="Echo any text string",
        parameters={
            "type": "object",
            "properties": { "text": { "type": "string", "description": "Text to echo" } },
            "required": ["text"]
        }
    ),
    tool_spec(
        math_tool,
        name="calculator",
        description="Calculate a math expression",
        parameters={
            "type": "object",
            "properties": { "expr": { "type": "string", "description": "Math expression to evaluate" } },
            "required": ["expr"]
        }
    ),
]
