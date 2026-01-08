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
        logger.info(
            f"[TRACE] AuthService.authenticate_password_grant started",
            extra={
                "trace_point": "auth_service_password_start",
                "username": token_request.username,
                "client_id": token_request.client_id,
                "scope": token_request.scope,
            }
        )
        
        # Validate request
        logger.debug(
            f"[TRACE] Validating password grant request",
            extra={"trace_point": "validate_request"}
        )
        
        if not token_request.validate_password_grant():
            logger.warning(
                f"[TRACE] Invalid password grant request - validation failed",
                extra={
                    "trace_point": "request_validation_failed",
                    "username": token_request.username,
                    "client_id": token_request.client_id,
                }
            )
            return None, None, None

        logger.debug(
            f"[TRACE] Request validation passed, validating OAuth client",
            extra={"trace_point": "validate_client", "client_id": token_request.client_id}
        )

        # Validate OAuth client
        client = await oauth_client_service.validate_client(
            db,
            token_request.client_id,
        )
        if not client:
            logger.warning(
                f"[TRACE] OAuth client validation failed",
                extra={
                    "trace_point": "client_validation_failed",
                    "client_id": token_request.client_id,
                }
            )
            return None, None, None

        logger.debug(
            f"[TRACE] OAuth client validated: {client.client_id}",
            extra={
                "trace_point": "client_validated",
                "client_id": client.client_id,
                "client_name": client.name,
            }
        )

        # Validate grant type
        logger.debug(
            f"[TRACE] Validating grant type for client",
            extra={"trace_point": "validate_grant_type", "client_id": client.client_id}
        )
        
        if not oauth_client_service.validate_grant_type(client, GrantType.PASSWORD):
            logger.warning(
                f"[TRACE] Password grant not allowed for client",
                extra={
                    "trace_point": "grant_type_not_allowed",
                    "client_id": token_request.client_id,
                }
            )
            return None, None, None

        logger.debug(
            f"[TRACE] Grant type validated, authenticating user",
            extra={
                "trace_point": "authenticate_user",
                "username": token_request.username,
            }
        )

        # Authenticate user
        user = await user_service.authenticate(
            db,
            token_request.username,
            token_request.password,
        )
        if not user:
            logger.warning(
                f"[TRACE] User authentication failed",
                extra={
                    "trace_point": "user_auth_failed",
                    "username": token_request.username,
                }
            )
            return None, None, None

        logger.info(
            f"[TRACE] User authenticated successfully: {user.id}",
            extra={
                "trace_point": "user_authenticated",
                "user_id": user.id,
                "username": user.username,
            }
        )

        # Validate and normalize scope
        logger.debug(
            f"[TRACE] Validating and normalizing scope",
            extra={
                "trace_point": "validate_scope",
                "requested_scope": token_request.scope,
                "client_id": client.client_id,
            }
        )
        
        is_valid_scope, normalized_scope = oauth_client_service.validate_scope(
            client,
            token_request.scope,
        )
        if not is_valid_scope:
            logger.warning(
                f"[TRACE] Invalid scope requested",
                extra={
                    "trace_point": "scope_validation_failed",
                    "requested_scope": token_request.scope,
                    "client_id": client.client_id,
                }
            )
            return None, None, None

        logger.debug(
            f"[TRACE] Scope validated and normalized: {normalized_scope}",
            extra={
                "trace_point": "scope_validated",
                "normalized_scope": normalized_scope,
            }
        )

        # Create token pair
        logger.info(
            f"[TRACE] Creating token pair",
            extra={
                "trace_point": "create_token_pair",
                "user_id": user.id,
                "client_id": client.client_id,
                "scope": normalized_scope,
            }
        )
        
        token_pair = token_service.create_token_pair(
            user_id=user.id,
            client_id=client.client_id,
            scope=normalized_scope,
            access_lifetime=client.access_token_lifetime,
            refresh_lifetime=client.refresh_token_lifetime,
        )

        logger.debug(
            f"[TRACE] Token pair created successfully",
            extra={"trace_point": "token_pair_created"}
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
            f"[TRACE] Password grant authentication completed successfully",
            extra={
                "trace_point": "auth_service_password_success",
                "user_id": user.id,
                "client_id": client.client_id,
                "scope": normalized_scope,
            }
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
        logger.info(
            f"[TRACE] AuthService.authenticate_refresh_grant started",
            extra={
                "trace_point": "auth_service_refresh_start",
                "client_id": token_request.client_id,
            }
        )
        
        # Validate request
        logger.debug(
            f"[TRACE] Validating refresh grant request",
            extra={"trace_point": "validate_refresh_request"}
        )
        
        if not token_request.validate_refresh_grant():
            logger.warning(
                f"[TRACE] Invalid refresh grant request - validation failed",
                extra={
                    "trace_point": "refresh_request_validation_failed",
                    "client_id": token_request.client_id,
                }
            )
            return None, None, None

        logger.debug(
            f"[TRACE] Request validation passed, validating OAuth client",
            extra={"trace_point": "validate_client_refresh", "client_id": token_request.client_id}
        )

        # Validate OAuth client
        client = await oauth_client_service.validate_client(
            db,
            token_request.client_id,
        )
        if not client:
            logger.warning(
                f"[TRACE] OAuth client validation failed for refresh grant",
                extra={
                    "trace_point": "client_validation_failed_refresh",
                    "client_id": token_request.client_id,
                }
            )
            return None, None, None

        logger.debug(
            f"[TRACE] OAuth client validated for refresh grant",
            extra={
                "trace_point": "client_validated_refresh",
                "client_id": client.client_id,
            }
        )

        # Validate grant type
        logger.debug(
            f"[TRACE] Validating refresh token grant type for client",
            extra={"trace_point": "validate_refresh_grant_type", "client_id": client.client_id}
        )
        
        if not oauth_client_service.validate_grant_type(client, GrantType.REFRESH_TOKEN):
            logger.warning(
                f"[TRACE] Refresh token grant not allowed for client",
                extra={
                    "trace_point": "refresh_grant_type_not_allowed",
                    "client_id": token_request.client_id,
                }
            )
            return None, None, None

        logger.debug(
            f"[TRACE] Grant type validated, validating refresh token",
            extra={"trace_point": "validate_refresh_token_payload"}
        )

        # Validate refresh token
        try:
            refresh_payload = token_service.validate_refresh_token(token_request.refresh_token)
            logger.debug(
                f"[TRACE] Refresh token payload validated",
                extra={
                    "trace_point": "refresh_token_payload_valid",
                    "jti": refresh_payload.jti,
                    "user_id": refresh_payload.sub,
                    "token_client_id": refresh_payload.client_id,
                }
            )
        except Exception as e:
            logger.warning(
                f"[TRACE] Invalid refresh token payload: {e}",
                extra={
                    "trace_point": "refresh_token_payload_invalid",
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            return None, None, None

        # Verify client_id matches
        logger.debug(
            f"[TRACE] Verifying client_id match",
            extra={
                "trace_point": "verify_client_id_match",
                "token_client_id": refresh_payload.client_id,
                "request_client_id": token_request.client_id,
            }
        )
        
        if refresh_payload.client_id != token_request.client_id:
            logger.warning(
                f"[TRACE] Client ID mismatch in refresh token",
                extra={
                    "trace_point": "client_id_mismatch",
                    "token_client_id": refresh_payload.client_id,
                    "request_client_id": token_request.client_id,
                }
            )
            return None, None, None

        logger.debug(
            f"[TRACE] Client ID verified, fetching user",
            extra={"trace_point": "fetch_user", "user_id": refresh_payload.sub}
        )

        # Get user
        user = await user_service.get_by_id(db, refresh_payload.sub)
        if not user or not user.is_active:
            logger.warning(
                f"[TRACE] User not found or inactive",
                extra={
                    "trace_point": "user_not_found_or_inactive",
                    "user_id": refresh_payload.sub,
                    "user_exists": user is not None,
                    "user_active": user.is_active if user else None,
                }
            )
            return None, None, None

        logger.info(
            f"[TRACE] User found and active: {user.id}",
            extra={
                "trace_point": "user_found_active",
                "user_id": user.id,
                "username": user.username,
            }
        )

        # Create new token pair
        logger.info(
            f"[TRACE] Creating new token pair for refresh grant",
            extra={
                "trace_point": "create_token_pair_refresh",
                "user_id": user.id,
                "client_id": client.client_id,
                "scope": refresh_payload.scope,
            }
        )
        
        token_pair = token_service.create_token_pair(
            user_id=user.id,
            client_id=client.client_id,
            scope=refresh_payload.scope,
            access_lifetime=client.access_token_lifetime,
            refresh_lifetime=client.refresh_token_lifetime,
        )

        logger.debug(
            f"[TRACE] New token pair created for refresh grant",
            extra={"trace_point": "token_pair_created_refresh"}
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
            f"[TRACE] Refresh grant authentication completed successfully",
            extra={
                "trace_point": "auth_service_refresh_success",
                "user_id": user.id,
                "client_id": client.client_id,
                "scope": refresh_payload.scope,
            }
        )

        return response, user, client


# Global instance
auth_service = AuthService()
