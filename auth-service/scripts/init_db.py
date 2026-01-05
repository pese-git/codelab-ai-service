#!/usr/bin/env python3
"""Script to initialize database with default data"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import logger
from app.models import User, OAuthClient, init_db
from app.models.database import async_session_maker
from app.schemas.oauth import GrantType
from app.utils.crypto import hash_password


async def create_default_user():
    """Create default admin user"""
    async with async_session_maker() as db:
        try:
            # Check if admin user already exists
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.username == "admin"))
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                logger.info("Admin user already exists")
                return

            # Create admin user
            admin = User(
                username="admin",
                email="admin@codelab.local",
                password_hash=hash_password("admin123"),
                is_active=True,
                is_verified=True,
            )

            db.add(admin)
            await db.commit()
            await db.refresh(admin)

            logger.info(f"✓ Admin user created: {admin.username} (password: admin123)")
            print(f"\n✓ Admin user created:")
            print(f"  Username: {admin.username}")
            print(f"  Email: {admin.email}")
            print(f"  Password: admin123")
            print(f"  ID: {admin.id}")

        except Exception as e:
            logger.error(f"Failed to create admin user: {e}")
            await db.rollback()
            raise


async def create_default_oauth_clients():
    """Create default OAuth clients"""
    async with async_session_maker() as db:
        try:
            from sqlalchemy import select

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
                logger.info("✓ Flutter app client created")
                print(f"\n✓ OAuth Client created:")
                print(f"  Client ID: {flutter_client.client_id}")
                print(f"  Name: {flutter_client.name}")
                print(f"  Type: Public")
                print(f"  Scopes: {flutter_client.allowed_scopes}")
            else:
                logger.info("Flutter app client already exists")

            # 2. Internal Services Client (Confidential Client)
            result = await db.execute(
                select(OAuthClient).where(OAuthClient.client_id == "codelab-internal")
            )
            if not result.scalar_one_or_none():
                internal_secret = "internal-secret-change-in-production"
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
                logger.info("✓ Internal services client created")
                print(f"\n✓ OAuth Client created:")
                print(f"  Client ID: {internal_client.client_id}")
                print(f"  Client Secret: {internal_secret}")
                print(f"  Name: {internal_client.name}")
                print(f"  Type: Confidential")
                print(f"  Scopes: {internal_client.allowed_scopes}")
            else:
                logger.info("Internal services client already exists")

            await db.commit()

        except Exception as e:
            logger.error(f"Failed to create OAuth clients: {e}")
            await db.rollback()
            raise


async def main():
    """Main initialization function"""
    print("=" * 60)
    print("CodeLab Auth Service - Database Initialization")
    print("=" * 60)

    try:
        # Initialize database (create tables)
        logger.info("Initializing database...")
        await init_db()
        logger.info("✓ Database initialized")

        # Create default user
        logger.info("Creating default user...")
        await create_default_user()

        # Create default OAuth clients
        logger.info("Creating default OAuth clients...")
        await create_default_oauth_clients()

        print("\n" + "=" * 60)
        print("✓ Database initialization completed successfully!")
        print("=" * 60)
        print("\nYou can now test the OAuth2 flow:")
        print("\ncurl -X POST http://localhost:8003/oauth/token \\")
        print('  -d "grant_type=password" \\')
        print('  -d "username=admin" \\')
        print('  -d "password=admin123" \\')
        print('  -d "client_id=codelab-flutter-app" \\')
        print('  -d "scope=api:read api:write"')
        print()

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
