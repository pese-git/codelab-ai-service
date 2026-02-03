"""
Сервис для проксирования запросов в Agent Runtime.

Устраняет дублирование кода в proxy endpoints через единую точку
обработки HTTP запросов и ошибок.
"""

import logging
from typing import Optional, Dict, Any

import httpx
from fastapi.responses import JSONResponse

logger = logging.getLogger("gateway.proxy")


class AgentRuntimeProxy:
    """Сервис для проксирования запросов в Agent Runtime."""
    
    def __init__(
        self,
        base_url: str,
        internal_api_key: str,
        timeout: float = 30.0
    ):
        """
        Инициализация прокси сервиса.
        
        Args:
            base_url: Базовый URL Agent Runtime
            internal_api_key: Ключ для внутренней аутентификации
            timeout: Таймаут для запросов (по умолчанию 30 сек)
        """
        self._base_url = base_url.rstrip('/')
        self._internal_api_key = internal_api_key
        self._timeout = timeout
    
    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """
        Проксировать GET запрос в Agent Runtime.
        
        Args:
            path: Путь endpoint (например, "/agents")
            params: Query параметры (опционально)
            
        Returns:
            JSONResponse с данными от Agent Runtime или ошибкой
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                url = f"{self._base_url}{path}"
                logger.debug(f"Proxying GET {url}")
                
                response = await client.get(
                    url,
                    params=params,
                    headers={"X-Internal-Auth": self._internal_api_key},
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                return self._handle_http_error(e, "GET", path)
            except Exception as e:
                return self._handle_generic_error(e, "GET", path)
    
    async def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """
        Проксировать POST запрос в Agent Runtime.
        
        Args:
            path: Путь endpoint (например, "/sessions")
            json: JSON данные для отправки (опционально)
            
        Returns:
            JSONResponse с данными от Agent Runtime или ошибкой
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                url = f"{self._base_url}{path}"
                logger.debug(f"Proxying POST {url}")
                
                response = await client.post(
                    url,
                    json=json,
                    headers={"X-Internal-Auth": self._internal_api_key},
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                return self._handle_http_error(e, "POST", path)
            except Exception as e:
                return self._handle_generic_error(e, "POST", path)
    
    def _handle_http_error(
        self,
        e: httpx.HTTPStatusError,
        method: str,
        path: str
    ) -> JSONResponse:
        """
        Обработать HTTP ошибку от Agent Runtime.
        
        Args:
            e: HTTP ошибка
            method: HTTP метод (GET, POST)
            path: Путь endpoint
            
        Returns:
            JSONResponse с информацией об ошибке
        """
        logger.error(
            f"Agent Runtime error [{method} {path}]: "
            f"status={e.response.status_code}, body={e.response.text}"
        )
        return JSONResponse(
            status_code=e.response.status_code,
            content={
                "error": f"Agent Runtime error: {e.response.status_code}",
                "detail": e.response.text if e.response.text else None
            }
        )
    
    def _handle_generic_error(
        self,
        e: Exception,
        method: str,
        path: str
    ) -> JSONResponse:
        """
        Обработать общую ошибку при проксировании.
        
        Args:
            e: Исключение
            method: HTTP метод (GET, POST)
            path: Путь endpoint
            
        Returns:
            JSONResponse с информацией об ошибке
        """
        logger.error(
            f"Error proxying to Agent Runtime [{method} {path}]: {e}",
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Gateway error",
                "detail": str(e)
            }
        )
