import logging

from fastapi import FastAPI

logger = logging.getLogger("llm-proxy")
from fastapi.openapi.utils import get_openapi

from app.api.v1.endpoints import router as router
from app.middleware.internal_auth import InternalAuthMiddleware
from app.models.schemas import HealthResponse

app = FastAPI(
    title="LLM Proxy Service",
    swagger_ui_init_oauth={},
    openapi_tags=[],  # если есть
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Добавляем схему X-Internal-Auth
    openapi_schema["components"]["securitySchemes"] = {
        "XInternalAuth": {"type": "apiKey", "in": "header", "name": "x-internal-auth"}
    }
    # Настроить всю security глобально для эндпоинтов по желанию:
    openapi_schema["security"] = [{"XInternalAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # Переопределить openapi-генератор  # ty:ignore[invalid-assignment]

# Подключение middleware
app.add_middleware(InternalAuthMiddleware)


app.include_router(router)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    logger.info("[LLM Proxy] Health check called")
    return HealthResponse.model_construct(status="healthy", service="llm-proxy", version="0.1.0")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, log_level="info", reload=True)
