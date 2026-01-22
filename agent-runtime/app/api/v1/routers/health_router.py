"""
Health check роутер.

Предоставляет endpoint для проверки состояния сервиса.
"""

import logging
from fastapi import APIRouter

from ..schemas.health_schemas import HealthResponse
from ....core.config import AppConfig

logger = logging.getLogger("agent-runtime.api.health")

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Проверяет состояние сервиса и возвращает базовую информацию.
    
    Returns:
        HealthResponse: Статус сервиса
        
    Пример ответа:
        {
            "status": "healthy",
            "service": "agent-runtime",
            "version": "0.3.0"
        }
    """
    logger.debug("Health check called")
    
    return HealthResponse(
        status="healthy",
        service="agent-runtime",
        version=AppConfig.VERSION
    )
