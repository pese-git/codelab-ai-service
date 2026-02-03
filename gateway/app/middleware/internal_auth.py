from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import config, logger


class InternalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Публичные endpoints без аутентификации
        public_paths = (
            "/health",
            "/api/v1/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        )
        
        # Разрешить WebSocket соединения и публичные пути
        if request.url.path in public_paths or request.url.path.startswith("/ws/"):
            return await call_next(request)
        
        # Для всех остальных endpoints требуется аутентификация
        auth = request.headers.get("x-internal-auth")
        logger.debug(
            f"[gateway][AUTH] Incoming X-Internal-Auth: '{auth}', INTERNAL_API_KEY: '{config.internal_api_key}'"
        )
        if auth != config.internal_api_key:
            logger.warning(
                f"[gateway][AUTH_FAIL] Unauthorized: header='{auth}' != key='{config.internal_api_key}'"
            )
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)
