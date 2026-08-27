"""Keeps each bot's actual trading state matching the state its owner asked for.

Freqtrade containers are launched with ``initial_state: stopped`` (see
``config_builder``), and a container has no memory of having been started: after a host
reboot, a docker daemon restart or a re-provision, every bot comes back with its trading
loop idle and *nothing says so*. That is how three production bots sat stopped for two
days while their containers reported perfectly healthy.

``BotInstance.trading_enabled`` records the intent — set when a user presses Start or
Stop, which ``routers/user.py`` intercepts. This loop periodically compares that intent
against what each bot actually reports and starts the ones that drifted.

Deliberately one-directional: it only ever **starts** a bot that should be trading. It
never stops one, because the flag defaults to false for pre-existing rows and a
stop-enforcing loop would silently shut those down on first run. It also only acts on a
bot reporting ``stopped`` — a bot the user explicitly *paused* is left alone — and it
never touches container lifecycle, which stays the admin's call.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import SessionLocal
from app.models.bot_instance import BotInstance
from app.services.proxy import ProxyError, forward
from app.services.runtime import BotRuntime

logger = logging.getLogger("control_plane.reconciler")

# Freqtrade's own words for a bot whose trading loop is idle. Anything else — running,
# paused, reload_config — is left untouched.
_RESUMABLE_STATES = {"stopped"}


async def reconcile_once() -> dict[str, int]:
    """Run one reconciliation pass. Returns a small tally for logging/tests."""
    tally = {"checked": 0, "resumed": 0, "failed": 0}

    with SessionLocal() as db:
        instances = list(
            db.scalars(
                select(BotInstance)
                .options(selectinload(BotInstance.user))
                .where(BotInstance.trading_enabled.is_(True))
            ).all()
        )
        if not instances:
            return tally

        states = await asyncio.to_thread(
            _container_states, [i.container_name for i in instances]
        )
        for instance in instances:
            # A container that is not up is not this loop's business; an admin stopped
            # it, or provisioning is mid-flight.
            if states.get(instance.container_name) != "running":
                continue
            tally["checked"] += 1
            try:
                if await _resume_if_idle(instance):
                    tally["resumed"] += 1
            except ProxyError as exc:
                # A bot still loading markets is unreachable but perfectly healthy;
                # the next pass will pick it up.
                logger.info("reconciler: %s unreachable: %s", instance.container_name, exc)
            except Exception:
                tally["failed"] += 1
                logger.exception("reconciler: %s failed", instance.container_name)

    if tally["resumed"]:
        logger.warning("reconciler: resumed trading on %d bot(s)", tally["resumed"])
    return tally


async def _resume_if_idle(instance: BotInstance) -> bool:
    """Start the trading loop if the bot reports itself stopped. True if it was."""
    resp = await forward(instance, "GET", "show_config")
    if resp.status_code != 200:
        return False
    state = resp.json().get("state")
    if not isinstance(state, str) or state.lower() not in _RESUMABLE_STATES:
        return False

    started = await forward(instance, "POST", "start")
    if started.status_code != 200:
        logger.warning(
            "reconciler: %s start -> HTTP %s %s",
            instance.container_name,
            started.status_code,
            started.text[:200],
        )
        return False
    logger.warning(
        "reconciler: %s was stopped but should be trading — resumed", instance.container_name
    )
    return True


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
        try:
            await asyncio.sleep(interval)
            await reconcile_once()
        except asyncio.CancelledError:
            logger.info("reconciler: stopped")
            raise
        except Exception:
            # Never let one bad pass kill the loop — it is the safety net itself.
            logger.exception("reconciler: pass failed")
