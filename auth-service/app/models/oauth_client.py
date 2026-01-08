"""OAuth Client model"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class OAuthClient(Base):
    """OAuth Client model for client applications"""

    __tablename__ = "oauth_clients"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Client identification
    client_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    client_secret_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # NULL for public clients
    )

    # Client information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Client type
    is_confidential: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Permissions
    allowed_scopes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Space-separated list of allowed scopes",
    )
    allowed_grant_types: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON array of allowed grant types",
    )

    # Token lifetimes (in seconds)
    access_token_lifetime: Mapped[int] = mapped_column(
        Integer,
        default=900,  # 15 minutes
        nullable=False,
    )
    refresh_token_lifetime: Mapped[int] = mapped_column(
        Integer,
        default=2592000,  # 30 days
        nullable=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<OAuthClient(id={self.id}, client_id={self.client_id}, name={self.name})>"
