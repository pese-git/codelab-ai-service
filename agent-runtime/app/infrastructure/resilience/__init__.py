"""
Механизмы устойчивости (Resilience).

Этот модуль содержит механизмы для повышения устойчивости системы
к сбоям и перегрузкам.
"""

from .circuit_breaker import CircuitBreaker, CircuitState
from .retry_handler import RetryHandler, with_retry, is_retryable_http_error

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "RetryHandler",
    "with_retry",
    "is_retryable_http_error",
]
