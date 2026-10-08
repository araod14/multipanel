"""Restore owner intent and evaluate TradingView entry protection every minute."""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import SessionLocal
from app.models.bot_instance import BotInstance
from app.models.user import User
from app.services import bot_config, proxy, trading_guard, tradingview
from app.services.proxy import ProxyError
from app.services.runtime import BotRuntime

logger = logging.getLogger("control_plane.reconciler")


def _exchange(instance: BotInstance) -> str:
    cred = instance.user.exchange_credential
    return cred.exchange_name if cred else get_settings().default_exchange


async def reconcile_once() -> dict[str, int]:
    """Batch fresh scanner queries, then re-read intent under each bot's lock."""
    tally = {"checked": 0, "resumed": 0, "paused": 0, "failed": 0}
    with SessionLocal() as db:
        instances = list(db.scalars(select(BotInstance).options(
            selectinload(BotInstance.user).selectinload(User.exchange_credential)
        )).all())
        if not instances:
            return tally
        states = await asyncio.to_thread(_container_states, [i.container_name for i in instances])
        snapshots = {}
        sem = asyncio.Semaphore(8)

        async def collect(instance):
            if states.get(instance.container_name) != "running":
                return
            async with sem:
                db.refresh(instance)
                cfg = bot_config.effective(instance.user_config_json)
                exchange = _exchange(instance)
                pairs = set()
                try:
                    pairs_resp = await proxy.forward(instance, "GET", "whitelist")
                    if pairs_resp.status_code == 200:
                        raw = pairs_resp.json().get("whitelist")
                        if isinstance(raw, list) and all(isinstance(p, str) for p in raw):
                            pairs = set(raw)
                except (ProxyError, ValueError, AttributeError):
                    logger.info("reconciler: bot=%s data unavailable", instance.id)
                # An unavailable runtime list is missing data, even for static bots.
                snapshots[instance.id] = (cfg, exchange, pairs)

        await asyncio.gather(*(collect(i) for i in instances))
        grouped = {}
        for cfg, exchange, pairs in snapshots.values():
            if cfg["tradingview_guard_enabled"]:
                grouped.setdefault(exchange, {}).setdefault(cfg["timeframe"], set()).update(pairs)
        exchanges = list(grouped)
        fetched = await asyncio.gather(*(
            tradingview.ratings(grouped[e], exchange=e) for e in exchanges
        ))
        ratings_by_exchange = dict(zip(exchanges, fetched))

    # Do not reuse the collecting session: manual commands/config may have changed
    # while the scanner was in flight. The fingerprint rejects obsolete config data.
    for instance_id, (cfg, exchange, pairs) in snapshots.items():
        async with trading_guard.bot_lock(instance_id):
            with SessionLocal() as db:
                instance = db.get(BotInstance, instance_id)
                if instance is None:
                    continue
                if bot_config.effective(instance.user_config_json) != cfg or _exchange(instance) != exchange:
                    continue
                tally["checked"] += 1
                try:
                    if instance.tradingview_guard_enabled:
                        evaluation = trading_guard.evaluate(
                            pairs, cfg["timeframe"], exchange, ratings_by_exchange.get(exchange, {})
                        )
                        trading_guard.apply_evaluation(db, instance, evaluation)
                        db.commit()
                    command = await trading_guard.sync_state(db, instance)
                    if command == "start":
                        tally["resumed"] += 1
                    elif command == "pause":
                        tally["paused"] += 1
                except ProxyError:
                    logger.info("reconciler: bot=%s unreachable", instance_id)
                except Exception:
                    tally["failed"] += 1
                    logger.exception("reconciler: bot=%s failed", instance_id)
    return tally


def _container_states(names: list[str]) -> dict[str, str | None]:
    try:
        runtime = BotRuntime()
    except Exception as exc:  # docker daemon unavailable
        logger.warning("reconciler: docker unavailable: %s", exc)
        return {name: None for name in names}
    states: dict[str, str | None] = {}
    for name in names:
        try:
            states[name] = runtime.status(name)
        except Exception:
            states[name] = None
    return states


async def run_forever() -> None:
    """Reconcile on an interval until cancelled. Started from the app lifespan."""
    interval = get_settings().trading_reconcile_interval
    logger.info("reconciler: started, every %ss", interval)
    while True:
        started = asyncio.get_running_loop().time()
        try:
            await reconcile_once()
            elapsed = asyncio.get_running_loop().time() - started
            await asyncio.sleep(max(1.0, interval - elapsed))
        except asyncio.CancelledError:
            logger.info("reconciler: stopped")
            raise
        except Exception:
            # Never let one bad pass kill the loop — it is the safety net itself.
            logger.exception("reconciler: pass failed")
            await asyncio.sleep(interval)
