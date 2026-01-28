"""
LLM Client для взаимодействия с LLM провайдерами.

Предоставляет абстракцию над конкретными LLM API (OpenAI, Anthropic, etc.)
через LiteLLM Proxy.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from ...domain.entities.llm_response import LLMResponse, ToolCall, TokenUsage
from ...core.config import AppConfig

logger = logging.getLogger("agent-runtime.infrastructure.llm_client")


class LLMClient(ABC):
    """
    Абстрактный интерфейс LLM клиента.
    
    Определяет контракт для взаимодействия с LLM провайдерами.
    Конкретные реализации должны наследоваться от этого класса.
    
    Пример:
        >>> client = LLMProxyClient(base_url="http://localhost:4000")
        >>> response = await client.chat_completion(
        ...     model="gpt-4",
        ...     messages=[{"role": "user", "content": "Hello"}],
        ...     tools=[]
        ... )
        >>> print(response.content)
    """
    
    @abstractmethod
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Выполнить chat completion запрос к LLM.
        
        Args:
            model: Имя модели (например, "gpt-4", "claude-3-opus")
            messages: История сообщений в формате OpenAI
            tools: Список доступных инструментов в формате OpenAI
            stream: Использовать ли стриминг (пока не поддерживается)
            temperature: Температура генерации (0.0-2.0)
            max_tokens: Максимальное количество токенов в ответе
            
        Returns:
            LLMResponse: Доменный объект ответа LLM
            
        Raises:
            LLMClientError: При ошибке вызова LLM API
        """
        pass


class LLMProxyClient(LLMClient):
    """
    Реализация LLM клиента через LiteLLM Proxy.
    
    Использует LiteLLM Proxy для унифицированного доступа
    к различным LLM провайдерам (OpenAI, Anthropic, etc.).
    
    Атрибуты:
        _base_url: URL LiteLLM Proxy сервера
        _api_key: API ключ для аутентификации (опционально)
        _timeout: Таймаут запросов в секундах
    
    Пример:
        >>> client = LLMProxyClient(
        ...     base_url="http://localhost:4000",
        ...     api_key="sk-...",
        ...     timeout=60
        ... )
        >>> response = await client.chat_completion(...)
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 360
    ):
        """
        Инициализация LLM Proxy клиента.
        
        Args:
            base_url: URL LiteLLM Proxy (по умолчанию из конфига)
            api_key: Internal API key для аутентификации (по умолчанию из конфига)
            timeout: Таймаут запросов в секундах
        """
        self._base_url = base_url or AppConfig.LLM_PROXY_URL
        # Используем INTERNAL_API_KEY как в старом клиенте
        self._api_key = api_key or AppConfig.INTERNAL_API_KEY
        self._timeout = timeout
        
        # Импортируем httpx здесь, чтобы не создавать зависимость на уровне модуля
        import httpx
        self._http_client = httpx.AsyncClient(
            timeout=self._timeout
        )
        
        logger.info(f"LLMProxyClient initialized with base_url={self._base_url}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Получить заголовки для HTTP запросов"""
        headers = {
            "Content-Type": "application/json"
        }
        
        # Используем X-Internal-Auth как в старом клиенте
        if self._api_key:
            headers["X-Internal-Auth"] = self._api_key
        
        return headers
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Выполнить chat completion через LiteLLM Proxy.
        
        Args:
            model: Имя модели
            messages: История сообщений
            tools: Список инструментов
            stream: Стриминг (пока не поддерживается)
            temperature: Температура генерации
            max_tokens: Максимум токенов
            
        Returns:
            LLMResponse: Доменный объект ответа
            
        Raises:
            LLMClientError: При ошибке API
        """
        try:
            # Подготовка запроса
            request_data = {
                "model": model,
                "messages": messages,
                "stream": stream
            }
            
            if tools:
                request_data["tools"] = tools
            
            if temperature is not None:
                request_data["temperature"] = temperature
            
            if max_tokens is not None:
                request_data["max_tokens"] = max_tokens
            
            logger.debug(
                f"Calling LLM: model={model}, messages={len(messages)}, "
                f"tools={len(tools)}"
            )
            
            # Вызов API (с префиксом /v1 как в старом клиенте)
            response = await self._http_client.post(
                f"{self._base_url}/v1/chat/completions",
                json=request_data,
                headers=self._get_headers()
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            logger.debug(f"LLM response received: {len(str(response_data))} chars")
            
            # Парсинг ответа
            return self._parse_response(response_data, model)
            
        except Exception as e:
            logger.error(f"Error calling LLM API: {e}", exc_info=True)
            raise LLMClientError(f"Failed to call LLM API: {e}") from e
    
    def _parse_response(
        self,
        data: Dict[str, Any],
        model: str
    ) -> LLMResponse:
        """
        Парсинг ответа LLM API в доменный объект.
        
        Args:
            data: JSON ответ от LLM API
            model: Имя модели (fallback если не в ответе)
            
        Returns:
            LLMResponse: Доменный объект
        """
        try:
            # Извлечение message из choices
            message = data["choices"][0]["message"]
            
            # Парсинг content
            content = message.get("content", "")
            if content is None:
                content = ""
            
            # Парсинг tool_calls
            tool_calls = []
            if "tool_calls" in message and message["tool_calls"]:
                for tc in message["tool_calls"]:
                    # Парсинг arguments (может быть строкой или dict)
                    arguments = tc["function"]["arguments"]
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            logger.warning(
                                f"Failed to parse tool arguments as JSON: {arguments}"
                            )
                            arguments = {}
                    
                    tool_call = ToolCall(
                        id=tc["id"],
                        tool_name=tc["function"]["name"],
                        arguments=arguments
                    )
                    tool_calls.append(tool_call)
            
            # Парсинг usage (может быть None для некоторых провайдеров)
            usage_data = data.get("usage") or {}
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0) if isinstance(usage_data, dict) else 0,
                completion_tokens=usage_data.get("completion_tokens", 0) if isinstance(usage_data, dict) else 0,
                total_tokens=usage_data.get("total_tokens", 0) if isinstance(usage_data, dict) else 0
            )
            
            # Извлечение finish_reason
            finish_reason = data["choices"][0].get("finish_reason")
            
            # Извлечение model (может отличаться от запрошенного)
            response_model = data.get("model", model)
            
            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                usage=usage,
                model=response_model,
                finish_reason=finish_reason
            )
            
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error parsing LLM response: {e}", exc_info=True)
            raise LLMClientError(f"Failed to parse LLM response: {e}") from e
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self._http_client.aclose()
        logger.debug("LLMProxyClient closed")


class LLMClientError(Exception):
    """Исключение при ошибке LLM клиента"""
    pass
