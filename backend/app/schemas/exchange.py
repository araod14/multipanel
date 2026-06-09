"""Schemas for managing a user's exchange API credentials and trading mode."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExchangeCredentialIn(BaseModel):
    """Admin payload to set/replace a user's exchange API credentials.

    Secrets are write-only: they are encrypted on receipt and never returned.
    """

    exchange_name: str = Field(..., min_length=2, max_length=64)
    key: str = Field(..., min_length=1)
    secret: str = Field(..., min_length=1)
    password: str | None = None
    uid: str | None = None


class ExchangeCredentialOut(BaseModel):
    """Non-secret metadata about a stored exchange credential."""

    model_config = ConfigDict(from_attributes=True)

    exchange_name: str
    key_masked: str
    has_password: bool
    has_uid: bool
    updated_at: datetime


class BotModeIn(BaseModel):
    """Toggle a user's bot between dry-run and live trading."""

    dry_run: bool
