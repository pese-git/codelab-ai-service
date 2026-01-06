"""JWT authentication middleware for Gateway"""

import time

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import AppConfig, logger


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT token validation"""

    def __init__(self, app, jwks_url: str, issuer: str, audience: str, cache_ttl: int = 3600):
        super().__init__(app)
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.audience = audience
        self.jwks_cache = None
        self.jwks_cache_time = 0
        self.cache_ttl = cache_ttl

    async def get_jwks(self):
        """Get JWKS with caching"""
        current_time = time.time()

        if self.jwks_cache is None or (current_time - self.jwks_cache_time) > self.cache_ttl:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.jwks_url, timeout=5.0)
                    response.raise_for_status()
                    self.jwks_cache = response.json()
                    self.jwks_cache_time = current_time
                    logger.debug(f"JWKS cache updated from {self.jwks_url}")
            except Exception as e:
                logger.error(f"Failed to fetch JWKS: {e}")
                # If cache exists, use it even if expired
                if self.jwks_cache is None:
                    raise

        return self.jwks_cache

    async def dispatch(self, request: Request, call_next):
        # Public endpoints
        public_paths = ("/health", "/docs", "/openapi.json", "/redoc")

        if request.url.path in public_paths or request.url.path.startswith("/ws/"):
            return await call_next(request)

        # Extract token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "error_description": "Missing or invalid Authorization header",
                },
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Validate JWT
        try:
            jwks = await self.get_jwks()

            # Decode and validate token
            payload = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"verify_exp": True, "verify_aud": True, "verify_iss": True},
            )

            # Check token type
            if payload.get("type") != "access":
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "invalid_token",
                        "error_description": "Invalid token type",
                    },
                )

            # Add user_id and scope to request state
            request.state.user_id = payload["sub"]
            request.state.scope = payload.get("scope", "")
            request.state.client_id = payload.get("client_id")

            logger.debug(
                f"JWT validated: user_id={payload['sub']}, scope={payload.get('scope')}"
            )

        except JWTError as e:
            logger.warning(f"JWT validation failed: {e}")
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_token", "error_description": str(e)},
            )
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "server_error", "error_description": "Internal error"},
            )

        return await call_next(request)


class HybridAuthMiddleware(BaseHTTPMiddleware):
    """Hybrid middleware supporting both JWT and X-Internal-Auth"""

    def __init__(self, app, jwks_url: str, issuer: str, audience: str, internal_api_key: str):
        super().__init__(app)
        self.jwt_middleware = JWTAuthMiddleware(app, jwks_url, issuer, audience)
        self.internal_api_key = internal_api_key

    async def dispatch(self, request: Request, call_next):
        # Public endpoints
        public_paths = ("/health", "/docs", "/openapi.json", "/redoc")

        if request.url.path in public_paths or request.url.path.startswith("/ws/"):
            return await call_next(request)

        # Try JWT authentication first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return await self.jwt_middleware.dispatch(request, call_next)

        # Fallback to X-Internal-Auth
        internal_auth = request.headers.get("X-Internal-Auth")
        if internal_auth == self.internal_api_key:
            # Set system user_id for internal requests
            request.state.user_id = "system"
            request.state.scope = "internal"
            request.state.client_id = "internal"
            logger.debug("Internal auth validated")
            return await call_next(request)

        # No valid authentication
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "error_description": "Authentication required"},
        )
