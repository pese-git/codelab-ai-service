"""
Agent Runtime Service - Main application entry point.

FastAPI application for AI agent runtime with LLM integration and tool execution.
Multi-agent system with specialized agents for different tasks.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.v1.endpoints import router as v1_router
from app.middleware.internal_auth import InternalAuthMiddleware
from app.core.config import AppConfig, logger


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
            init_agent_context_subscriber
        )
        logger.info("✓ Event Bus initialized with subscribers")
        
        # Initialize agent context subscriber (Phase 3)
        init_agent_context_subscriber()
        if AppConfig.USE_EVENT_DRIVEN_CONTEXT:
            logger.info("✓ Event-driven context updates ENABLED")
        else:
            logger.info("ℹ Event-driven context updates DISABLED (using direct calls)")
        
        # Initialize database
        from app.services.database import init_database, init_db
        init_database(AppConfig.DB_URL)
        await init_db()
        logger.info("✓ Database initialized")
        
        # Initialize async session manager
        from app.services.session_manager_async import init_session_manager
        await init_session_manager()
        logger.info("✓ Session manager initialized")
        
        # Initialize async agent context manager
        from app.services.agent_context_async import init_agent_context_manager
        await init_agent_context_manager()
        logger.info("✓ Agent context manager initialized")
        
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
    
    # Shutdown managers (flush pending writes)
    try:
        from app.services.session_manager_async import session_manager
        from app.services.agent_context_async import agent_context_manager
        
        if session_manager:
            await session_manager.shutdown()
            logger.info("✓ Session manager shutdown")
        
        if agent_context_manager:
            await agent_context_manager.shutdown()
            logger.info("✓ Agent context manager shutdown")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    # Close database
    from app.services.database import close_db
    await close_db()
    logger.info("✓ Database closed")


# Initialize multi-agent system
import app.agents  # This will register all agents

# Create FastAPI application
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

# Include API routers
app.include_router(v1_router)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True
    )
