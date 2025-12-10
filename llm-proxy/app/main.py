from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.utils import get_openapi

from app.api.v1.endpoints import router as v1_router
from app.middleware.internal_auth import InternalAuthMiddleware

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


app.openapi = custom_openapi  # Переопределить openapi-генератор

# Подключение middleware
app.add_middleware(InternalAuthMiddleware)

# Подключение эндпоинтов API v1
app.include_router(v1_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, log_level="info", reload=True)
