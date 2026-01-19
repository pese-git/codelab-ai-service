"""
Rate Limiting middleware.

Ограничивает частоту запросов для защиты от перегрузки и DDoS.
"""

import time
import logging
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("agent-runtime.middleware.rate_limit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware для ограничения частоты запросов.
    
    Отслеживает количество запросов от каждого клиента
    и блокирует при превышении лимита.
    
    Атрибуты:
        requests_per_minute: Максимальное количество запросов в минуту
        requests: История запросов по клиентам
    
    Пример использования:
        >>> app.add_middleware(
        ...     RateLimitMiddleware,
        ...     requests_per_minute=60
        ... )
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        """
        Инициализация middleware.
        
        Args:
            app: FastAPI приложение
            requests_per_minute: Лимит запросов в минуту (default: 60)
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[float]] = defaultdict(list)
        logger.info(
            f"RateLimitMiddleware initialized "
            f"(limit: {requests_per_minute} req/min)"
        )
    
    async def dispatch(self, request: Request, call_next):
        """
        Обработать запрос с проверкой rate limit.
        
        Args:
            request: HTTP запрос
            call_next: Следующий обработчик в цепочке
            
        Returns:
            HTTP ответ
            
        Raises:
            HTTPException 429: Если превышен лимит запросов
        """
        # Получить идентификатор клиента (IP адрес)
        client_id = request.client.host if request.client else "unknown"
        
        # Текущее время
        now = time.time()
        
        # Очистить старые запросы (старше 60 секунд)
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < 60
        ]
        
        # Проверить лимит
        if len(self.requests[client_id]) >= self.requests_per_minute:
            logger.warning(
                f"Rate limit exceeded for client {client_id}: "
                f"{len(self.requests[client_id])} requests in last minute"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Too many requests",
                    "limit": self.requests_per_minute,
                    "window": "1 minute",
                    "retry_after": 60
                }
            )
        
        # Добавить текущий запрос
        self.requests[client_id].append(now)
        
        # Логировать если близко к лимиту
        if len(self.requests[client_id]) > self.requests_per_minute * 0.8:
            logger.warning(
                f"Client {client_id} approaching rate limit: "
                f"{len(self.requests[client_id])}/{self.requests_per_minute}"
            )
        
        # Продолжить обработку
        response = await call_next(request)
        
        # Добавить заголовки с информацией о лимите
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - len(self.requests[client_id])
        )
        response.headers["X-RateLimit-Reset"] = str(int(now + 60))
        
        return response
    
    async def cleanup(self):
        """
        Очистить историю запросов.
        
        Удаляет старые записи для освобождения памяти.
        Должен вызываться периодически.
        """
        now = time.time()
        cleaned = 0
        
        for client_id in list(self.requests.keys()):
            # Очистить старые запросы
            old_count = len(self.requests[client_id])
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if now - req_time < 60
            ]
            
            # Удалить клиента если нет активных запросов
            if not self.requests[client_id]:
                del self.requests[client_id]
                cleaned += 1
        
        if cleaned > 0:
            logger.debug(f"Cleaned up {cleaned} inactive clients from rate limiter")
