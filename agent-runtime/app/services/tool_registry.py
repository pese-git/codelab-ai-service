# app/services/tool_registry.py

def echo_tool(text: str) -> str:
    return text

def math_tool(expr: str) -> str:
    try:
        return str(eval(expr))
    except Exception as e:
        return f"error: {e}"

TOOLS = {
    "echo": echo_tool,
    "calculator": math_tool,
}
