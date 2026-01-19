"""
Retry механизм для Event Handlers.

Автоматически повторяет failed event handlers с экспоненциальной задержкой.
"""

import asyncio
import logging
from typing import Callable, Any
from functools import wraps

logger = logging.getLogger("agent-runtime.infrastructure.retry_handler")


class RetryHandler:
    """
    Обработчик с автоматическими повторами.
    
    Оборачивает event handler и автоматически повторяет
    выполнение при ошибках с экспоненциальной задержкой.
    
    Атрибуты:
        max_retries: Максимальное количество повторов
        base_delay: Базовая задержка между повторами (секунды)
        max_delay: Максимальная задержка (секунды)
        exponential_base: База для экспоненциального роста задержки
    
    Пример:
        >>> @RetryHandler(max_retries=3)
        >>> async def handle_event(event):
        ...     # Обработка события
        ...     pass
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        """
        Инициализация retry handler.
        
        Args:
            max_retries: Максимальное количество повторов
            base_delay: Базовая задержка (секунды)
            max_delay: Максимальная задержка (секунды)
            exponential_base: База для экспоненциального роста
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def __call__(self, func: Callable) -> Callable:
        """
        Декоратор для добавления retry логики.
        
        Args:
            func: Async функция для оборачивания
            
        Returns:
            Обернутая функция с retry логикой
        """
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            """Обертка с retry логикой"""
            last_exception = None
            
            for attempt in range(self.max_retries + 1):
                try:
                    # Попытка выполнить функцию
                    result = await func(*args, **kwargs)
                    
                    # Успех
                    if attempt > 0:
                        logger.info(
                            f"Handler {func.__name__} succeeded on attempt {attempt + 1}"
                        )
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Последняя попытка - пробросить ошибку
                    if attempt == self.max_retries:
                        logger.error(
                            f"Handler {func.__name__} failed after "
                            f"{self.max_retries + 1} attempts: {e}"
                        )
                        # TODO: Отправить в Dead Letter Queue
                        raise
                    
                    # Вычислить задержку с экспоненциальным ростом
                    delay = min(
                        self.base_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    
                    logger.warning(
                        f"Handler {func.__name__} failed (attempt {attempt + 1}/"
                        f"{self.max_retries + 1}), retrying in {delay:.1f}s: {e}"
                    )
                    
                    # Подождать перед следующей попыткой
                    await asyncio.sleep(delay)
            
            # Не должно достигаться, но на всякий случай
            raise last_exception
        
        return wrapper


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
):
    """
    Декоратор для добавления retry логики к функции.
    
    Args:
        max_retries: Максимальное количество повторов
        base_delay: Базовая задержка (секунды)
        max_delay: Максимальная задержка (секунды)
        
    Returns:
        Декоратор
        
    Пример:
        >>> @with_retry(max_retries=3, base_delay=1.0)
        >>> async def handle_critical_event(event):
        ...     # Критическая обработка события
        ...     await save_to_database(event)
    """
    return RetryHandler(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay
    )
