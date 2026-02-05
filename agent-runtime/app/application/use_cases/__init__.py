"""
Application Use Cases.

Use Cases инкапсулируют бизнес-логику приложения и координируют
работу доменных сервисов для выполнения конкретных сценариев.

Каждый Use Case:
- Имеет одну четкую ответственность
- Координирует доменные сервисы
- Не содержит бизнес-логику (она в Domain Layer)
- Возвращает результат или генерирует stream

Примеры:
    >>> use_case = ProcessMessageUseCase(...)
    >>> async for chunk in use_case.execute(request):
    ...     print(chunk)
"""

from .base_use_case import UseCase, StreamingUseCase
from .process_message_use_case import ProcessMessageUseCase
from .switch_agent_use_case import SwitchAgentUseCase
from .process_tool_result_use_case import ProcessToolResultUseCase
from .handle_approval_use_case import HandleApprovalUseCase

__all__ = [
    "UseCase",
    "StreamingUseCase",
    "ProcessMessageUseCase",
    "SwitchAgentUseCase",
    "ProcessToolResultUseCase",
    "HandleApprovalUseCase",
]
