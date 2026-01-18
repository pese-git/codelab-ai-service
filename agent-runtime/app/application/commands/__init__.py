"""
Commands (Команды).

Команды представляют намерение изменить состояние системы.
Следуют паттерну CQRS (Command Query Responsibility Segregation).
"""

from .base import Command, CommandHandler
from .create_session import CreateSessionCommand, CreateSessionHandler
from .add_message import AddMessageCommand, AddMessageHandler
from .switch_agent import SwitchAgentCommand, SwitchAgentHandler

__all__ = [
    "Command",
    "CommandHandler",
    "CreateSessionCommand",
    "CreateSessionHandler",
    "AddMessageCommand",
    "AddMessageHandler",
    "SwitchAgentCommand",
    "SwitchAgentHandler",
]
