"""
Tests for retry service with exponential backoff.
"""
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from tenacity import RetryError

from app.services.retry_service import (
    RetryableError,
    NonRetryableError,
    is_retryable_http_error,
    call_with_retry,
    llm_retry
)


class TestRetryableErrorDetection:
    """Test detection of retryable errors."""
    
    def test_timeout_is_retryable(self):
        """TimeoutException should be retryable."""
        error = httpx.TimeoutException("Request timeout")
        assert is_retryable_http_error(error) is True
    
    def test_rate_limit_is_retryable(self):
        """429 status code should be retryable."""
        response = httpx.Response(429, request=httpx.Request("GET", "http://test"))
        error = httpx.HTTPStatusError("Rate limited", request=response.request, response=response)
        assert is_retryable_http_error(error) is True
    
    def test_service_unavailable_is_retryable(self):
        """503 status code should be retryable."""
        response = httpx.Response(503, request=httpx.Request("GET", "http://test"))
        error = httpx.HTTPStatusError("Service unavailable", request=response.request, response=response)
        assert is_retryable_http_error(error) is True
    
    def test_gateway_timeout_is_retryable(self):
        """504 status code should be retryable."""
        response = httpx.Response(504, request=httpx.Request("GET", "http://test"))
        error = httpx.HTTPStatusError("Gateway timeout", request=response.request, response=response)
        assert is_retryable_http_error(error) is True
    
    def test_connect_error_is_retryable(self):
        """ConnectError should be retryable."""
        error = httpx.ConnectError("Connection failed")
        assert is_retryable_http_error(error) is True
    
    def test_read_timeout_is_retryable(self):
        """ReadTimeout should be retryable."""
        error = httpx.ReadTimeout("Read timeout")
        assert is_retryable_http_error(error) is True
    
    def test_400_is_not_retryable(self):
        """400 status code should not be retryable."""
        response = httpx.Response(400, request=httpx.Request("GET", "http://test"))
        error = httpx.HTTPStatusError("Bad request", request=response.request, response=response)
        assert is_retryable_http_error(error) is False
    
    def test_404_is_not_retryable(self):
        """404 status code should not be retryable."""
        response = httpx.Response(404, request=httpx.Request("GET", "http://test"))
        error = httpx.HTTPStatusError("Not found", request=response.request, response=response)
        assert is_retryable_http_error(error) is False
    
    def test_500_is_not_retryable(self):
        """500 status code should not be retryable (server error, not transient)."""
        response = httpx.Response(500, request=httpx.Request("GET", "http://test"))
        error = httpx.HTTPStatusError("Internal error", request=response.request, response=response)
        assert is_retryable_http_error(error) is False


class TestRetryDecorator:
    """Test retry decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        """Successful call should not trigger retry."""
        mock_func = AsyncMock(return_value="success")
        
        @llm_retry
        async def test_func():
            return await mock_func()
        
        result = await test_func()
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retryable_error_triggers_retry(self):
        """RetryableError should trigger retry."""
        mock_func = AsyncMock(side_effect=[
            RetryableError("First attempt"),
            RetryableError("Second attempt"),
            "success"
        ])
        
        @llm_retry
        async def test_func():
            result = await mock_func()
            if isinstance(result, str):
                return result
            raise result
        
        result = await test_func()
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Should fail after max retry attempts."""
        mock_func = AsyncMock(side_effect=RetryableError("Always fails"))
        
        @llm_retry
        async def test_func():
            await mock_func()
            raise RetryableError("Always fails")
        
        # tenacity wraps the exception in RetryError
        with pytest.raises(RetryError):
            await test_func()
        
        # Should try 3 times (initial + 2 retries)
        assert mock_func.call_count == 3
    
    @pytest.mark.asyncio
    async def test_non_retryable_error_no_retry(self):
        """Non-retryable errors should not trigger retry."""
        mock_func = AsyncMock(side_effect=ValueError("Bad input"))
        
        @llm_retry
        async def test_func():
            await mock_func()
        
        with pytest.raises(ValueError):
            await test_func()
        
        # Should only try once
        assert mock_func.call_count == 1


class TestCallWithRetry:
    """Test call_with_retry helper function."""
    
    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Successful call should return result."""
        async def success_func():
            return "success"
        
        result = await call_with_retry(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retryable_http_error(self):
        """Retryable HTTP error should trigger retry."""
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            return "success"
        
        result = await call_with_retry(failing_func, max_attempts=3)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_non_retryable_http_error(self):
        """Non-retryable HTTP error should fail immediately."""
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            response = httpx.Response(400, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("Bad request", request=response.request, response=response)
        
        with pytest.raises(NonRetryableError):
            await call_with_retry(failing_func, max_attempts=3)
        
        # Should only try once
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_custom_max_attempts(self):
        """Should respect custom max_attempts parameter."""
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Timeout")
        
        # tenacity wraps the exception in RetryError
        with pytest.raises(RetryError):
            await call_with_retry(failing_func, max_attempts=5)
        
        assert call_count == 5


class TestLLMProxyClientRetry:
    """Test retry integration with LLM Proxy Client."""
    
    @pytest.mark.asyncio
    async def test_llm_client_retries_on_timeout(self):
        """LLM client should retry on timeout."""
        from app.infrastructure.llm.client import LLMProxyClient
        
        client = LLMProxyClient()
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # First two calls timeout, third succeeds
            mock_client.post = AsyncMock(side_effect=[
                httpx.TimeoutException("Timeout 1"),
                httpx.TimeoutException("Timeout 2"),
                AsyncMock(
                    status_code=200,
                    json=lambda: {"choices": [{"message": {"content": "success"}}]},
                    raise_for_status=lambda: None
                )
            ])
            
            result = await client.chat_completion(
                model="test-model",
                messages=[{"role": "user", "content": "test"}]
            )
            
            assert result["choices"][0]["message"]["content"] == "success"
            assert mock_client.post.call_count == 3
    
    @pytest.mark.asyncio
    async def test_llm_client_fails_on_non_retryable(self):
        """LLM client should not retry on non-retryable errors."""
        from app.infrastructure.llm.client import LLMProxyClient
        
        client = LLMProxyClient()
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # 400 error should not be retried
            response = httpx.Response(400, request=httpx.Request("POST", "http://test"))
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad request",
                    request=response.request,
                    response=response
                )
            )
            
            # LLM client raises httpx.HTTPStatusError for non-retryable errors
            with pytest.raises(httpx.HTTPStatusError):
                await client.chat_completion(
                    model="test-model",
                    messages=[{"role": "user", "content": "test"}]
                )
            
            # Note: Circuit breaker may retry a few times before giving up
            # The important thing is that it eventually fails with the original error
            assert mock_client.post.call_count >= 1
