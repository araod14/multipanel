"""Schemas for managing a user's exchange API credentials and trading mode."""

import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExchangeName(str, enum.Enum):
    """Exchanges the control plane will accept real credentials for.

    Note ``binance`` and ``binanceus`` are distinct exchanges with incompatible keys
    (freqtrade docs/exchanges.md "Binance sites"), so this is an exact id, not a family.
    """

    binance = "binance"


class ExchangeCredentialIn(BaseModel):
    """Admin payload to set/replace a user's exchange API credentials.

    Secrets are write-only: they are encrypted on receipt and never returned.
    """

    exchange_name: ExchangeName
    key: str = Field(..., min_length=1)
    secret: str = Field(..., min_length=1)
    password: str | None = None
    uid: str | None = None


class ExchangeCredentialOut(BaseModel):
    """Non-secret metadata about a stored exchange credential.

    ``exchange_name`` is a plain ``str`` on purpose while the input side is an enum:
    strict on write, permissive on read. A row stored before the allowlist existed must
    stay readable, or an admin could not even see it in order to delete it.
    """

    model_config = ConfigDict(from_attributes=True)

    exchange_name: str
    key_masked: str
    has_password: bool
    has_uid: bool
    updated_at: datetime
    # Populated by the probe when credentials are set; absent on a plain read.
    verified: bool | None = None
    can_withdraw: bool | None = None
    balance: float | None = None


class ExchangeOptionsOut(BaseModel):
    """Exchanges the admin UI may offer, so it never hardcodes the list."""

    supported: list[str]
    default: str


class BotModeIn(BaseModel):
    """Toggle a user's bot between dry-run and live trading."""

    dry_run: bool
