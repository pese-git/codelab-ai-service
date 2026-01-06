"""Pydantic schemas"""

from app.schemas.oauth import (
    GrantType,
    OAuthClientCreate,
    OAuthClientResponse,
    TokenErrorResponse,
    TokenRequest,
    TokenResponse,
)
from app.schemas.token import (
    AccessTokenPayload,
    JWTPayload,
    RefreshTokenPayload,
    TokenPair,
    TokenType,
)
from app.schemas.user import UserCreate, UserInDB, UserResponse, UserUpdate

__all__ = [
    # OAuth
    "GrantType",
    "TokenRequest",
    "TokenResponse",
    "TokenErrorResponse",
    "OAuthClientCreate",
    "OAuthClientResponse",
    # Token
    "TokenType",
    "JWTPayload",
    "AccessTokenPayload",
    "RefreshTokenPayload",
    "TokenPair",
    # User
    "UserCreate",
    "UserUpdate",
    "UserInDB",
    "UserResponse",
]
