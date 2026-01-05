"""OAuth2 endpoints"""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import logger
from app.core.dependencies import AuthServiceDep, DBSession
from app.schemas.oauth import GrantType, TokenErrorResponse, TokenRequest, TokenResponse
from app.services.refresh_token_service import refresh_token_service

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
async def token_endpoint(
    request: Request,
    db: DBSession,
    auth_svc: AuthServiceDep,
    grant_type: str = Form(...),
    client_id: str = Form(...),
    username: str | None = Form(None),
    password: str | None = Form(None),
    refresh_token: str | None = Form(None),
    scope: str | None = Form(None),
):
    """
    OAuth2 Token Endpoint
    
    Supports:
    - Password Grant: username + password → access_token + refresh_token
    - Refresh Token Grant: refresh_token → new access_token + new refresh_token
    
    Args:
        grant_type: OAuth2 grant type (password or refresh_token)
        client_id: OAuth client ID
        username: Username or email (for password grant)
        password: Password (for password grant)
        refresh_token: Refresh token (for refresh_token grant)
        scope: Requested scopes (optional)
        
    Returns:
        TokenResponse with access_token and refresh_token
        
    Raises:
        HTTPException: OAuth2 error response
    """
    try:
        # Parse grant type
        try:
            grant_type_enum = GrantType(grant_type)
        except ValueError:
            return _error_response(
                "unsupported_grant_type",
                f"Grant type '{grant_type}' is not supported",
            )

        # Create token request
        token_request = TokenRequest(
            grant_type=grant_type_enum,
            client_id=client_id,
            username=username,
            password=password,
            refresh_token=refresh_token,
            scope=scope,
        )

        # Handle password grant
        if grant_type_enum == GrantType.PASSWORD:
            return await _handle_password_grant(request, db, auth_svc, token_request)

        # Handle refresh token grant
        elif grant_type_enum == GrantType.REFRESH_TOKEN:
            return await _handle_refresh_grant(request, db, auth_svc, token_request)

        else:
            return _error_response(
                "unsupported_grant_type",
                f"Grant type '{grant_type}' is not implemented",
            )

    except Exception as e:
        logger.error(f"Token endpoint error: {e}", exc_info=True)
        return _error_response(
            "server_error",
            "An internal error occurred",
        )


async def _handle_password_grant(
    request: Request,
    db: DBSession,
    auth_svc: AuthServiceDep,
    token_request: TokenRequest,
) -> JSONResponse:
    """Handle password grant"""
    
    # Validate required parameters
    if not token_request.username or not token_request.password:
        return _error_response(
            "invalid_request",
            "Missing required parameters: username and password",
        )

    # Authenticate
    result = await auth_svc.authenticate_password_grant(db, token_request)
    token_response, user, client = result

    if not token_response:
        return _error_response(
            "invalid_grant",
            "Invalid username or password",
            status_code=401,
        )

    # Save refresh token to database
    # Extract payload from token_response
    from app.services.token_service import token_service

    refresh_payload = token_service.validate_refresh_token(token_response.refresh_token)
    await refresh_token_service.save_refresh_token(db, refresh_payload)

    logger.info(
        f"Password grant successful: user={user.id}, client={client.client_id}",
        extra={
            "user_id": user.id,
            "client_id": client.client_id,
            "ip_address": request.client.host if request.client else None,
        },
    )

    return JSONResponse(
        content=token_response.model_dump(),
        status_code=200,
    )


async def _handle_refresh_grant(
    request: Request,
    db: DBSession,
    auth_svc: AuthServiceDep,
    token_request: TokenRequest,
) -> JSONResponse:
    """Handle refresh token grant"""
    
    # Validate required parameters
    if not token_request.refresh_token:
        return _error_response(
            "invalid_request",
            "Missing required parameter: refresh_token",
        )

    # Validate refresh token in database
    from app.services.token_service import token_service

    try:
        old_refresh_payload = token_service.validate_refresh_token(token_request.refresh_token)
    except Exception as e:
        logger.warning(f"Invalid refresh token JWT: {e}")
        return _error_response(
            "invalid_grant",
            "Invalid or expired refresh token",
            status_code=401,
        )

    # Check if token is revoked or reused
    is_valid, error_msg = await refresh_token_service.validate_refresh_token(
        db,
        old_refresh_payload.jti,
    )

    if not is_valid:
        return _error_response(
            "invalid_grant",
            error_msg or "Refresh token is invalid",
            status_code=401,
        )

    # Authenticate with refresh token
    result = await auth_svc.authenticate_refresh_grant(db, token_request)
    token_response, user, client = result

    if not token_response:
        return _error_response(
            "invalid_grant",
            "Invalid refresh token",
            status_code=401,
        )

    # Revoke old refresh token
    await refresh_token_service.revoke_token(db, old_refresh_payload.jti)

    # Save new refresh token
    new_refresh_payload = token_service.validate_refresh_token(token_response.refresh_token)
    await refresh_token_service.save_refresh_token(
        db,
        new_refresh_payload,
        parent_jti=old_refresh_payload.jti,
    )

    logger.info(
        f"Refresh grant successful: user={user.id}, client={client.client_id}",
        extra={
            "user_id": user.id,
            "client_id": client.client_id,
            "ip_address": request.client.host if request.client else None,
        },
    )

    return JSONResponse(
        content=token_response.model_dump(),
        status_code=200,
    )


def _error_response(
    error: str,
    error_description: str | None = None,
    status_code: int = 400,
) -> JSONResponse:
    """
    Create OAuth2 error response
    
    Args:
        error: OAuth2 error code
        error_description: Human-readable error description
        status_code: HTTP status code
        
    Returns:
        JSONResponse with error
    """
    error_response = TokenErrorResponse(
        error=error,
        error_description=error_description,
    )

    return JSONResponse(
        content=error_response.model_dump(exclude_none=True),
        status_code=status_code,
    )
