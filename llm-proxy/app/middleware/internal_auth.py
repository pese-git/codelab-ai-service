from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import AppConfig, logger


class InternalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        public_paths = {"/health", "/llm/models", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}
        if request.url.path in public_paths:
            return await call_next(request)
        auth = request.headers.get("x-internal-auth")
        logger.debug(
            f"[llm-proxy][AUTH] Incoming X-Internal-Auth: '{auth}', INTERNAL_API_KEY: '{AppConfig.INTERNAL_API_KEY}'"
        )
        if auth != AppConfig.INTERNAL_API_KEY:
            logger.warning(
                f"[llm-proxy][AUTH_FAIL] Unauthorized: header='{auth}' != key='{AppConfig.INTERNAL_API_KEY}'"
            )
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)
