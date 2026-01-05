"""Audit service for security events logging"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import logger
from app.models.audit_log import AuditLog


class AuditService:
    """Service for audit logging"""

    async def log_event(
        self,
        db: AsyncSession,
        event_type: str,
        success: bool,
        user_id: str | None = None,
        client_id: str | None = None,
        event_data: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        error_message: str | None = None,
    ) -> AuditLog:
        """
        Log an audit event
        
        Args:
            db: Database session
            event_type: Type of event (login_success, login_failed, etc.)
            success: Whether the event was successful
            user_id: User ID (if applicable)
            client_id: OAuth client ID (if applicable)
            event_data: Additional event data
            ip_address: Client IP address
            user_agent: Client user agent
            error_message: Error message (if failed)
            
        Returns:
            Created AuditLog record
        """
        audit_log = AuditLog(
            user_id=user_id,
            client_id=client_id,
            event_type=event_type,
            event_data=event_data,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )

        db.add(audit_log)
        await db.commit()
        await db.refresh(audit_log)

        # Also log to application logs
        log_level = logger.info if success else logger.warning
        log_level(
            f"Audit: {event_type} - {'SUCCESS' if success else 'FAILED'}",
            extra={
                "event_type": event_type,
                "success": success,
                "user_id": user_id,
                "client_id": client_id,
                "ip_address": ip_address,
            },
        )

        return audit_log

    async def log_login_success(
        self,
        db: AsyncSession,
        user_id: str,
        client_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        scope: str | None = None,
    ) -> AuditLog:
        """Log successful login"""
        return await self.log_event(
            db=db,
            event_type="login_success",
            success=True,
            user_id=user_id,
            client_id=client_id,
            event_data={"scope": scope} if scope else None,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_login_failed(
        self,
        db: AsyncSession,
        username: str,
        client_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        reason: str | None = None,
    ) -> AuditLog:
        """Log failed login attempt"""
        return await self.log_event(
            db=db,
            event_type="login_failed",
            success=False,
            user_id=None,  # User not authenticated
            client_id=client_id,
            event_data={"username": username},
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=reason,
        )

    async def log_token_refresh(
        self,
        db: AsyncSession,
        user_id: str,
        client_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log token refresh"""
        return await self.log_event(
            db=db,
            event_type="token_refresh",
            success=True,
            user_id=user_id,
            client_id=client_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_token_revoke(
        self,
        db: AsyncSession,
        user_id: str,
        client_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log token revocation"""
        return await self.log_event(
            db=db,
            event_type="token_revoke",
            success=True,
            user_id=user_id,
            client_id=client_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_security_incident(
        self,
        db: AsyncSession,
        incident_type: str,
        user_id: str | None = None,
        client_id: str | None = None,
        event_data: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log security incident (e.g., refresh token reuse)"""
        return await self.log_event(
            db=db,
            event_type=f"security_incident_{incident_type}",
            success=False,
            user_id=user_id,
            client_id=client_id,
            event_data=event_data,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=f"Security incident: {incident_type}",
        )


# Global instance
audit_service = AuditService()
