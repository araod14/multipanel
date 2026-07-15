"""Verify exchange API credentials against the exchange before storing them.

Without this, a wrong, revoked or permission-less key is only discovered when the bot
container fails to boot, which surfaces as an opaque ``BotStatus.error``.

Deliberately hand-rolled over the ``httpx`` we already depend on rather than pulling in
ccxt (~60 MB of exchange modules) purely to call one endpoint from the internet-facing
process. Binance's scheme is plain ``HMAC-SHA256(secret, query_string)`` in hex; the
signature is cross-checked against ccxt's implementation in ``smoke_exchange_probe.py``
using Binance's own published example vector.

Only HMAC keys can be probed. Freqtrade also accepts Binance RSA keys (see freqtrade
docs/exchanges.md "Binance RSA keys"), which this cannot verify — those are reported as
such rather than as a bad key.
"""

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger("control_plane.exchange_probe")

_BINANCE_API = "https://api.binance.com"
_ACCOUNT_PATH = "/api/v3/account"
_RECV_WINDOW_MS = 5000
_TIMEOUT_S = 15.0

# Binance error codes we must tell apart. A rejection is final; anything else is a
# transient/environmental failure that must not be reported as "your key is bad".
_INVALID_KEY_CODES = {
    -2015,  # Invalid API-key, IP, or permissions for action
    -2014,  # API-key format invalid
    -1022,  # Signature for this request is not valid
    -2008,  # Invalid Api-Key ID
}
_CLOCK_SKEW_CODES = {
    -1021,  # Timestamp for this request is outside of the recvWindow
}


class ExchangeProbeError(RuntimeError):
    """Base class for a failed credential probe."""


class InvalidExchangeCredentials(ExchangeProbeError):
    """The exchange authoritatively rejected the credentials. Never skippable."""


class ExchangeProbeUnavailable(ExchangeProbeError):
    """The probe could not reach a verdict (network, geo block, clock skew).

    Skippable by an explicit admin override: refusing to store a key because *we* could
    not reach the exchange would be wrong.
    """


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of a successful credential probe."""

    can_trade: bool
    can_withdraw: bool
    balance: float
    stake_currency: str


def sign(secret: str, query_string: str) -> str:
    """Return Binance's ``signature`` for a query string.

    Split out so the offline smoke test can pin it against Binance's published vector.
    """
    return hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()


def looks_like_pem(secret: str) -> bool:
    """Whether ``secret`` is an RSA/Ed25519 private key rather than an HMAC secret."""
    return secret.lstrip().startswith("-----BEGIN")


def probe(exchange_name: str, key: str, secret: str, *, stake_currency: str = "USDT") -> ProbeResult:
    """Verify ``key``/``secret`` against the exchange and report what they can do.

    One signed call to Binance's ``/api/v3/account`` proves the key, the secret and the
    signature, reports whether the key may trade, and returns the free balance — so an
    admin can confirm the deposit landed before enabling live trading.

    :raises InvalidExchangeCredentials: the exchange rejected the credentials (422-worthy).
    :raises ExchangeProbeUnavailable: no verdict reachable (503-worthy, overridable).
    """
    if exchange_name != "binance":
        raise ExchangeProbeUnavailable(f"no credential probe implemented for '{exchange_name}'")

    if looks_like_pem(secret):
        raise ExchangeProbeUnavailable(
            "this looks like an RSA/Ed25519 private key, which cannot be verified "
            "automatically. Use an HMAC-SHA256 API key, or store it without verification."
        )

    query = f"timestamp={int(time.time() * 1000)}&recvWindow={_RECV_WINDOW_MS}"
    url = f"{_BINANCE_API}{_ACCOUNT_PATH}?{query}&signature={sign(secret, query)}"

    try:
        resp = httpx.get(url, headers={"X-MBX-APIKEY": key}, timeout=_TIMEOUT_S)
    except httpx.HTTPError as exc:
        raise ExchangeProbeUnavailable(f"could not reach {exchange_name}: {exc}") from exc

    if resp.status_code == 451:
        raise ExchangeProbeUnavailable(
            "Binance refused this server's location (HTTP 451). It restricts API access by "
            "server country; the host running the control plane must be in an eligible one."
        )

    if resp.status_code != 200:
        _raise_for_error_body(resp)

    return _parse_account(resp.json(), stake_currency)


def _raise_for_error_body(resp: httpx.Response) -> None:
    """Translate a non-200 Binance response into the right exception. Always raises."""
    try:
        body = resp.json()
        code, msg = body.get("code"), body.get("msg", "")
    except ValueError:
        raise ExchangeProbeUnavailable(
            f"unexpected response from Binance (HTTP {resp.status_code})"
        ) from None

    if code in _INVALID_KEY_CODES:
        raise InvalidExchangeCredentials(f"Binance rejected these credentials: {msg}")
    if code in _CLOCK_SKEW_CODES:
        raise ExchangeProbeUnavailable(
            f"Binance rejected the request timestamp ({msg}). This is a server clock skew, "
            "not a bad key — check the host's NTP sync and retry."
        )
    raise ExchangeProbeUnavailable(f"Binance error {code}: {msg}")


def _parse_account(body: dict, stake_currency: str) -> ProbeResult:
    """Build a :class:`ProbeResult` from Binance's ``/api/v3/account`` payload."""
    balance = 0.0
    for entry in body.get("balances", []):
        if entry.get("asset") == stake_currency:
            balance = float(entry.get("free", 0) or 0)
            break

    result = ProbeResult(
        can_trade=bool(body.get("canTrade", False)),
        can_withdraw=bool(body.get("canWithdraw", False)),
        balance=balance,
        stake_currency=stake_currency,
    )

    if not result.can_trade:
        raise InvalidExchangeCredentials(
            "this API key is valid but cannot trade. Enable 'Spot & Margin Trading' on the "
            "key in Binance, then save it again."
        )
    return result
