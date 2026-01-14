"""
Retry service with exponential backoff for handling transient failures.

Provides retry mechanisms for LLM calls and other external service interactions.
"""
import logging
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import httpx

logger = logging.getLogger("agent-runtime.retry_service")

T = TypeVar('T')


class RetryableError(Exception):
    """Exception that indicates an operation can be retried."""
    pass


class NonRetryableError(Exception):
    """Exception that indicates an operation should not be retried."""
    pass


def is_retryable_http_error(exception: Exception) -> bool:
    """
    Determine if an HTTP error is retryable.
    
    Args:
        exception: Exception to check
        
    Returns:
        True if the error is retryable, False otherwise
    """
    if isinstance(exception, httpx.TimeoutException):
        return True
    
    if isinstance(exception, httpx.HTTPStatusError):
        # Retry on rate limit, service unavailable, gateway timeout
        status_code = exception.response.status_code
        return status_code in [429, 503, 504]
    
    if isinstance(exception, httpx.ConnectError):
        return True
    
    if isinstance(exception, httpx.ReadTimeout):
        return True
    
    return False


def create_retry_decorator(
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 10.0,
    multiplier: float = 1.0
):
    """
    Create a retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        multiplier: Multiplier for exponential backoff
        
    Returns:
        Retry decorator
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(RetryableError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG)
    )


# Default retry decorator for LLM calls
llm_retry = create_retry_decorator(
    max_attempts=3,
    min_wait=2.0,
    max_wait=10.0,
    multiplier=1.0
)


async def call_with_retry(
    func: Callable[..., Any],
    *args,
    max_attempts: int = 3,
    **kwargs
) -> Any:
    """
    Call an async function with retry logic.
    
    Args:
        func: Async function to call
        *args: Positional arguments for the function
        max_attempts: Maximum number of attempts
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function call
        
    Raises:
        RetryableError: If all retry attempts fail
        NonRetryableError: If a non-retryable error occurs
    """
    retry_decorator = create_retry_decorator(max_attempts=max_attempts)
    
    @retry_decorator
    async def _wrapped():
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if is_retryable_http_error(e):
                logger.warning(f"Retryable error occurred: {e}")
                raise RetryableError(f"Retryable error: {e}") from e
            else:
                logger.error(f"Non-retryable error occurred: {e}")
                raise NonRetryableError(f"Non-retryable error: {e}") from e
    
    return await _wrapped()
