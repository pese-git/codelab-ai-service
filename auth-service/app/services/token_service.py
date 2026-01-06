"""Token service for JWT operations"""

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import rsa_key_manager
from app.schemas.token import AccessTokenPayload, RefreshTokenPayload, TokenPair, TokenType


class TokenService:
    """Service for creating and validating JWT tokens"""

    def __init__(self):
        self.algorithm = "RS256"

    def create_access_token(
        self,
        user_id: str,
        client_id: str,
        scope: str,
        lifetime: int | None = None,
    ) -> tuple[str, AccessTokenPayload]:
        """
        Create an access token
        
        Args:
            user_id: User ID (subject)
            client_id: OAuth client ID
            scope: Space-separated scopes
            lifetime: Token lifetime in seconds (default from settings)
            
        Returns:
            Tuple of (token string, payload)
        """
        if lifetime is None:
            lifetime = settings.access_token_lifetime

        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=lifetime)

        payload = AccessTokenPayload(
            iss=settings.jwt_issuer,
            sub=user_id,
            aud=settings.jwt_audience,
            exp=int(exp.timestamp()),
            iat=int(now.timestamp()),
            nbf=int(now.timestamp()),
            jti=str(uuid.uuid4()),
            type=TokenType.ACCESS,
            client_id=client_id,
            scope=scope,
        )

        token = jwt.encode(
            payload.model_dump(),
            rsa_key_manager.get_private_key_pem(),
            algorithm=self.algorithm,
            headers={"kid": rsa_key_manager.kid},
        )

        return token, payload

    def create_refresh_token(
        self,
        user_id: str,
        client_id: str,
        scope: str,
        lifetime: int | None = None,
    ) -> tuple[str, RefreshTokenPayload]:
        """
        Create a refresh token
        
        Args:
            user_id: User ID (subject)
            client_id: OAuth client ID
            scope: Space-separated scopes
            lifetime: Token lifetime in seconds (default from settings)
            
        Returns:
            Tuple of (token string, payload)
        """
        if lifetime is None:
            lifetime = settings.refresh_token_lifetime

        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=lifetime)

        payload = RefreshTokenPayload(
            iss=settings.jwt_issuer,
            sub=user_id,
            aud=settings.jwt_audience,
            exp=int(exp.timestamp()),
            iat=int(now.timestamp()),
            nbf=int(now.timestamp()),
            jti=str(uuid.uuid4()),
            type=TokenType.REFRESH,
            client_id=client_id,
            scope=scope,
        )

        token = jwt.encode(
            payload.model_dump(),
            rsa_key_manager.get_private_key_pem(),
            algorithm=self.algorithm,
            headers={"kid": rsa_key_manager.kid},
        )

        return token, payload

    def create_token_pair(
        self,
        user_id: str,
        client_id: str,
        scope: str,
        access_lifetime: int | None = None,
        refresh_lifetime: int | None = None,
    ) -> TokenPair:
        """
        Create a pair of access and refresh tokens
        
        Args:
            user_id: User ID (subject)
            client_id: OAuth client ID
            scope: Space-separated scopes
            access_lifetime: Access token lifetime in seconds
            refresh_lifetime: Refresh token lifetime in seconds
            
        Returns:
            TokenPair with both tokens and their payloads
        """
        access_token, access_payload = self.create_access_token(
            user_id=user_id,
            client_id=client_id,
            scope=scope,
            lifetime=access_lifetime,
        )

        refresh_token, refresh_payload = self.create_refresh_token(
            user_id=user_id,
            client_id=client_id,
            scope=scope,
            lifetime=refresh_lifetime,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_payload=access_payload,
            refresh_token_payload=refresh_payload,
        )

    def decode_token(self, token: str, verify: bool = True) -> dict:
        """
        Decode and validate a JWT token
        
        Args:
            token: JWT token string
            verify: Whether to verify signature and expiration
            
        Returns:
            Decoded payload
            
        Raises:
            JWTError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                rsa_key_manager.get_public_key_pem(),
                algorithms=[self.algorithm],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
                options={"verify_signature": verify, "verify_exp": verify},
            )
            return payload
        except JWTError as e:
            raise JWTError(f"Invalid token: {str(e)}")

    def validate_access_token(self, token: str) -> AccessTokenPayload:
        """
        Validate an access token
        
        Args:
            token: JWT token string
            
        Returns:
            AccessTokenPayload
            
        Raises:
            JWTError: If token is invalid
        """
        payload = self.decode_token(token)

        if payload.get("type") != TokenType.ACCESS:
            raise JWTError("Invalid token type")

        return AccessTokenPayload(**payload)

    def validate_refresh_token(self, token: str) -> RefreshTokenPayload:
        """
        Validate a refresh token
        
        Args:
            token: JWT token string
            
        Returns:
            RefreshTokenPayload
            
        Raises:
            JWTError: If token is invalid
        """
        payload = self.decode_token(token)

        if payload.get("type") != TokenType.REFRESH:
            raise JWTError("Invalid token type")

        return RefreshTokenPayload(**payload)


# Global instance
token_service = TokenService()
