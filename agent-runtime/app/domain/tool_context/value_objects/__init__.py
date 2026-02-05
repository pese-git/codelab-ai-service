"""
Value Objects для Tool Context.

Типобезопасные примитивы для работы с инструментами.
"""

from .tool_name import ToolName
from .tool_call_id import ToolCallId
from .tool_arguments import ToolArguments
from .tool_result import ToolResult
from .tool_category import ToolCategory
from .tool_execution_mode import ToolExecutionMode
from .tool_permission import ToolPermission

__all__ = [
    "ToolName",
    "ToolCallId",
    "ToolArguments",
    "ToolResult",
    "ToolCategory",
    "ToolExecutionMode",
    "ToolPermission",
]
