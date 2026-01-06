"""FastAPI dependencies"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.services.auth_service import auth_service
from app.services.oauth_client_service import oauth_client_service
from app.services.token_service import token_service
from app.services.user_service import user_service

# Database session dependency
DBSession = Annotated[AsyncSession, Depends(get_db)]


# Service dependencies
def get_user_service():
    """Get user service instance"""
    return user_service


def get_oauth_client_service():
    """Get OAuth client service instance"""
    return oauth_client_service


def get_auth_service():
    """Get auth service instance"""
    return auth_service


def get_token_service():
    """Get token service instance"""
    return token_service


# Type annotations for services
UserServiceDep = Annotated[type[user_service], Depends(get_user_service)]
OAuthClientServiceDep = Annotated[type[oauth_client_service], Depends(get_oauth_client_service)]
AuthServiceDep = Annotated[type[auth_service], Depends(get_auth_service)]
TokenServiceDep = Annotated[type[token_service], Depends(get_token_service)]
