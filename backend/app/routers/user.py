"""User-facing endpoints: a guarded reverse proxy to the caller's own bot.

Every route resolves ``CurrentUser`` to that user's single :class:`BotInstance`, so a
user can never address another user's instance. Only an allowlisted subset of the
Freqtrade REST API is forwarded.
"""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.models.bot_instance import BotInstance
from app.schemas.bots import BotInstanceOut
from app.security.deps import CurrentUser, DbSession
from app.services import proxy
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
