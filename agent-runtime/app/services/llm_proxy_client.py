"""
LLM Proxy Client for agent runtime.

Handles communication with LLM Proxy service via REST API.
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import AppConfig

logger = logging.getLogger("agent-runtime.llm_proxy_client")


class LLMProxyClient:
    """
    Client for communicating with LLM Proxy service.
    
    Encapsulates REST API calls to LLM Proxy for chat completions.
    """

    def __init__(
        self, 
        api_url: Optional[str] = None, 
        api_key: Optional[str] = None,
        timeout: float = 360.0
    ):
        """
        Initialize LLM Proxy client.
        
        Args:
            api_url: LLM Proxy service URL (default from config)
            api_key: Internal API key for authentication (default from config)
            timeout: Request timeout in seconds
        """
        self.api_url = api_url or AppConfig.LLM_PROXY_URL
        self.api_key = api_key or AppConfig.INTERNAL_API_KEY
        self.timeout = timeout

    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send chat completion request to LLM Proxy.
        
        Args:
            model: Model identifier
            messages: List of message dictionaries
            tools: Optional list of tool specifications
            stream: Whether to stream the response
            extra_params: Additional parameters for the request
            
        Returns:
            LLM response as dictionary
            
        Raises:
            httpx.HTTPError: If request fails
        """
        # Build request payload
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream
        }
        
        if tools:
            payload["tools"] = tools
        
        if extra_params:
            payload.update(extra_params)

        logger.info(
            f"Sending chat completion request: model={model}, "
            f"messages={len(messages)}, stream={stream}"
        )
        logger.debug(f"Request payload keys: {list(payload.keys())}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/v1/chat/completions",
                    json=payload,
                    headers={"X-Internal-Auth": self.api_key},
                    timeout=self.timeout,
                )
            
            response.raise_for_status()
            
            result = response.json()
            
            logger.info(
                f"Received LLM response: status={response.status_code}, "
                f"choices={len(result.get('choices', []))}"
            )
            logger.debug(f"Response preview: {str(result)[:200]}...")
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(
                f"HTTP error in chat_completion: {e}",
                exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in chat_completion: {e}",
                exc_info=True
            )
            raise


# Singleton instance for global use
llm_proxy_client = LLMProxyClient()
