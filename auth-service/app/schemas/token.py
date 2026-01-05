"""Token schemas (JWT payload)"""

from enum import Enum

from pydantic import BaseModel, Field


class TokenType(str, Enum):
    """Token types"""

    ACCESS = "access"
    REFRESH = "refresh"


class JWTPayload(BaseModel):
    """Base JWT payload"""

    iss: str = Field(..., description="Issuer")
    sub: str = Field(..., description="Subject (user_id)")
    aud: str = Field(..., description="Audience")
    exp: int = Field(..., description="Expiration time (Unix timestamp)")
    iat: int = Field(..., description="Issued at (Unix timestamp)")
    nbf: int = Field(..., description="Not before (Unix timestamp)")
    jti: str = Field(..., description="JWT ID (unique identifier)")
    type: TokenType = Field(..., description="Token type")
    client_id: str = Field(..., description="Client ID")


class AccessTokenPayload(JWTPayload):
    """Access token payload"""

    type: TokenType = TokenType.ACCESS
    scope: str = Field(..., description="Space-separated scopes")


class RefreshTokenPayload(JWTPayload):
    """Refresh token payload"""

    type: TokenType = TokenType.REFRESH
    scope: str = Field(..., description="Space-separated scopes")


class TokenPair(BaseModel):
    """Pair of access and refresh tokens"""

    access_token: str
    refresh_token: str
    access_token_payload: AccessTokenPayload
    refresh_token_payload: RefreshTokenPayload
