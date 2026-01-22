"""
API схемы для health check.

Определяет структуру ответа health check endpoint.
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Ответ health check endpoint.
    
    Атрибуты:
        status: Статус сервиса (healthy, degraded, unhealthy)
        service: Название сервиса
        version: Версия сервиса
    
    Пример:
        {
            "status": "healthy",
            "service": "agent-runtime",
            "version": "0.3.0"
        }
    """
    
    status: str = Field(description="Статус сервиса")
    service: str = Field(description="Название сервиса")
    version: str = Field(description="Версия сервиса")
