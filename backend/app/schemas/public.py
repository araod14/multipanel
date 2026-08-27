"""Schemas for the unauthenticated public results page.

These models are the security boundary of ``GET /api/public/results``: the endpoint is
reachable by anyone, so only fields declared here are ever serialized. Nothing that
identifies infrastructure (container name, internal hostname), nothing from a user row
beyond the username, and nothing encrypted (``*_enc``) or credential-shaped may be
added. When in doubt, leave it out — see also the field allowlist test in
``smoke_public.py``.
"""

from datetime import datetime

from pydantic import BaseModel


class PublicPairPerf(BaseModel):
    """Realised profit for one traded pair (from Freqtrade's ``/performance``)."""

    pair: str
    profit_abs: float | None
    profit_ratio: float | None
    count: int


class PublicDailyPoint(BaseModel):
    """One day of the profit series (from Freqtrade's ``/daily``)."""

    date: str
    abs_profit: float | None
    rel_profit: float | None
    trade_count: int


class PublicAccount(BaseModel):
    """One account's public snapshot.

    Config fields come from the control-plane database and are therefore always
    present; every live figure is ``None`` when the bot could not be reached, which
    ``reachable`` reports explicitly.
    """

    # --- identity / state ---
    username: str
    reachable: bool
    container_state: str | None
    bot_state: str | None
    # What the owner asked for, so a reader can tell "stopped on purpose" apart from
    # "stopped by accident and about to be resumed".
    trading_enabled: bool
    dry_run: bool
    exchange: str | None

    # --- configuration (from the control plane DB, always available) ---
    strategy_key: str
    strategy_label: str
    pairlist_mode: str
    pairs: list[str]
    volume_number_assets: int
    stake_amount: float | str
    max_open_trades: int
    stoploss: float
    timeframe: str
    roi_table: list[dict]
    dry_run_wallet: float

    # --- pairs actually being traded (a volume pairlist is only known at runtime) ---
    whitelist: list[str] | None

    # --- results ---
    profit_closed_abs: float | None
    profit_closed_ratio: float | None
    profit_all_abs: float | None
    profit_all_ratio: float | None
    trade_count: int | None
    closed_trade_count: int | None
    winning_trades: int | None
    losing_trades: int | None
    winrate: float | None
    profit_factor: float | None
    expectancy: float | None
    expectancy_ratio: float | None
    sharpe: float | None
    sortino: float | None
    sqn: float | None
    calmar: float | None
    cagr: float | None
    max_drawdown: float | None
    max_drawdown_abs: float | None
    current_drawdown: float | None
    trading_volume: float | None
    avg_duration: str | None
    best_pair: str | None
    best_pair_profit_ratio: float | None
    first_trade_timestamp: int | None
    bot_start_timestamp: int | None

    # --- amounts ---
    balance_total: float | None
    balance_total_bot: float | None
    starting_capital: float | None
    starting_capital_ratio: float | None
    open_trades: int | None
    total_stake_deployed: float | None

    # --- breakdowns ---
    performance: list[PublicPairPerf]
    daily: list[PublicDailyPoint]


class PublicTotals(BaseModel):
    """Fleet-wide rollup across the reachable accounts."""

    accounts: int
    reachable: int
    running: int
    live_accounts: int
    dry_accounts: int
    profit_closed_abs: float
    profit_all_abs: float
    closed_trade_count: int
    winning_trades: int
    losing_trades: int
    winrate: float | None
    open_trades: int
    total_stake_deployed: float
    balance_total: float


class PublicResultsOut(BaseModel):
    """The whole public page payload."""

    generated_at: datetime
    stake_currency: str
    totals: PublicTotals
    accounts: list[PublicAccount]
