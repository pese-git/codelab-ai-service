"""Authentication service"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import logger
from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.schemas.oauth import GrantType, TokenRequest, TokenResponse
from app.schemas.token import TokenPair
from app.services.oauth_client_service import oauth_client_service
from app.services.token_service import token_service
from app.services.user_service import user_service


class AuthService:
    """Service for authentication operations"""

    async def authenticate_password_grant(
        self,
        db: AsyncSession,
        token_request: TokenRequest,
    ) -> tuple[TokenResponse, User, OAuthClient] | tuple[None, None, None]:
        """
        Authenticate user with password grant
        
        Args:
            db: Database session
            token_request: Token request with username and password
            
        Returns:
            Tuple of (TokenResponse, User, OAuthClient) if successful,
            (None, None, None) otherwise
        """
        # Validate request
        if not token_request.validate_password_grant():
            logger.warning("Invalid password grant request")
            return None, None, None

        # Validate OAuth client
        client = await oauth_client_service.validate_client(
            db,
            token_request.client_id,
        )
        if not client:
            logger.warning(f"Invalid client: {token_request.client_id}")
            return None, None, None

        # Validate grant type
        if not oauth_client_service.validate_grant_type(client, GrantType.PASSWORD):
            logger.warning(f"Password grant not allowed for client: {token_request.client_id}")
            return None, None, None

        # Authenticate user
        user = await user_service.authenticate(
            db,
            token_request.username,
            token_request.password,
        )
        if not user:
            logger.warning(f"Authentication failed for user: {token_request.username}")
            return None, None, None

        # Validate and normalize scope
        is_valid_scope, normalized_scope = oauth_client_service.validate_scope(
            client,
            token_request.scope,
        )
        if not is_valid_scope:
            logger.warning(
                f"Invalid scope requested: {token_request.scope} for client {client.client_id}"
            )
            return None, None, None

        # Create token pair
        token_pair = token_service.create_token_pair(
            user_id=user.id,
            client_id=client.client_id,
            scope=normalized_scope,
            access_lifetime=client.access_token_lifetime,
            refresh_lifetime=client.refresh_token_lifetime,
        )

        # Create response
        response = TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="bearer",
            expires_in=client.access_token_lifetime,
            scope=normalized_scope,
        )

        logger.info(
            f"Password grant successful: user={user.id}, client={client.client_id}, "
            f"scope={normalized_scope}"
        )

        return response, user, client

    async def authenticate_refresh_grant(
        self,
        db: AsyncSession,
        token_request: TokenRequest,
    ) -> tuple[TokenResponse, User, OAuthClient] | tuple[None, None, None]:
        """
        Authenticate with refresh token grant
        
        Args:
            db: Database session
            token_request: Token request with refresh token
            
        Returns:
            Tuple of (TokenResponse, User, OAuthClient) if successful,
            (None, None, None) otherwise
        """
        # Validate request
        if not token_request.validate_refresh_grant():
            logger.warning("Invalid refresh grant request")
            return None, None, None

        # Validate OAuth client
        client = await oauth_client_service.validate_client(
            db,
            token_request.client_id,
        )
        if not client:
            logger.warning(f"Invalid client: {token_request.client_id}")
            return None, None, None

        # Validate grant type
        if not oauth_client_service.validate_grant_type(client, GrantType.REFRESH_TOKEN):
            logger.warning(
                f"Refresh token grant not allowed for client: {token_request.client_id}"
            )
            return None, None, None

        # Validate refresh token
        try:
            refresh_payload = token_service.validate_refresh_token(token_request.refresh_token)
        except Exception as e:
            logger.warning(f"Invalid refresh token: {e}")
            return None, None, None

        # Verify client_id matches
        if refresh_payload.client_id != token_request.client_id:
            logger.warning(
                f"Client ID mismatch: token={refresh_payload.client_id}, "
                f"request={token_request.client_id}"
            )
            return None, None, None

        # Get user
        user = await user_service.get_by_id(db, refresh_payload.sub)
        if not user or not user.is_active:
            logger.warning(f"User not found or inactive: {refresh_payload.sub}")
            return None, None, None

        # TODO: Check if refresh token is revoked in database
        # This will be implemented in Iteration 4 with RefreshTokenService

        # Create new token pair
        token_pair = token_service.create_token_pair(
            user_id=user.id,
            client_id=client.client_id,
            scope=refresh_payload.scope,
            access_lifetime=client.access_token_lifetime,
            refresh_lifetime=client.refresh_token_lifetime,
        )

        # Create response
        response = TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="bearer",
            expires_in=client.access_token_lifetime,
            scope=refresh_payload.scope,
        )

        logger.info(
            f"Refresh grant successful: user={user.id}, client={client.client_id}, "
            f"scope={refresh_payload.scope}"
        )

        return response, user, client


# Global instance
auth_service = AuthService()
