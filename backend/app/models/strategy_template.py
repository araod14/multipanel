"""Strategy template model — reusable non-secret trade defaults assigned to users."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StrategyTemplate(Base):
    """A named bundle of non-secret config defaults plus the strategy class to run.

    ``base_config_json`` holds only NON-secret Freqtrade config fragments
    (pairlists, minimal_roi, stoploss, timeframe, pricing, etc.). Secrets are never
    stored here — they live encrypted on :class:`ExchangeCredential`.
    """

    __tablename__ = "strategy_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    strategy_class_name: Mapped[str] = mapped_column(String(128))
    base_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
