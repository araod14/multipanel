"""User-facing endpoints: a guarded reverse proxy to the caller's own bot.

Every route resolves ``CurrentUser`` to that user's single :class:`BotInstance`, so a
user can never address another user's instance. Only an allowlisted subset of the
Freqtrade REST API is forwarded.
"""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.models.bot_instance import BotInstance
from app.schemas.bot_config import BotConfigIn, BotConfigOut, StrategyOption
from app.schemas.bots import BotInstanceOut
from app.security.deps import CurrentUser, DbSession
from app.services import bot_config, provisioning, proxy, strategy_assets
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
    cfg = bot_config.effective(instance.user_config_json)
    return BotConfigOut(
        **cfg,
        stake_currency=bot_config.STAKE_CURRENCY,
        available_strategies=[
            StrategyOption(key=s.key, label=s.label, description=s.description)
            for s in strategy_assets.STRATEGIES.values()
        ],
        available_timeframes=bot_config.ALLOWED_TIMEFRAMES,
        available_pairlist_modes=bot_config.PAIRLIST_MODES,
    )


@router.get("/bot/config", response_model=BotConfigOut)
def get_config(user: CurrentUser) -> BotConfigOut:
    """Return the caller's editable bot settings and the available choices."""
    return _config_out(_bot_or_404(user))


@router.put("/bot/config", response_model=BotConfigOut)
def update_config(body: BotConfigIn, user: CurrentUser, db: DbSession) -> BotConfigOut:
    """Update the caller's editable settings and re-provision their bot.

    Settings are merged over the current ones, validated, persisted, and the bot
    container is recreated so the new config and strategy take effect.
    """
    instance = _bot_or_404(user)
    current = bot_config.effective(instance.user_config_json)
    merged = {**current, **body.to_payload()}
    try:
        validated = bot_config.validate(merged)
    except ConfigValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    instance.user_config_json = validated  # reassign so SQLAlchemy tracks the change
    provisioning.provision_bot(db, user)
    db.commit()
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

    try:
        upstream = await proxy.forward(instance, method, ft_path, params=params, json=body)
    except ProxyError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"bot unreachable: {exc}"
        ) from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
