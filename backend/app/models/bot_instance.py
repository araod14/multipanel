"""Per-user Freqtrade bot instance model."""

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class BotStatus(str, enum.Enum):
    """Lifecycle state of a bot instance (container-level)."""

    provisioned = "provisioned"
    running = "running"
    stopped = "stopped"
    error = "error"


class BotInstance(Base):
    """Bookkeeping for the single Freqtrade container owned by a user.

    The generated Freqtrade ``api_server`` credentials are stored ENCRYPTED — the
    proxy layer decrypts them in-memory to obtain a JWT from the instance. The
    container is addressed by ``internal_hostname`` on a private docker network
    (always port 8080 internally), so no host port is published.
    """

    __tablename__ = "bot_instances"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    strategy_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("strategy_templates.id"), nullable=True
    )

    container_name: Mapped[str] = mapped_column(String(128), unique=True)
    internal_hostname: Mapped[str] = mapped_column(String(128))
    status: Mapped[BotStatus] = mapped_column(
        Enum(BotStatus, native_enum=False), default=BotStatus.provisioned
    )

    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    # DESIRED trading state, as opposed to ``status`` (which tracks the container).
    # Freqtrade containers boot with ``initial_state: stopped`` and forget they were
    # trading, so after a host reboot every bot silently sits idle. This records what
    # the user asked for; ``services/reconciler.py`` makes reality match it again.
    # False by default: a new bot has not been started yet.
    trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    stake_currency: Mapped[str] = mapped_column(String(16), default="USDT")
    db_path: Mapped[str] = mapped_column(String(255))

    # User-editable Freqtrade settings (safe whitelist; see services/bot_config.py).
    user_config_json: Mapped[dict] = mapped_column(JSON, default=dict)

    # Generated Freqtrade api_server credentials (encrypted at rest).
    api_username: Mapped[str] = mapped_column(String(64))
    api_password_enc: Mapped[str] = mapped_column(String(512))
    jwt_secret_enc: Mapped[str] = mapped_column(String(512))
    ws_token_enc: Mapped[str] = mapped_column(String(512))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="bot")
