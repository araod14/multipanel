"""Persistent entry protection and command coordination (one API worker)."""

import asyncio
import logging
from datetime import UTC, datetime
from weakref import WeakValueDictionary

from sqlalchemy.orm import Session

from app.models.bot_instance import BotInstance
from app.services import audit, proxy

logger = logging.getLogger("control_plane.trading_guard")
_locks: WeakValueDictionary[int, asyncio.Lock] = WeakValueDictionary()


def bot_lock(instance_id: int) -> asyncio.Lock:
    lock = _locks.get(instance_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[instance_id] = lock
    return lock


def evaluate(pairs: set[str], timeframe: str, exchange: str, values: dict) -> dict:
    """No missing value or neutral coin may reduce the majority denominator."""
    buy = sell = neutral = missing = 0
    for pair in pairs:
        value = values.get((pair, timeframe))
        if value is None:
            missing += 1
        elif value >= 0.1:
            buy += 1
        elif value <= -0.1:
            sell += 1
        else:
            neutral += 1
    complete = bool(pairs) and missing == 0
    reason = "missing_data"
    if complete:
        reason = "all_sell" if sell == len(pairs) else (
            "majority_buy" if buy * 2 > len(pairs) else "mixed"
        )
    return dict(
        checked_at=datetime.now(UTC).isoformat(), timeframe=timeframe, exchange=exchange,
        total=len(pairs), buy=buy, sell=sell, neutral=neutral, missing=missing,
        data_complete=complete, reason=reason,
    )


def apply_evaluation(db: Session, instance: BotInstance, evaluation: dict) -> None:
    """Persist guard intent before commanding Freqtrade, so failed actions retry."""
    previous = instance.tradingview_paused
    instance.tradingview_evaluation = evaluation
    if evaluation["data_complete"]:
        if evaluation["reason"] == "all_sell":
            instance.tradingview_paused = True
        elif evaluation["reason"] == "majority_buy":
            instance.tradingview_paused = False
    if previous != instance.tradingview_paused:
        action = "tradingview.pause" if instance.tradingview_paused else "tradingview.resume"
        audit.record(db, actor="system:tradingview", action=action,
                     target_user_id=instance.user_id, detail=evaluation["reason"])
        logger.info("%s bot=%s", action, instance.id)


async def sync_state(db: Session, instance: BotInstance, state: str | None = None) -> str | None:
    """Caller holds bot_lock. Return the command accepted, or None.

    Manual stops always win. An external paused bot is left alone unless this
    control plane owns its pause. pause works from stopped too, restoring exit
    management after a restart without briefly enabling entries.
    """
    if not instance.trading_enabled:
        return None
    if state is None:
        resp = await proxy.forward(instance, "GET", "show_config")
        if resp.status_code != 200:
            return None
        state = resp.json().get("state")
    if not isinstance(state, str):
        return None
    state = state.lower()
    paused = instance.manual_paused or (
        instance.tradingview_guard_enabled and instance.tradingview_paused
    )
    command = None
    if paused and state in {"running", "stopped"}:
        command = "pause"
    elif not paused and (state == "stopped" or (
        state == "paused" and instance.entry_pause_managed
    )):
        command = "start"
    if command is None:
        if instance.entry_pause_managed and state == "running" and not paused:
            instance.entry_pause_managed = False
            instance.entry_pause_pending = False
            db.commit()
        elif instance.entry_pause_pending and state == "paused":
            # A previous pause may have reached Freqtrade even if its response was
            # lost. Confirm it without mistaking it for an unrelated external pause.
            instance.entry_pause_pending = False
            db.commit()
        return None
    if command == "pause":
        # Claim only a pause we actually request (never an already external pause).
        # Persist before I/O: transport failure does not prove the command failed.
        instance.entry_pause_managed = True
        instance.entry_pause_pending = True
        db.commit()
    resp = await proxy.forward(instance, "POST", command)
    if resp.status_code != 200:
        logger.warning("bot=%s %s rejected: HTTP %s", instance.id, command, resp.status_code)
        return None
    instance.entry_pause_managed = command == "pause"
    instance.entry_pause_pending = False
    audit.record(db, actor="system:reconciler", action=f"trading.{command}",
                 target_user_id=instance.user_id)
    db.commit()
    return command
