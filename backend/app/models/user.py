"""End-user (bot owner) model."""

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.bot_instance import BotInstance
    from app.models.exchange_credential import ExchangeCredential


class UserStatus(str, enum.Enum):
    """Lifecycle state of a bot-owning user."""

    active = "active"
    suspended = "suspended"


class User(Base):
    """A user who owns exactly one Freqtrade bot instance."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False), default=UserStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    bot: Mapped["BotInstance | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    exchange_credential: Mapped["ExchangeCredential | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
