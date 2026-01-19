"""
Circuit Breaker для защиты от каскадных сбоев.

Предотвращает перегрузку внешних сервисов при их недоступности.
"""

import asyncio
import logging
from enum import Enum
from datetime import datetime, timedelta, timezone
from typing import Callable, TypeVar, Any

logger = logging.getLogger("agent-runtime.infrastructure.circuit_breaker")

T = TypeVar('T')


class CircuitState(str, Enum):
    """
    Состояния Circuit Breaker.
    
    - CLOSED: Нормальная работа, запросы проходят
    - OPEN: Сервис недоступен, запросы блокируются
    - HALF_OPEN: Тестовый режим, пробуем восстановить
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit Breaker для защиты от каскадных сбоев.
    
    Отслеживает ошибки при вызове внешних сервисов и
    автоматически блокирует запросы при превышении порога.
    
    Атрибуты:
        failure_threshold: Количество ошибок для открытия circuit
        recovery_timeout: Время до попытки восстановления (секунды)
        expected_exception: Тип исключения для отслеживания
        state: Текущее состояние circuit
        failure_count: Счетчик ошибок
        last_failure_time: Время последней ошибки
    
    Пример:
        >>> circuit_breaker = CircuitBreaker(
        ...     failure_threshold=5,
        ...     recovery_timeout=60
        ... )
        >>> 
        >>> result = await circuit_breaker.call(
        ...     call_llm_proxy,
        ...     model="gpt-4",
        ...     messages=[...]
        ... )
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        """
        Инициализация Circuit Breaker.
        
        Args:
            failure_threshold: Количество ошибок для открытия circuit
            recovery_timeout: Время до попытки восстановления (секунды)
            expected_exception: Тип исключения для отслеживания
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        
        logger.info(
            f"CircuitBreaker initialized "
            f"(threshold={failure_threshold}, timeout={recovery_timeout}s)"
        )
    
    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Вызвать функцию через Circuit Breaker.
        
        Args:
            func: Async функция для вызова
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Результат вызова функции
            
        Raises:
            Exception: Если circuit OPEN или функция вызвала ошибку
            
        Пример:
            >>> result = await circuit_breaker.call(
            ...     fetch_data,
            ...     url="https://api.example.com"
            ... )
        """
        # Проверить состояние circuit
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info("Circuit breaker entering HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
            else:
                logger.warning("Circuit breaker is OPEN, rejecting request")
                raise Exception(
                    f"Circuit breaker is OPEN. "
                    f"Service unavailable. "
                    f"Retry after {self.recovery_timeout} seconds."
                )
        
        # Попытаться выполнить функцию
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            logger.error(f"Circuit breaker recorded failure: {e}")
            raise
    
    def _on_success(self):
        """
        Обработать успешный вызов.
        
        Сбрасывает счетчик ошибок и переводит в CLOSED состояние.
        """
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker recovered, entering CLOSED state")
        
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """
        Обработать неудачный вызов.
        
        Увеличивает счетчик ошибок и открывает circuit при превышении порога.
        """
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        logger.warning(
            f"Circuit breaker failure count: {self.failure_count}/"
            f"{self.failure_threshold}"
        )
        
        if self.failure_count >= self.failure_threshold:
            logger.error(
                f"Circuit breaker threshold exceeded, entering OPEN state "
                f"for {self.recovery_timeout} seconds"
            )
            self.state = CircuitState.OPEN
    
    def _should_attempt_reset(self) -> bool:
        """
        Проверить, можно ли попытаться восстановить circuit.
        
        Returns:
            True если прошло достаточно времени с последней ошибки
        """
        if not self.last_failure_time:
            return False
        
        elapsed = datetime.now(timezone.utc) - self.last_failure_time
        return elapsed > timedelta(seconds=self.recovery_timeout)
    
    def get_state(self) -> CircuitState:
        """
        Получить текущее состояние circuit.
        
        Returns:
            Текущее состояние
        """
        return self.state
    
    def reset(self):
        """
        Принудительно сбросить circuit в CLOSED состояние.
        
        Используется для ручного восстановления.
        """
        logger.info("Circuit breaker manually reset to CLOSED state")
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
    
    def get_stats(self) -> dict:
        """
        Получить статистику circuit breaker.
        
        Returns:
            Словарь со статистикой
        """
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "recovery_timeout": self.recovery_timeout
        }
