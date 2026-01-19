"""
Механизмы устойчивости (Resilience).

Этот модуль содержит механизмы для повышения устойчивости системы
к сбоям и перегрузкам.
"""

from .circuit_breaker import CircuitBreaker, CircuitState

__all__ = [
    "CircuitBreaker",
    "CircuitState",
]
