"""
Agent Runtime Service - Main application entry point.

FastAPI application for AI agent runtime with LLM integration and tool execution.
Multi-agent system with specialized agents for different tasks.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.v1.routers import (
    health_router,
    sessions_router,
    agents_router,
    messages_router,
    events_router
)
from app.api.middleware.internal_auth import InternalAuthMiddleware
from app.api.middleware import RateLimitMiddleware
from app.core.config import AppConfig, logger

# Глобальные экземпляры адаптеров (инициализируются в lifespan)
session_manager_adapter = None
agent_context_manager_adapter = None
message_orchestration_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting Agent Runtime Service...")
    logger.info(f"Version: {AppConfig.VERSION}")
    
    # Startup logic
    try:
        # Initialize Event Bus and subscribers
        from app.events.subscribers import (
            metrics_collector,
            audit_logger,
            agent_context_subscriber,
            session_metrics_collector
        )
        
        # Start session metrics collector
        await session_metrics_collector.start()
        
        logger.info("✓ Event Bus initialized with subscribers")
        logger.info("✓ Event-driven architecture fully active (Phase 4)")
        logger.info("✓ Persistence handled by domain services (immediate)")
        logger.info("✓ Session metrics collector active")
        
        # Initialize database
        from app.services.database import init_database, init_db
        init_database(AppConfig.DB_URL)
        await init_db()
        logger.info("✓ Database initialized")
        
        # Initialize multi-agent system
        from app.agents import initialize_agents
        initialize_agents()
        logger.info("✓ Multi-agent system initialized")
        
        # Управление сессиями и контекстом через адаптеры
        # Адаптеры обеспечивают обратную совместимость с новыми доменными сервисами
        # Персистентность обрабатывается доменными сервисами (SessionManagementService, AgentOrchestrationService)
        logger.info("✓ Session/context management via new architecture (adapters)")
        
        # Инициализация адаптеров для новой архитектуры
        # ВАЖНО: Не используем database session при startup, так как адаптеры
        # будут использоваться с request-scoped сессиями через dependency injection
        from app.infrastructure.adapters import (
            SessionManagerAdapter,
            AgentContextManagerAdapter
        )
        from app.domain.services import (
            SessionManagementService,
            AgentOrchestrationService
        )
        from app.infrastructure.cleanup import SessionCleanupService
        from app.core.dependencies import get_event_publisher
        from app.services.database import get_db
        
        try:
            # Получить singleton event publisher
            event_publisher = get_event_publisher()
            
            # ПРИМЕЧАНИЕ: Мы НЕ создаем репозитории и сервисы здесь,
            # так как они требуют database session, которая должна быть request-scoped.
            # Вместо этого, глобальные адаптеры будут None, и мы будем использовать
            # dependency injection в роутерах для получения сервисов с правильной сессией.
            
            # Установить глобальные адаптеры в None (будут использоваться через DI)
            global session_manager_adapter, agent_context_manager_adapter, message_orchestration_service
            session_manager_adapter = None
            agent_context_manager_adapter = None
            message_orchestration_service = None
            
            logger.info("✓ Manager adapters will be initialized per-request via dependency injection")
            
            # Initialize session cleanup service
            # Cleanup service создает свои собственные database sessions по мере необходимости
            from app.infrastructure.persistence.repositories import SessionRepositoryImpl
            from app.infrastructure.persistence.database import async_session_maker
            
            # Создаем cleanup service с фабрикой для создания сессий
            # Он будет создавать свои собственные сессии при каждом запуске cleanup
            async def get_cleanup_session_service():
                """Фабрика для создания session service с новой DB сессией"""
                async with async_session_maker() as db:
                    cleanup_repo = SessionRepositoryImpl(db)
                    return SessionManagementService(
                        repository=cleanup_repo,
                        event_publisher=event_publisher.publish
                    )
            
            # Создаем временную сессию только для инициализации cleanup service
            db_gen = get_db()
            db = await db_gen.__anext__()
            try:
                cleanup_repo = SessionRepositoryImpl(db)
                cleanup_session_service = SessionManagementService(
                    repository=cleanup_repo,
                    event_publisher=event_publisher.publish
                )
                
                cleanup_service = SessionCleanupService(
                    session_service=cleanup_session_service,
                    cleanup_interval_hours=1,
                    max_age_hours=24
                )
                await cleanup_service.start()
                logger.info("✓ Session cleanup service started")
            finally:
                # Правильно закрываем генератор сессии
                try:
                    await db_gen.aclose()
                except Exception:
                    pass
                
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}", exc_info=True)
            session_manager_adapter = None
            agent_context_manager_adapter = None
            message_orchestration_service = None
            cleanup_service = None
        
        # Publish system startup event
        from app.events.event_bus import event_bus
        from app.events.base_event import BaseEvent
        from app.events.event_types import EventType, EventCategory
        await event_bus.publish(
            BaseEvent(
                event_type=EventType.SYSTEM_STARTUP,
                event_category=EventCategory.SYSTEM,
                data={"version": AppConfig.VERSION},
                source="main"
            )
        )
        logger.info("✓ System startup event published")
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down Agent Runtime Service...")
    
    # Персистентность обрабатывается доменными сервисами напрямую (подписчик не нужен)
    logger.info("✓ Persistence handled by domain services (no subscriber needed)")
    
    # Publish system shutdown event
    try:
        from app.events.event_bus import event_bus
        from app.events.base_event import BaseEvent
        from app.events.event_types import EventType, EventCategory
        await event_bus.publish(
            BaseEvent(
                event_type=EventType.SYSTEM_SHUTDOWN,
                event_category=EventCategory.SYSTEM,
                data={},
                source="main"
            ),
            wait_for_handlers=True  # Wait for handlers to complete
        )
        logger.info("✓ System shutdown event published")
    except Exception as e:
        logger.error(f"Error publishing shutdown event: {e}")
    
    # Shutdown cleanup service
    try:
        if 'cleanup_service' in locals() and cleanup_service:
            await cleanup_service.stop()
            logger.info("✓ Session cleanup service stopped")
    except Exception as e:
        logger.error(f"Error stopping cleanup service: {e}")
    
    # Shutdown обрабатывается репозиториями в новой архитектуре
    logger.info("✓ Session/context managers shutdown (managed by new architecture)")
    
    # Close database
    from app.services.database import close_db
    await close_db()
    logger.info("✓ Database closed")


# Create FastAPI application (agents will be initialized in lifespan)
app = FastAPI(
    title="Agent Runtime Service",
    version=AppConfig.VERSION,
    description="AI Agent Runtime with LLM integration and tool execution support",
    lifespan=lifespan,
)


def custom_openapi():
    """
    Customize OpenAPI schema to include internal authentication.
    
    Adds X-Internal-Auth security scheme to all endpoints.
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add X-Internal-Auth security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "XInternalAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "x-internal-auth"
        }
    }
    
    # Apply security globally to all endpoints
    openapi_schema["security"] = [{"XInternalAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Override OpenAPI schema generator
app.openapi = custom_openapi  # type: ignore[assignment]

# Add middleware
app.add_middleware(InternalAuthMiddleware)

# Add rate limiting middleware (60 requests per minute per client)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=60
)

# Include API routers
# Новые структурированные роутеры
app.include_router(health_router)
app.include_router(sessions_router)
app.include_router(agents_router)
app.include_router(messages_router)
app.include_router(events_router)

logger.info("✓ API routers registered")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True
    )
