"""Schemas for the user-editable bot settings."""

from typing import Any

from pydantic import BaseModel, Field


class StrategyOption(BaseModel):
    """A selectable strategy template."""

    key: str
    label: str
    description: str


class RoiStep(BaseModel):
    """One step of the minimal-ROI table: take ``roi`` profit after ``minutes``."""

    minutes: int = Field(ge=0)
    roi: float


class BotConfigOut(BaseModel):
    """The user's current editable settings plus the available choices."""

    strategy: str
    pairlist_mode: str
    pairs: list[str]
    volume_number_assets: int
    stake_currency: str
    stake_amount: float | str
    max_open_trades: int
    stoploss: float
    roi_table: list[RoiStep]
    timeframe: str
    trailing_stop: bool
    trailing_stop_positive: float | None
    trailing_stop_positive_offset: float
    dry_run_wallet: float
    available_strategies: list[StrategyOption]
    available_timeframes: list[str]
    available_pairlist_modes: list[str]


class BotConfigIn(BaseModel):
    """User-submitted settings update (all fields optional; merged over current)."""

    strategy: str | None = None
    pairlist_mode: str | None = None
    pairs: list[str] | None = None
    volume_number_assets: int | None = Field(default=None, ge=1, le=100)
    stake_amount: float | str | None = None
    max_open_trades: int | None = Field(default=None, ge=1, le=50)
    stoploss: float | None = None
    roi: float | None = None  # legacy single-value ROI, upgraded to roi_table on merge
    roi_table: list[RoiStep] | None = None
    timeframe: str | None = None
    trailing_stop: bool | None = None
    trailing_stop_positive: float | None = None
    trailing_stop_positive_offset: float | None = None
    dry_run_wallet: float | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return only the explicitly provided fields."""
        payload = self.model_dump(exclude_none=True)
        if "roi_table" in payload:
            payload["roi_table"] = [dict(s) for s in payload["roi_table"]]
        return payload
