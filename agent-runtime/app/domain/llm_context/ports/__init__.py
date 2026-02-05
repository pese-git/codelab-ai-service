"""
Ports (интерфейсы) для LLM Context.

Определяют контракты для взаимодействия с внешними системами.
"""

from .llm_provider import ILLMProvider
from .token_counter import ITokenCounter

__all__ = [
    "ILLMProvider",
    "ITokenCounter",
]
