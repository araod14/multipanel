"""Authenticated reverse proxy to per-user Freqtrade REST APIs.

For each :class:`BotInstance` the control plane logs in with that instance's stored
(decrypted) ``api_server`` credentials, caches the resulting JWT, and forwards
whitelisted ``/api/v1/*`` calls with a Bearer header. On a 401 the token is
refreshed once and the call retried. Users never see the bot's credentials.
"""

import logging

import httpx

from app.config import get_settings
from app.models.bot_instance import BotInstance
from app.security.vault import decrypt
from app.services.runtime import BotRuntime

logger = logging.getLogger("control_plane.proxy")

# JWT access token cache, keyed by BotInstance.id.
_token_cache: dict[int, str] = {}

# Shared async client (connection pooling).
_client = httpx.AsyncClient(timeout=15.0)


class ProxyError(RuntimeError):
    """Raised when a bot instance cannot be reached or authenticated."""


def _base_url(instance: BotInstance) -> str:
    """Resolve the base URL of a bot's REST API.

    Production uses docker DNS (container name); host-side dev resolves the
    container IP via the Docker SDK.
    """
    settings = get_settings()
    if settings.bot_address_mode == "docker_ip":
        ip = BotRuntime().ip_address(instance.container_name, settings.bot_network)
        if not ip:
            raise ProxyError(f"container {instance.container_name} has no IP / not running")
        return f"http://{ip}:8080"
    return f"http://{instance.internal_hostname}:8080"


async def _login(instance: BotInstance) -> str:
    """Authenticate to the instance and cache a fresh access token."""
    base = _base_url(instance)
    password = decrypt(instance.api_password_enc)
    try:
        resp = await _client.post(
            f"{base}/api/v1/token/login", auth=(instance.api_username, password)
        )
    except httpx.HTTPError as exc:
        raise ProxyError(f"login transport error: {exc}") from exc
    if resp.status_code != 200:
        raise ProxyError(f"login failed: {resp.status_code} {resp.text[:200]}")
    token = resp.json()["access_token"]
    _token_cache[instance.id] = token
    return token


async def _token(instance: BotInstance) -> str:
    """Return a cached token, logging in if none is cached."""
    cached = _token_cache.get(instance.id)
    return cached if cached else await _login(instance)


async def forward(
    instance: BotInstance,
    method: str,
    ft_path: str,
    *,
    params: dict | None = None,
    json: dict | None = None,
) -> httpx.Response:
    """Forward a request to ``/api/v1/<ft_path>`` on the instance.

    Refreshes the JWT once on a 401 and retries.

    :param ft_path: path under ``/api/v1/`` (no leading slash), e.g. ``"status"``.
    :raises ProxyError: on transport failure or unauthenticated state.
    """
    base = _base_url(instance)
    url = f"{base}/api/v1/{ft_path}"

    token = await _token(instance)
    resp = await _do(method, url, token, params, json)
    if resp.status_code == 401:
        _token_cache.pop(instance.id, None)
        token = await _login(instance)
        resp = await _do(method, url, token, params, json)
    return resp


async def _do(
    method: str, url: str, token: str, params: dict | None, json: dict | None
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"}
    try:
        return await _client.request(method, url, headers=headers, params=params, json=json)
    except httpx.HTTPError as exc:
        raise ProxyError(f"transport error talking to bot: {exc}") from exc


def invalidate(instance_id: int) -> None:
    """Drop any cached token for an instance (e.g. after re-provisioning)."""
    _token_cache.pop(instance_id, None)
