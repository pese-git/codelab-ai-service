"""
Agent Runtime Service - Main application entry point.

FastAPI application for AI agent runtime with LLM integration and tool execution.
"""
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.v1.endpoints import router as v1_router
from app.middleware.internal_auth import InternalAuthMiddleware
from app.core.config import AppConfig

# Create FastAPI application
app = FastAPI(
    title="Agent Runtime Service",
    version=AppConfig.VERSION,
    description="AI Agent Runtime with LLM integration and tool execution support"
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
