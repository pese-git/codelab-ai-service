"""OAuth Client service"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import logger
from app.models.oauth_client import OAuthClient
from app.schemas.oauth import GrantType, OAuthClientCreate
from app.utils.crypto import hash_password, verify_password


class OAuthClientService:
    """Service for OAuth client management"""

    async def create_client(
        self,
        db: AsyncSession,
        client_data: OAuthClientCreate,
    ) -> OAuthClient:
        """
        Create a new OAuth client
        
        Args:
            db: Database session
            client_data: Client creation data
            
        Returns:
            Created OAuth client
            
        Raises:
            ValueError: If client already exists
        """
        # Check if client already exists
        existing = await self.get_by_client_id(db, client_data.client_id)
        if existing:
            raise ValueError(f"Client with client_id '{client_data.client_id}' already exists")

        # Hash client secret if provided
        client_secret_hash = None
        if client_data.client_secret:
            client_secret_hash = hash_password(client_data.client_secret)

        # Convert grant types to JSON
        grant_types_json = json.dumps([gt.value for gt in client_data.allowed_grant_types])

        # Create client
        client = OAuthClient(
            client_id=client_data.client_id,
            client_secret_hash=client_secret_hash,
            name=client_data.name,
            description=client_data.description,
            is_confidential=client_data.is_confidential,
            allowed_scopes=client_data.allowed_scopes,
            allowed_grant_types=grant_types_json,
            access_token_lifetime=client_data.access_token_lifetime,
            refresh_token_lifetime=client_data.refresh_token_lifetime,
        )

        db.add(client)
        await db.commit()
        await db.refresh(client)

        logger.info(f"OAuth client created: {client.client_id}")

        return client

    async def get_by_client_id(
        self,
        db: AsyncSession,
        client_id: str,
    ) -> OAuthClient | None:
        """
        Get OAuth client by client_id
        
        Args:
            db: Database session
            client_id: Client ID
            
        Returns:
            OAuth client or None if not found
        """
        result = await db.execute(
            select(OAuthClient).where(OAuthClient.client_id == client_id)
        )
        return result.scalar_one_or_none()

    async def validate_client(
        self,
        db: AsyncSession,
        client_id: str,
        client_secret: str | None = None,
    ) -> OAuthClient | None:
        """
        Validate OAuth client credentials
        
        Args:
            db: Database session
            client_id: Client ID
            client_secret: Client secret (for confidential clients)
            
        Returns:
            OAuth client if valid, None otherwise
        """
        client = await self.get_by_client_id(db, client_id)
        if not client:
            logger.warning(f"Client validation failed: client not found ({client_id})")
            return None

        # Check if client is active
        if not client.is_active:
            logger.warning(f"Client validation failed: client inactive ({client_id})")
            return None

        # Validate client secret for confidential clients
        if client.is_confidential:
            if not client_secret:
                logger.warning(f"Client validation failed: missing secret ({client_id})")
                return None

            if not verify_password(client_secret, client.client_secret_hash):
                logger.warning(f"Client validation failed: invalid secret ({client_id})")
                return None

        logger.debug(f"Client validated: {client_id}")
        return client

    def validate_grant_type(
        self,
        client: OAuthClient,
        grant_type: GrantType,
    ) -> bool:
        """
        Validate if grant type is allowed for client
        
        Args:
            client: OAuth client
            grant_type: Grant type to validate
            
        Returns:
            True if allowed, False otherwise
        """
        try:
            allowed_grant_types = json.loads(client.allowed_grant_types)
            is_allowed = grant_type.value in allowed_grant_types

            if not is_allowed:
                logger.warning(
                    f"Grant type not allowed: {grant_type.value} for client {client.client_id}"
                )

            return is_allowed

        except json.JSONDecodeError:
            logger.error(f"Invalid grant_types JSON for client {client.client_id}")
            return False

    def validate_scope(
        self,
        client: OAuthClient,
        requested_scope: str | None,
    ) -> tuple[bool, str]:
        """
        Validate and normalize requested scope
        
        Args:
            client: OAuth client
            requested_scope: Requested scope (space-separated)
            
        Returns:
            Tuple of (is_valid, normalized_scope)
        """
        # Get allowed scopes
        allowed_scopes = set(client.allowed_scopes.split())

        # If no scope requested, use all allowed scopes
        if not requested_scope:
            return True, client.allowed_scopes

        # Validate requested scopes
        requested_scopes = set(requested_scope.split())

        # Check if all requested scopes are allowed
        invalid_scopes = requested_scopes - allowed_scopes
        if invalid_scopes:
            logger.warning(
                f"Invalid scopes requested: {invalid_scopes} for client {client.client_id}"
            )
            return False, ""

        # Return normalized scope (sorted, space-separated)
        normalized_scope = " ".join(sorted(requested_scopes))
        return True, normalized_scope


# Global instance
oauth_client_service = OAuthClientService()
