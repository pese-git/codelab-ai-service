"""
Entities для LLM Context.

Инкапсулируют бизнес-логику работы с LLM запросами и взаимодействиями.
"""

from .llm_request import LLMRequest
from .llm_interaction import LLMInteraction

__all__ = [
    "LLMRequest",
    "LLMInteraction",
]
