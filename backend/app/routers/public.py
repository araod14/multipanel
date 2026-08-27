"""Unauthenticated, read-only results page.

This is the one router with no ``CurrentUser``/``CurrentAdmin`` dependency: the results
page is deliberately public. Three things keep that safe, and all three must stay:

* the response is shaped by :mod:`app.schemas.public`, an explicit field allowlist that
  never carries an email, a container name, an internal hostname or anything encrypted;
* the upstream calls are a fixed list inside :mod:`app.services.public_stats` — no path,
  parameter or bot id is taken from the caller, so nothing here widens the guarded proxy;
* the collection is cached and per-IP rate limited, so an anonymous caller cannot use
  this endpoint to amplify traffic into every bot.

``CP_PUBLIC_RESULTS_ENABLED=false`` takes the page down without a code change.
"""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, status

from app.config import get_settings
from app.schemas.public import PublicResultsOut
from app.security.deps import DbSession
from app.services import public_stats

router = APIRouter(prefix="/public", tags=["public"])

_RATE_WINDOW_SECONDS = 60.0

# client ip -> timestamps of its requests inside the current window.
_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    """Best-effort caller identity for rate limiting.

    Production terminates TLS in the host nginx, so the socket peer is always the
    loopback proxy; the first ``X-Forwarded-For`` hop is the real client.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request, budget: int) -> None:
    """Allow ``budget`` requests per minute per IP, else raise 429."""
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW_SECONDS

    # Prune every idle bucket while we are here, so the dict cannot grow unbounded
    # across the many one-shot IPs a public page attracts.
    for ip in [ip for ip, hits in _hits.items() if not hits or hits[-1] < cutoff]:
        del _hits[ip]

    hits = _hits[_client_ip(request)]
    while hits and hits[0] < cutoff:
        hits.popleft()
    if len(hits) >= budget:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded, try again shortly",
        )
    hits.append(now)


@router.get("/results", response_model=PublicResultsOut)
async def public_results(request: Request, db: DbSession) -> dict:
    """Return every account's trading results, configuration and amounts."""
    settings = get_settings()
    if not settings.public_results_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    _rate_limit(request, settings.public_results_rate_limit)
    return await public_stats.collect(db)
