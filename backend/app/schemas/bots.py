"""Bot instance schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.models.bot_instance import BotStatus


class BotInstanceOut(BaseModel):
    """Bot instance representation (no secrets)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    container_name: str
    internal_hostname: str
    status: BotStatus
    dry_run: bool
    # Whether the owner wants this bot trading. ``status`` is the container; this is the
    # trading loop inside it, which the reconciler restores after a reboot.
    trading_enabled: bool
    stake_currency: str
    created_at: datetime
    last_seen_at: datetime | None
    # Not stored on the instance: filled from settings so the UI can state the ceiling it
    # is about to enable. ``default_factory`` runs per response, so it tracks the config.
    live_max_capital: float = Field(default_factory=lambda: get_settings().live_max_capital)
