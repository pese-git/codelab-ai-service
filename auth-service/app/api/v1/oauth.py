"""OAuth2 endpoints"""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import logger
from app.core.dependencies import AuthServiceDep, DBSession
from app.schemas.oauth import GrantType, TokenErrorResponse, TokenRequest, TokenResponse
from app.services.audit_service import audit_service
from app.services.brute_force_protection import brute_force_protection
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
    # Get client IP for tracing
    ip_address = request.client.host if request.client else "unknown"
    
    logger.info(
        f"[TRACE] Token endpoint called: grant_type={grant_type}, client_id={client_id}, "
        f"username={username}, ip={ip_address}",
        extra={
            "trace_point": "token_endpoint_start",
            "grant_type": grant_type,
            "client_id": client_id,
            "username": username,
            "ip_address": ip_address,
            "has_password": password is not None,
            "has_refresh_token": refresh_token is not None,
            "scope": scope,
        }
    )
    
    try:
        # Parse grant type
        try:
            grant_type_enum = GrantType(grant_type)
            logger.debug(
                f"[TRACE] Grant type parsed successfully: {grant_type_enum.value}",
                extra={"trace_point": "grant_type_parsed", "grant_type": grant_type_enum.value}
            )
        except ValueError:
            logger.warning(
                f"[TRACE] Unsupported grant type: {grant_type}",
                extra={"trace_point": "grant_type_invalid", "grant_type": grant_type}
            )
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
        
        logger.debug(
            f"[TRACE] Token request created",
            extra={"trace_point": "token_request_created", "client_id": client_id}
        )

        # Handle password grant
        if grant_type_enum == GrantType.PASSWORD:
            logger.info(
                f"[TRACE] Routing to password grant handler",
                extra={"trace_point": "route_password_grant", "username": username}
            )
            return await _handle_password_grant(request, db, auth_svc, token_request)

        # Handle refresh token grant
        elif grant_type_enum == GrantType.REFRESH_TOKEN:
            logger.info(
                f"[TRACE] Routing to refresh token grant handler",
                extra={"trace_point": "route_refresh_grant", "client_id": client_id}
            )
            return await _handle_refresh_grant(request, db, auth_svc, token_request)

        else:
            logger.warning(
                f"[TRACE] Grant type not implemented: {grant_type}",
                extra={"trace_point": "grant_type_not_implemented", "grant_type": grant_type}
            )
            return _error_response(
                "unsupported_grant_type",
                f"Grant type '{grant_type}' is not implemented",
            )

    except Exception as e:
        logger.error(
            f"[TRACE] Token endpoint error: {e}",
            exc_info=True,
            extra={
                "trace_point": "token_endpoint_error",
                "error_type": type(e).__name__,
                "grant_type": grant_type,
                "client_id": client_id,
                "username": username,
            }
        )
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
    
    logger.info(
        f"[TRACE] Password grant handler started",
        extra={
            "trace_point": "password_grant_start",
            "username": token_request.username,
            "client_id": token_request.client_id,
        }
    )
    
    # Validate required parameters
    if not token_request.username or not token_request.password:
        logger.warning(
            f"[TRACE] Missing required parameters for password grant",
            extra={
                "trace_point": "password_grant_missing_params",
                "has_username": token_request.username is not None,
                "has_password": token_request.password is not None,
            }
        )
        return _error_response(
            "invalid_request",
            "Missing required parameters: username and password",
        )

    # Get client IP
    ip_address = request.client.host if request.client else "unknown"
    
    logger.debug(
        f"[TRACE] Checking brute-force protection",
        extra={
            "trace_point": "brute_force_check",
            "username": token_request.username,
            "ip_address": ip_address,
        }
    )

    # Check brute-force lockout
    is_locked, lockout_reason = await brute_force_protection.is_locked_out(
        token_request.username,
        ip_address,
    )
    if is_locked:
        logger.warning(
            f"[TRACE] Account locked due to brute-force protection",
            extra={
                "trace_point": "brute_force_locked",
                "username": token_request.username,
                "ip_address": ip_address,
                "reason": lockout_reason,
            }
        )
        return _error_response(
            "invalid_grant",
            lockout_reason or "Account temporarily locked",
            status_code=429,
        )
    
    logger.debug(
        f"[TRACE] Brute-force check passed, proceeding to authentication",
        extra={"trace_point": "brute_force_passed", "username": token_request.username}
    )

    # Authenticate
    logger.info(
        f"[TRACE] Calling auth service for password grant authentication",
        extra={
            "trace_point": "auth_service_call",
            "username": token_request.username,
            "client_id": token_request.client_id,
        }
    )
    
    result = await auth_svc.authenticate_password_grant(db, token_request)
    token_response, user, client = result

    if not token_response:
        logger.warning(
            f"[TRACE] Authentication failed for password grant",
            extra={
                "trace_point": "password_grant_auth_failed",
                "username": token_request.username,
                "client_id": token_request.client_id,
                "ip_address": ip_address,
            }
        )
        
        # Record failed attempt
        await brute_force_protection.record_failed_attempt(
            token_request.username,
            ip_address,
        )
        
        logger.debug(
            f"[TRACE] Failed attempt recorded",
            extra={"trace_point": "failed_attempt_recorded", "username": token_request.username}
        )

        # Log failed login
        await audit_service.log_login_failed(
            db=db,
            username=token_request.username,
            client_id=token_request.client_id,
            ip_address=ip_address,
            user_agent=request.headers.get("User-Agent"),
            reason="Invalid credentials",
        )

        return _error_response(
            "invalid_grant",
            "Invalid username or password",
            status_code=401,
        )

    logger.info(
        f"[TRACE] Authentication successful, resetting failed attempts",
        extra={
            "trace_point": "password_grant_auth_success",
            "user_id": user.id,
            "username": user.username,
            "client_id": client.client_id,
        }
    )

    # Reset failed attempts on successful login
    await brute_force_protection.reset_failed_attempts(
        token_request.username,
        ip_address,
    )

    # Log successful login
    await audit_service.log_login_success(
        db=db,
        user_id=user.id,
        client_id=client.client_id,
        ip_address=ip_address,
        user_agent=request.headers.get("User-Agent"),
        scope=token_response.scope,
    )
    
    logger.debug(
        f"[TRACE] Saving refresh token to database",
        extra={"trace_point": "save_refresh_token", "user_id": user.id}
    )

    # Save refresh token to database
    # Extract payload from token_response
    from app.services.token_service import token_service

    refresh_payload = token_service.validate_refresh_token(token_response.refresh_token)
    await refresh_token_service.save_refresh_token(db, refresh_payload)

    logger.info(
        f"[TRACE] Password grant completed successfully: user={user.id}, client={client.client_id}",
        extra={
            "trace_point": "password_grant_complete",
            "user_id": user.id,
            "client_id": client.client_id,
            "ip_address": request.client.host if request.client else None,
            "scope": token_response.scope,
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
    
    logger.info(
        f"[TRACE] Refresh grant handler started",
        extra={
            "trace_point": "refresh_grant_start",
            "client_id": token_request.client_id,
        }
    )
    
    # Validate required parameters
    if not token_request.refresh_token:
        logger.warning(
            f"[TRACE] Missing refresh token parameter",
            extra={"trace_point": "refresh_grant_missing_token"}
        )
        return _error_response(
            "invalid_request",
            "Missing required parameter: refresh_token",
        )

    # Validate refresh token in database
    from app.services.token_service import token_service

    logger.debug(
        f"[TRACE] Validating refresh token JWT",
        extra={"trace_point": "refresh_token_jwt_validation"}
    )

    try:
        old_refresh_payload = token_service.validate_refresh_token(token_request.refresh_token)
        logger.debug(
            f"[TRACE] Refresh token JWT validated successfully",
            extra={
                "trace_point": "refresh_token_jwt_valid",
                "jti": old_refresh_payload.jti,
                "user_id": old_refresh_payload.sub,
            }
        )
    except Exception as e:
        logger.warning(
            f"[TRACE] Invalid refresh token JWT: {e}",
            extra={
                "trace_point": "refresh_token_jwt_invalid",
                "error": str(e),
                "error_type": type(e).__name__,
            }
        )
        return _error_response(
            "invalid_grant",
            "Invalid or expired refresh token",
            status_code=401,
        )

    logger.debug(
        f"[TRACE] Checking if refresh token is revoked or reused",
        extra={
            "trace_point": "refresh_token_db_check",
            "jti": old_refresh_payload.jti,
        }
    )

    # Check if token is revoked or reused
    is_valid, error_msg = await refresh_token_service.validate_refresh_token(
        db,
        old_refresh_payload.jti,
    )

    if not is_valid:
        logger.warning(
            f"[TRACE] Refresh token validation failed in database",
            extra={
                "trace_point": "refresh_token_db_invalid",
                "jti": old_refresh_payload.jti,
                "error_msg": error_msg,
            }
        )
        return _error_response(
            "invalid_grant",
            error_msg or "Refresh token is invalid",
            status_code=401,
        )
    
    logger.debug(
        f"[TRACE] Refresh token validated, proceeding to authentication",
        extra={"trace_point": "refresh_token_validated", "jti": old_refresh_payload.jti}
    )

    # Authenticate with refresh token
    logger.info(
        f"[TRACE] Calling auth service for refresh grant authentication",
        extra={
            "trace_point": "auth_service_refresh_call",
            "client_id": token_request.client_id,
            "user_id": old_refresh_payload.sub,
        }
    )
    
    result = await auth_svc.authenticate_refresh_grant(db, token_request)
    token_response, user, client = result

    if not token_response:
        logger.warning(
            f"[TRACE] Refresh grant authentication failed",
            extra={
                "trace_point": "refresh_grant_auth_failed",
                "client_id": token_request.client_id,
                "jti": old_refresh_payload.jti,
            }
        )
        return _error_response(
            "invalid_grant",
            "Invalid refresh token",
            status_code=401,
        )

    logger.info(
        f"[TRACE] Refresh grant authentication successful",
        extra={
            "trace_point": "refresh_grant_auth_success",
            "user_id": user.id,
            "client_id": client.client_id,
        }
    )

    logger.debug(
        f"[TRACE] Revoking old refresh token",
        extra={"trace_point": "revoke_old_token", "jti": old_refresh_payload.jti}
    )

    # Revoke old refresh token
    await refresh_token_service.revoke_token(db, old_refresh_payload.jti)

    logger.debug(
        f"[TRACE] Saving new refresh token",
        extra={"trace_point": "save_new_refresh_token", "user_id": user.id}
    )

    # Save new refresh token
    new_refresh_payload = token_service.validate_refresh_token(token_response.refresh_token)
    await refresh_token_service.save_refresh_token(
        db,
        new_refresh_payload,
        parent_jti=old_refresh_payload.jti,
    )

    # Log token refresh
    await audit_service.log_token_refresh(
        db=db,
        user_id=user.id,
        client_id=client.client_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )

    logger.info(
        f"[TRACE] Refresh grant completed successfully: user={user.id}, client={client.client_id}",
        extra={
            "trace_point": "refresh_grant_complete",
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
