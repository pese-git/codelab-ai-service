"""
Data Transfer Objects (DTO).

DTO используются для передачи данных между слоями приложения.
Они изолируют внутреннюю структуру доменных сущностей от внешнего API.
"""

from .session_dto import SessionDTO, SessionListItemDTO
from .message_dto import MessageDTO
from .agent_context_dto import AgentContextDTO, AgentSwitchDTO

__all__ = [
    "SessionDTO",
    "SessionListItemDTO",
    "MessageDTO",
    "AgentContextDTO",
    "AgentSwitchDTO",
]
