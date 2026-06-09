"""Encrypted exchange API credentials, one set per user."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ExchangeCredential(Base):
    """A user's exchange API credentials, stored as Fernet-encrypted blobs.

    Only ``exchange_name`` is plaintext. The key/secret/password/uid columns hold
    ciphertext produced by :mod:`app.security.vault`; they are decrypted in-memory
    only when launching the user's container and injected as ``FREQTRADE__*`` env.
    """

    __tablename__ = "exchange_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    exchange_name: Mapped[str] = mapped_column(String(64))

    key_enc: Mapped[str] = mapped_column(String(1024))
    secret_enc: Mapped[str] = mapped_column(String(1024))
    password_enc: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    uid_enc: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped["User"] = relationship(back_populates="exchange_credential")
