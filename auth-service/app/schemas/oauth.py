"""OAuth schemas"""

from enum import Enum

from pydantic import BaseModel, Field


class GrantType(str, Enum):
    """OAuth2 grant types"""

    PASSWORD = "password"
    REFRESH_TOKEN = "refresh_token"
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"


class TokenRequest(BaseModel):
    """OAuth2 token request"""

    grant_type: GrantType
    client_id: str = Field(..., min_length=1)

    # Password grant fields
    username: str | None = Field(None, min_length=1)
    password: str | None = Field(None, min_length=1)

    # Refresh token grant fields
    refresh_token: str | None = Field(None, min_length=1)

    # Optional scope
    scope: str | None = None

    def validate_password_grant(self) -> bool:
        """Validate password grant parameters"""
        return self.grant_type == GrantType.PASSWORD and self.username and self.password

    def validate_refresh_grant(self) -> bool:
        """Validate refresh token grant parameters"""
        return self.grant_type == GrantType.REFRESH_TOKEN and self.refresh_token


class TokenResponse(BaseModel):
    """OAuth2 token response"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    scope: str | None = None


class TokenErrorResponse(BaseModel):
    """OAuth2 error response"""

    error: str
    error_description: str | None = None
    error_uri: str | None = None


class OAuthClientCreate(BaseModel):
    """Schema for creating OAuth client"""

    client_id: str = Field(..., min_length=8, max_length=255)
    client_secret: str | None = Field(None, min_length=16)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    is_confidential: bool = False
    allowed_scopes: str = Field(..., min_length=1)
    allowed_grant_types: list[GrantType]
    access_token_lifetime: int = Field(900, gt=0)
    refresh_token_lifetime: int = Field(2592000, gt=0)


class OAuthClientResponse(BaseModel):
    """Schema for OAuth client response"""

    id: str
    client_id: str
    name: str
    description: str | None
    is_confidential: bool
    allowed_scopes: str
    allowed_grant_types: str
    access_token_lifetime: int
    refresh_token_lifetime: int
    is_active: bool

    model_config = {"from_attributes": True}
