"""
LLM Context — Bounded Context для работы с LLM провайдерами.

Инкапсулирует всю логику взаимодействия с LLM API:
- Value Objects для типобезопасности
- Entities для бизнес-логики
- Domain Events для трассировки
- Domain Services для сложной логики
- Ports для абстракции инфраструктуры
"""

# Value Objects
from .value_objects import (
    ModelName,
    PromptTemplate,
    TokenLimit,
    Temperature,
    LLMRequestId,
    FinishReason,
)

# Entities
from .entities import (
    LLMRequest,
    LLMInteraction,
)

# Domain Events
from .events import (
    LLMRequestCreated,
    LLMRequestValidated,
    LLMRequestSent,
    LLMResponseReceived,
    LLMResponseProcessed,
    LLMInteractionStarted,
    LLMInteractionCompleted,
    LLMInteractionFailed,
)

# Domain Services
from .services import (
    LLMRequestBuilder,
    LLMResponseValidator,
    TokenEstimator,
)

# Ports
from .ports import (
    ILLMProvider,
    ITokenCounter,
)

__all__ = [
    # Value Objects
    "ModelName",
    "PromptTemplate",
    "TokenLimit",
    "Temperature",
    "LLMRequestId",
    "FinishReason",
    # Entities
    "LLMRequest",
    "LLMInteraction",
    # Domain Events
    "LLMRequestCreated",
    "LLMRequestValidated",
    "LLMRequestSent",
    "LLMResponseReceived",
    "LLMResponseProcessed",
    "LLMInteractionStarted",
    "LLMInteractionCompleted",
    "LLMInteractionFailed",
    # Domain Services
    "LLMRequestBuilder",
    "LLMResponseValidator",
    "TokenEstimator",
    # Ports
    "ILLMProvider",
    "ITokenCounter",
]
