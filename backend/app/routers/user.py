"""User-facing endpoints: a guarded reverse proxy to the caller's own bot.

Every route resolves ``CurrentUser`` to that user's single :class:`BotInstance`, so a
user can never address another user's instance. Only an allowlisted subset of the
Freqtrade REST API is forwarded.
"""

import asyncio
from contextlib import nullcontext

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.config import get_settings
from app.models.bot_instance import BotInstance
from app.schemas.bot_config import BotConfigIn, BotConfigOut, StrategyOption
from app.schemas.bots import BotInstanceOut
from app.security.deps import CurrentUser, DbSession
from app.services import (
    audit,
    bot_config,
    provisioning,
    proxy,
    public_stats,
    strategy_assets,
    trading_guard,
)
from app.services.bot_config import ConfigValidationError
from app.services.proxy import ProxyError

router = APIRouter(prefix="/me", tags=["user"])

# Exact (METHOD, path) pairs that may be forwarded to a bot's /api/v1/.
_ALLOWED_EXACT: set[tuple[str, str]] = {
    ("GET", "status"),
    ("GET", "count"),
    ("GET", "profit"),
    ("GET", "balance"),
    ("GET", "daily"),
    ("GET", "weekly"),
    ("GET", "monthly"),
    ("GET", "performance"),
    ("GET", "stats"),
    ("GET", "trades"),
    ("GET", "whitelist"),
    ("GET", "blacklist"),
    ("GET", "locks"),
    ("GET", "show_config"),
    ("GET", "logs"),
    ("GET", "health"),
    ("GET", "ping"),
    ("GET", "plot_config"),
    ("GET", "pair_candles"),
    ("POST", "start"),
    ("POST", "stop"),
    ("POST", "pause"),
    ("POST", "reload_config"),
    ("POST", "forceenter"),
    ("POST", "forceexit"),
}

# (METHOD, prefix) pairs allowing a trailing id segment, e.g. trades/{id}.
_ALLOWED_PREFIX: set[tuple[str, str]] = {
    ("GET", "trade/"),
    ("DELETE", "trades/"),
    ("POST", "trades/"),
}


# Record manual intent only when the bot accepts the command.
_TRADING_INTENT: dict[tuple[str, str], bool] = {
    ("POST", "start"): True,
    ("POST", "stop"): False,
    ("POST", "pause"): True,
}


def _is_allowed(method: str, ft_path: str) -> bool:
    if (method, ft_path) in _ALLOWED_EXACT:
        return True
    return any(method == m and ft_path.startswith(p) for m, p in _ALLOWED_PREFIX)


def _bot_or_404(user) -> BotInstance:
    if user.bot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no bot provisioned")
    return user.bot


@router.get("/bot", response_model=BotInstanceOut)
def my_bot(user: CurrentUser) -> BotInstance:
    """Return the caller's bot bookkeeping (status, dry_run, etc.)."""
    return _bot_or_404(user)


def _config_out(instance: BotInstance) -> BotConfigOut:
    settings = get_settings()
    cfg = bot_config.effective(instance.user_config_json)
    return BotConfigOut(
        **cfg,
        stake_currency=bot_config.STAKE_CURRENCY,
        dry_run=instance.dry_run,
        live_max_capital=settings.live_max_capital,
        live_min_stake=settings.live_min_stake,
        available_strategies=[
            StrategyOption(key=s.key, label=s.label, description=s.description)
            for s in strategy_assets.STRATEGIES.values()
        ],
        available_timeframes=bot_config.ALLOWED_TIMEFRAMES,
        available_pairlist_modes=bot_config.PAIRLIST_MODES,
        available_base_coins=bot_config.COMMON_BASE_COINS,
    )


@router.get("/bot/config", response_model=BotConfigOut)
def get_config(user: CurrentUser) -> BotConfigOut:
    """Return the caller's editable bot settings and the available choices."""
    return _config_out(_bot_or_404(user))


@router.put("/bot/config", response_model=BotConfigOut)
async def update_config(body: BotConfigIn, user: CurrentUser, db: DbSession) -> BotConfigOut:
    """Update settings; recreate the container only for changed trading parameters.

    Settings are merged over the current ones, validated, persisted, and the bot
    container is recreated so new trading parameters take effect. Guard-only
    changes are applied without recreating the container.
    """
    instance = _bot_or_404(user)
    async with trading_guard.bot_lock(instance.id):
        db.refresh(instance)
        current = bot_config.effective(instance.user_config_json)
        merged = {**current, **body.to_payload()}
        try:
            validated = bot_config.validate(merged, dry_run=instance.dry_run)
        except ConfigValidationError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        runtime_changed = any(
            current[k] != validated[k] for k in validated if k != "tradingview_guard_enabled"
        )
        instance.user_config_json = validated
        if current["tradingview_guard_enabled"] != validated["tradingview_guard_enabled"]:
            audit.record(db, actor=f"user:{user.id}", action="tradingview.configure",
                         target_user_id=user.id, detail=f"enabled={validated['tradingview_guard_enabled']}")
        if not validated["tradingview_guard_enabled"]:
            instance.tradingview_paused = False
        if runtime_changed:
            await asyncio.to_thread(provisioning.provision_bot, db, user)
        db.commit()
        if not runtime_changed:
            try:
                await trading_guard.sync_state(db, instance)
            except ProxyError:
                pass  # persisted intent is retried by the reconciler
        public_stats.invalidate()
        db.refresh(instance)
        return _config_out(instance)


@router.api_route("/bot/ft/{ft_path:path}", methods=["GET", "POST", "DELETE"])
async def proxy_to_bot(ft_path: str, request: Request, user: CurrentUser, db: DbSession) -> Response:
    """Forward an allowlisted call to the caller's own Freqtrade instance."""
    method = request.method
    if not _is_allowed(method, ft_path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"{method} {ft_path} not permitted"
        )

    instance = _bot_or_404(user)
    params = dict(request.query_params)
    body = None
    if method in ("POST", "DELETE"):
        raw = await request.body()
        if raw:
            body = await request.json()

    lock = trading_guard.bot_lock(instance.id) if method != "GET" else nullcontext()
    async with lock:
        if method != "GET":
            db.refresh(instance)
        target = ft_path
        if method == "POST" and ft_path == "start" and (
            instance.tradingview_guard_enabled and instance.tradingview_paused
        ):
            target = "pause"
        if method == "POST" and ft_path == "forceenter" and (
            instance.manual_paused or (instance.tradingview_guard_enabled and instance.tradingview_paused)
        ):
            raise HTTPException(status_code=409, detail="new entries are paused")
        try:
            upstream = await proxy.forward(instance, method, target, params=params, json=body)
        except ProxyError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=f"bot unreachable: {exc}"
            ) from exc
        intent = _TRADING_INTENT.get((method, ft_path))
        if intent is not None and upstream.status_code == 200:
            instance.trading_enabled = intent
            instance.manual_paused = ft_path == "pause"
            instance.entry_pause_managed = target == "pause"
            instance.entry_pause_pending = False
            db.commit()
            public_stats.invalidate()

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
