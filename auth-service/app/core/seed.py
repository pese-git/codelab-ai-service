"""Database seeding with default data"""

import json

from sqlalchemy import select

from app.core.config import logger
from app.models import OAuthClient, User
from app.models.database import async_session_maker
from app.schemas.oauth import GrantType
from app.utils.crypto import hash_password


async def seed_default_data():
    """Seed database with default users and OAuth clients"""
    async with async_session_maker() as db:
        try:
            await _create_default_user(db)
            await _create_default_oauth_clients(db)
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to seed default data: {e}")
            await db.rollback()


async def _create_default_user(db):
    """Create default admin user"""
    # Check if admin user already exists
    result = await db.execute(select(User).where(User.username == "admin"))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.debug("Admin user already exists")
        return

    # Create admin user
    try:
        password_hash = hash_password("admin123")
        admin = User(
            username="admin",
            email="admin@codelab.local",
            password_hash=password_hash,
            is_active=True,
            is_verified=True,
        )

        db.add(admin)
        logger.info("✓ Admin user created (username: admin, password: admin123)")
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        raise


async def _create_default_oauth_clients(db):
    """Create default OAuth clients"""
    
    # 1. Flutter App Client (Public Client)
    result = await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == "codelab-flutter-app")
    )
    if not result.scalar_one_or_none():
        flutter_client = OAuthClient(
            client_id="codelab-flutter-app",
            client_secret_hash=None,  # Public client
            name="CodeLab Flutter Application",
            description="Official CodeLab mobile and desktop application",
            is_confidential=False,
            allowed_scopes="api:read api:write",
            allowed_grant_types=json.dumps([
                GrantType.PASSWORD.value,
                GrantType.REFRESH_TOKEN.value,
            ]),
            access_token_lifetime=900,  # 15 minutes
            refresh_token_lifetime=2592000,  # 30 days
            is_active=True,
        )

        db.add(flutter_client)
        logger.info("✓ OAuth client created: codelab-flutter-app (public)")
    else:
        logger.debug("Flutter app client already exists")

    # 2. Internal Services Client (Confidential Client)
    result = await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == "codelab-internal")
    )
    if not result.scalar_one_or_none():
        # Use shorter secret for bcrypt (max 72 bytes)
        internal_secret = "internal-secret-123"
        internal_client = OAuthClient(
            client_id="codelab-internal",
            client_secret_hash=hash_password(internal_secret),
            name="CodeLab Internal Services",
            description="Internal microservices communication",
            is_confidential=True,
            allowed_scopes="api:admin api:read api:write",
            allowed_grant_types=json.dumps([
                GrantType.PASSWORD.value,
                GrantType.REFRESH_TOKEN.value,
            ]),
            access_token_lifetime=3600,  # 1 hour
            refresh_token_lifetime=7776000,  # 90 days
            is_active=True,
        )

        db.add(internal_client)
        logger.info("✓ OAuth client created: codelab-internal (confidential, secret: internal-secret-123)")
    else:
        logger.debug("Internal services client already exists")
