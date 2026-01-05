from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.v1.endpoints import router as v1_router
from app.core.config import AppConfig
from app.middleware.internal_auth import InternalAuthMiddleware
from app.middleware.jwt_auth import HybridAuthMiddleware
from app.models.rest import HealthResponse

app = FastAPI(title="Gateway Service")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint в корне приложения для Docker healthcheck"""
    return HealthResponse.model_construct(
        status="healthy", service="gateway", version=AppConfig.VERSION
    )


def custom_openapi():
    """
    Customize OpenAPI schema to include authentication.
    
    Adds security schemes for both JWT and X-Internal-Auth.
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
        "XInternalAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "x-internal-auth",
        },
    }
    
    # Apply security globally (either JWT or Internal Auth)
    openapi_schema["security"] = [{"BearerAuth": []}, {"XInternalAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Override OpenAPI schema generator
app.openapi = custom_openapi  # type: ignore[assignment]

# Подключение middleware авторизации
config = AppConfig()
if config.USE_JWT_AUTH:
    # Use hybrid middleware (JWT + X-Internal-Auth)
    app.add_middleware(
        HybridAuthMiddleware,
        jwks_url=config.JWKS_URL,
        internal_api_key=config.INTERNAL_API_KEY,
    )
else:
    # Use only X-Internal-Auth (legacy)
    app.add_middleware(InternalAuthMiddleware)

# Подключение роутов API v1
app.include_router(v1_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info", reload=True)
