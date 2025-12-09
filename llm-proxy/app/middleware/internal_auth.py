import os
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "change-me-internal-key")
logger = logging.getLogger("llm-proxy")

class InternalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/llm/models"):
            return await call_next(request)
        auth = request.headers.get("x-internal-auth")
        logger.debug(
            f"[llm-proxy][AUTH] Incoming X-Internal-Auth: '{auth}', INTERNAL_API_KEY: '{INTERNAL_API_KEY}'"
        )
        if auth != INTERNAL_API_KEY:
            logger.warning(
                f"[llm-proxy][AUTH_FAIL] Unauthorized: header='{auth}' != key='{INTERNAL_API_KEY}'"
            )
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)