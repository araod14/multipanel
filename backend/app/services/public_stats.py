"""Fleet-wide rollup of every account's trading results, for the public page.

This is the only aggregation layer in the control plane. It fans out to each user's
Freqtrade instance over :mod:`app.services.proxy`, using a **fixed, hard-coded** set of
read-only endpoints — no path ever comes from a caller, so the deny-by-default posture
of the user proxy is preserved rather than widened.

Two properties matter because the consumer is unauthenticated:

* **A collected snapshot is cached** for ``settings.public_results_ttl`` seconds behind a
  lock, so a burst of anonymous requests collapses into a single fan-out instead of
  multiplying into one request per bot per caller.
* **A bot being down is not an error.** Configuration comes from the control-plane
  database, so an account still lists its strategy, pairs and stake with every live
  figure ``None`` and ``reachable`` false.
"""

import asyncio
import logging
import math
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models.bot_instance import BotInstance
from app.models.user import User
from app.services import bot_config, strategy_assets
from app.services.proxy import ProxyError, forward
from app.services.runtime import BotRuntime

logger = logging.getLogger("control_plane.public_stats")

# Days of profit history pulled for the sparkline.
DAILY_DAYS = 30

# Bots queried concurrently. Each bot costs one httpx connection per in-flight call.
_MAX_CONCURRENCY = 8

# The complete, closed set of Freqtrade endpoints this page reads. Read-only by
# construction: every entry is a GET, and callers cannot influence the list.
_FT_CALLS: tuple[tuple[str, dict[str, Any] | None], ...] = (
    ("profit", None),
    ("balance", None),
    ("count", None),
    ("performance", None),
    ("whitelist", None),
    ("show_config", None),
    ("daily", {"timescale": DAILY_DAYS}),
)

# (collected_at, payload) of the last successful collection.
_cache: tuple[float, dict[str, Any]] | None = None
_cache_lock = asyncio.Lock()


def invalidate() -> None:
    """Drop the cached snapshot so the next request re-collects."""
    global _cache
    _cache = None


def _num(value: Any) -> float | None:
    """Coerce a Freqtrade numeric to a JSON-safe float, or ``None``.

    Freqtrade reports an infinite profit factor for a bot with no losing trades, and
    ``json.loads`` happily produces ``inf``/``nan`` floats from it. Those cannot be
    serialised as JSON, so they are normalised away here rather than at the edge.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _int(value: Any) -> int | None:
    """Coerce a Freqtrade integer field, or ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if math.isfinite(value) else None


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


async def _fetch(
    instance: BotInstance, path: str, params: dict[str, Any] | None, sem: asyncio.Semaphore
) -> Any:
    """GET one Freqtrade endpoint, returning ``None`` on any failure.

    A single unreachable or erroring endpoint must not blank out the rest of an
    account's snapshot, so every failure mode collapses to ``None``.
    """
    async with sem:
        try:
            resp = await forward(instance, "GET", path, params=params)
        except ProxyError as exc:
            logger.info("public stats: %s %s unreachable: %s", instance.container_name, path, exc)
            return None
        if resp.status_code != 200:
            logger.info(
                "public stats: %s %s -> HTTP %s", instance.container_name, path, resp.status_code
            )
            return None
        try:
            return resp.json()
        except ValueError:
            return None


def _config_block(instance: BotInstance) -> dict[str, Any]:
    """Render the account's settings straight from the control-plane database."""
    cfg = bot_config.effective(instance.user_config_json)
    spec = strategy_assets.get_spec(cfg["strategy"])
    return {
        "strategy_key": cfg["strategy"],
        "strategy_label": spec.label,
        "pairlist_mode": cfg["pairlist_mode"],
        "pairs": list(cfg["pairs"]),
        "volume_number_assets": cfg["volume_number_assets"],
        "stake_amount": cfg["stake_amount"],
        "max_open_trades": cfg["max_open_trades"],
        "stoploss": cfg["stoploss"],
        "timeframe": cfg["timeframe"],
        "roi_table": list(cfg["roi_table"]),
        "dry_run_wallet": cfg["dry_run_wallet"],
    }


