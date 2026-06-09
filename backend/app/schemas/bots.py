"""Bot instance schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
    stake_currency: str
    created_at: datetime
    last_seen_at: datetime | None
