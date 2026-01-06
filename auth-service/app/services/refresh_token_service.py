"""Refresh Token service for token rotation"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import logger
from app.models.refresh_token import RefreshToken
from app.schemas.token import RefreshTokenPayload
from app.utils.crypto import hash_token_jti


class RefreshTokenService:
    """Service for refresh token management and rotation"""

    async def save_refresh_token(
        self,
        db: AsyncSession,
        payload: RefreshTokenPayload,
        parent_jti: str | None = None,
    ) -> RefreshToken:
        """
        Save refresh token to database
        
        Args:
            db: Database session
            payload: Refresh token payload
            parent_jti: Parent token JTI (for rotation chain)
            
        Returns:
            Created RefreshToken record
        """
        # Hash JTI
        jti_hash = hash_token_jti(payload.jti)
        parent_jti_hash = hash_token_jti(parent_jti) if parent_jti else None

        # Create refresh token record
        refresh_token = RefreshToken(
            jti_hash=jti_hash,
            user_id=payload.sub,
            client_id=payload.client_id,
            scope=payload.scope,
            expires_at=datetime.fromtimestamp(payload.exp, tz=timezone.utc),
            parent_jti_hash=parent_jti_hash,
        )

        db.add(refresh_token)
        await db.commit()
        await db.refresh(refresh_token)

        logger.debug(f"Refresh token saved: {jti_hash[:16]}...")

        return refresh_token

    async def get_by_jti(
        self,
        db: AsyncSession,
        jti: str,
    ) -> RefreshToken | None:
        """
        Get refresh token by JTI
        
        Args:
            db: Database session
            jti: JWT ID
            
        Returns:
            RefreshToken or None if not found
        """
        jti_hash = hash_token_jti(jti)

        result = await db.execute(
            select(RefreshToken).where(RefreshToken.jti_hash == jti_hash)
        )
        return result.scalar_one_or_none()

    async def validate_refresh_token(
        self,
        db: AsyncSession,
        jti: str,
    ) -> tuple[bool, str | None]:
        """
        Validate refresh token
        
        Args:
            db: Database session
            jti: JWT ID
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        token = await self.get_by_jti(db, jti)

        if not token:
            return False, "Refresh token not found"

        if token.revoked:
            # SECURITY: Refresh token reuse detected!
            logger.warning(
                f"SECURITY: Refresh token reuse detected! "
                f"jti={jti[:16]}..., user_id={token.user_id}"
            )
            # Revoke all tokens in the chain
            await self.revoke_token_chain(db, token)
            return False, "Refresh token has been revoked (reuse detected)"

        if token.is_expired:
            return False, "Refresh token has expired"

        return True, None

    async def revoke_token(
        self,
        db: AsyncSession,
        jti: str,
    ) -> bool:
        """
        Revoke a refresh token
        
        Args:
            db: Database session
            jti: JWT ID
            
        Returns:
            True if revoked, False if not found
        """
        token = await self.get_by_jti(db, jti)
        if not token:
            return False

        token.revoked = True
        token.revoked_at = datetime.now(timezone.utc)

        await db.commit()

        logger.info(f"Refresh token revoked: {jti[:16]}...")

        return True

    async def revoke_token_chain(
        self,
        db: AsyncSession,
        token: RefreshToken,
    ) -> None:
        """
        Revoke entire token chain (for security incidents)
        
        Args:
            db: Database session
            token: RefreshToken that was reused
        """
        # Revoke the token itself
        token.revoked = True
        token.revoked_at = datetime.now(timezone.utc)

        # Find and revoke all tokens in the chain
        # (tokens with same user_id and client_id)
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == token.user_id,
                RefreshToken.client_id == token.client_id,
                RefreshToken.revoked == False,
            )
        )
        tokens_to_revoke = result.scalars().all()

        for t in tokens_to_revoke:
            t.revoked = True
            t.revoked_at = datetime.now(timezone.utc)

        await db.commit()

        logger.warning(
            f"SECURITY: Revoked {len(tokens_to_revoke)} tokens in chain "
            f"for user {token.user_id}"
        )

    async def cleanup_expired_tokens(
        self,
        db: AsyncSession,
        days_to_keep: int = 7,
    ) -> int:
        """
        Delete expired refresh tokens older than specified days
        
        Args:
            db: Database session
            days_to_keep: Number of days to keep expired tokens
            
        Returns:
            Number of deleted tokens
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        result = await db.execute(
            select(RefreshToken).where(RefreshToken.expires_at < cutoff_date)
        )
        tokens_to_delete = result.scalars().all()

        for token in tokens_to_delete:
            await db.delete(token)

        await db.commit()

        count = len(tokens_to_delete)
        if count > 0:
            logger.info(f"Cleaned up {count} expired refresh tokens")

        return count


# Global instance
refresh_token_service = RefreshTokenService()