def _empty_live() -> dict[str, Any]:
    """The live half of an account snapshot, for a bot that answered nothing."""
    return {
        "bot_state": None,
        "exchange": None,
        "whitelist": None,
        "profit_closed_abs": None,
        "profit_closed_ratio": None,
        "profit_all_abs": None,
        "profit_all_ratio": None,
        "trade_count": None,
        "closed_trade_count": None,
        "winning_trades": None,
        "losing_trades": None,
        "winrate": None,
        "profit_factor": None,
        "expectancy": None,
        "expectancy_ratio": None,
        "sharpe": None,
        "sortino": None,
        "sqn": None,
        "calmar": None,
        "cagr": None,
        "max_drawdown": None,
        "max_drawdown_abs": None,
        "current_drawdown": None,
        "trading_volume": None,
        "avg_duration": None,
        "best_pair": None,
        "best_pair_profit_ratio": None,
        "first_trade_timestamp": None,
        "bot_start_timestamp": None,
        "balance_total": None,
        "balance_total_bot": None,
        "starting_capital": None,
        "starting_capital_ratio": None,
        "open_trades": None,
        "total_stake_deployed": None,
        "performance": [],
        "daily": [],
    }


def _live_block(results: dict[str, Any]) -> dict[str, Any]:
    """Map the raw Freqtrade payloads onto the public account fields."""
    profit = results.get("profit") or {}
    balance = results.get("balance") or {}
    count = results.get("count") or {}
    show_config = results.get("show_config") or {}
    performance = results.get("performance") or []
    whitelist = results.get("whitelist") or {}
    daily = (results.get("daily") or {}).get("data") or []

    block = _empty_live()
    block.update(
        {
            "bot_state": _str(show_config.get("state")),
            "exchange": _str(show_config.get("exchange")),
            "whitelist": (
                [p for p in whitelist.get("whitelist", []) if isinstance(p, str)]
                if isinstance(whitelist.get("whitelist"), list)
                else None
            ),
            "profit_closed_abs": _num(profit.get("profit_closed_coin")),
            "profit_closed_ratio": _num(profit.get("profit_closed_ratio")),
            "profit_all_abs": _num(profit.get("profit_all_coin")),
            "profit_all_ratio": _num(profit.get("profit_all_ratio")),
            "trade_count": _int(profit.get("trade_count")),
            "closed_trade_count": _int(profit.get("closed_trade_count")),
            "winning_trades": _int(profit.get("winning_trades")),
            "losing_trades": _int(profit.get("losing_trades")),
            "winrate": _num(profit.get("winrate")),
            "profit_factor": _num(profit.get("profit_factor")),
            "expectancy": _num(profit.get("expectancy")),
            "expectancy_ratio": _num(profit.get("expectancy_ratio")),
            "sharpe": _num(profit.get("sharpe")),
            "sortino": _num(profit.get("sortino")),
            "sqn": _num(profit.get("sqn")),
            "calmar": _num(profit.get("calmar")),
            "cagr": _num(profit.get("cagr")),
            "max_drawdown": _num(profit.get("max_drawdown")),
            "max_drawdown_abs": _num(profit.get("max_drawdown_abs")),
            "current_drawdown": _num(profit.get("current_drawdown")),
            "trading_volume": _num(profit.get("trading_volume")),
            "avg_duration": _str(profit.get("avg_duration")),
            "best_pair": _str(profit.get("best_pair")),
            # ``best_rate`` is the older name for the same ratio; keep both working.
            "best_pair_profit_ratio": _num(
                profit.get("best_pair_profit_ratio", profit.get("best_rate"))
            ),
            "first_trade_timestamp": _int(profit.get("first_trade_timestamp")),
            "bot_start_timestamp": _int(profit.get("bot_start_timestamp")),
            "balance_total": _num(balance.get("total")),
            "balance_total_bot": _num(balance.get("total_bot")),
            "starting_capital": _num(balance.get("starting_capital")),
            "starting_capital_ratio": _num(balance.get("starting_capital_ratio")),
            "open_trades": _int(count.get("current")),
            "total_stake_deployed": _num(count.get("total_stake")),
            "performance": [
                {
                    "pair": e["pair"],
                    "profit_abs": _num(e.get("profit_abs")),
                    "profit_ratio": _num(e.get("profit_ratio")),
                    "count": _int(e.get("count")) or 0,
                }
                for e in performance
                if isinstance(e, dict) and isinstance(e.get("pair"), str)
            ],
            "daily": [
                {
                    "date": str(d.get("date")),
                    "abs_profit": _num(d.get("abs_profit")),
                    "rel_profit": _num(d.get("rel_profit")),
                    "trade_count": _int(d.get("trade_count")) or 0,
                }
                for d in daily
                if isinstance(d, dict)
            ],
        }
    )
    return block


