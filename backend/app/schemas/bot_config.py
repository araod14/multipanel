"""Schemas for the user-editable bot settings."""

from typing import Any

from pydantic import BaseModel, Field


class StrategyOption(BaseModel):
    """A selectable strategy template."""

    key: str
    label: str
    description: str


class BotConfigOut(BaseModel):
    """The user's current editable settings plus the available choices."""

    strategy: str
    pairs: list[str]
    stake_currency: str
    stake_amount: float | str
    max_open_trades: int
    stoploss: float
    roi: float
    timeframe: str
    available_strategies: list[StrategyOption]
    available_timeframes: list[str]


class BotConfigIn(BaseModel):
    """User-submitted settings update (all fields optional; merged over current)."""

    strategy: str | None = None
    pairs: list[str] | None = None
    stake_currency: str | None = Field(default=None, max_length=10)
    stake_amount: float | str | None = None
    max_open_trades: int | None = Field(default=None, ge=1, le=50)
    stoploss: float | None = None
    roi: float | None = None
    timeframe: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return only the explicitly provided fields."""
        return self.model_dump(exclude_none=True)
