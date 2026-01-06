"""Rate limiting middleware"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import logger
from app.services.rate_limiter import rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests"""

    async def dispatch(self, request: Request, call_next):
        from app.core.config import settings

        # Skip if rate limiting is disabled
        if not settings.enable_rate_limiting:
            return await call_next(request)

        # Skip rate limiting for public endpoints
        public_paths = (
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/.well-known/jwks.json",
        )

        if request.url.path in public_paths:
            return await call_next(request)

        # Get client IP
        ip_address = self._get_client_ip(request)

        # Skip rate limiting for localhost in development
        if settings.is_development and ip_address in ("127.0.0.1", "localhost", "::1"):
            return await call_next(request)

        # Check rate limit for IP
        is_allowed, remaining = await rate_limiter.check_rate_limit_ip(ip_address)

        if not is_allowed:
            logger.warning(f"Rate limit exceeded for IP: {ip_address}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "error_description": "Too many requests. Please try again later.",
                },
                headers={
                    "X-RateLimit-Limit": "5",
                    "X-RateLimit-Remaining": str(remaining),
                    "Retry-After": "60",
                },
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Get client IP address from request
        
        Args:
            request: FastAPI request
            
        Returns:
            Client IP address
        """
        # Check X-Forwarded-For header (for proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get first IP in the chain
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct client
        if request.client:
            return request.client.host

        return "unknown"