async def _collect_account(
    user: User, instance: BotInstance, container_state: str | None, sem: asyncio.Semaphore
) -> dict[str, Any]:
    """Build one account's snapshot: DB config always, live figures best-effort."""
    account: dict[str, Any] = {
        "username": user.username,
        "container_state": container_state,
        "trading_enabled": instance.trading_enabled,
        "dry_run": instance.dry_run,
        **_config_block(instance),
    }

    # Skip the fan-out entirely for a container that is not up: it would only buy us
    # seven connection timeouts per stopped bot.
    if container_state != "running":
        return {**account, "reachable": False, **_empty_live()}

    payloads = await asyncio.gather(
        *(_fetch(instance, path, params, sem) for path, params in _FT_CALLS)
    )
    results = {path: payload for (path, _), payload in zip(_FT_CALLS, payloads)}
    reachable = results.get("profit") is not None
    return {**account, "reachable": reachable, **_live_block(results)}


def _container_states(names: list[str]) -> dict[str, str | None]:
    """Read the live Docker status of each container.

    ``BotInstance.status`` is only written on lifecycle actions, so it goes stale as
    soon as a container exits on its own; Docker is the only honest source.
    """
    try:
        runtime = BotRuntime()
    except Exception as exc:  # docker daemon unavailable
        logger.warning("public stats: docker unavailable: %s", exc)
        return {name: None for name in names}
    states: dict[str, str | None] = {}
    for name in names:
        try:
            states[name] = runtime.status(name)
        except Exception as exc:
            logger.info("public stats: status(%s) failed: %s", name, exc)
            states[name] = None
    return states


def _totals(accounts: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum the fleet-wide figures over the accounts that reported them."""

    def total(field: str) -> float:
        return sum(a[field] for a in accounts if isinstance(a.get(field), (int, float)))

    wins = int(total("winning_trades"))
    losses = int(total("losing_trades"))
    decided = wins + losses
    return {
        "accounts": len(accounts),
        "reachable": sum(1 for a in accounts if a["reachable"]),
        "running": sum(1 for a in accounts if a["container_state"] == "running"),
        "live_accounts": sum(1 for a in accounts if not a["dry_run"]),
        "dry_accounts": sum(1 for a in accounts if a["dry_run"]),
        "profit_closed_abs": total("profit_closed_abs"),
        "profit_all_abs": total("profit_all_abs"),
        "closed_trade_count": int(total("closed_trade_count")),
        "winning_trades": wins,
        "losing_trades": losses,
        "winrate": (wins / decided) if decided else None,
        "open_trades": int(total("open_trades")),
        "total_stake_deployed": total("total_stake_deployed"),
        "balance_total": total("balance_total"),
    }


async def _collect_uncached(db: Session) -> dict[str, Any]:
    """Collect a fresh snapshot of every provisioned account."""
    rows = db.scalars(
        select(User).options(selectinload(User.bot)).order_by(User.username)
    ).all()
    pairs = [(u, u.bot) for u in rows if u.bot is not None]

    states = await asyncio.to_thread(
        _container_states, [instance.container_name for _, instance in pairs]
    )

    sem = asyncio.Semaphore(_MAX_CONCURRENCY)
    accounts = await asyncio.gather(
        *(
            _collect_account(user, instance, states.get(instance.container_name), sem)
            for user, instance in pairs
        )
    )
    accounts = list(accounts)
    # Best performers first; an account with no figures yet sorts last.
    accounts.sort(
        key=lambda a: a["profit_all_abs"] if isinstance(a["profit_all_abs"], float) else -math.inf,
        reverse=True,
    )
    return {
        "generated_at": datetime.now(UTC),
        "stake_currency": bot_config.STAKE_CURRENCY,
        "totals": _totals(accounts),
        "accounts": accounts,
    }


async def collect(db: Session) -> dict[str, Any]:
    """Return the public rollup, reusing a recent snapshot when one exists."""
    global _cache
    ttl = get_settings().public_results_ttl
    now = time.monotonic()

    cached = _cache
    if cached is not None and now - cached[0] < ttl:
        return cached[1]

    async with _cache_lock:
        # Re-check: another request may have refreshed while we waited for the lock.
        cached = _cache
        if cached is not None and time.monotonic() - cached[0] < ttl:
            return cached[1]
        payload = await _collect_uncached(db)
        _cache = (time.monotonic(), payload)
        return payload
