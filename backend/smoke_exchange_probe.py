"""Offline checks for the real-money guard rails. No server, no Docker, no network.

This is where the money-critical logic is pinned down:
  * the Binance request signature,
  * the live stake/exposure rules,
  * the exchange allowlist,
  * the ``available_capital`` ceiling handed to Freqtrade.

Run from backend/:

    .venv/bin/python smoke_exchange_probe.py
"""

import os
import sys

# Settings are read at import time and cached; pin the limits this script asserts on so a
# developer's .env cannot make the expected values drift.
os.environ["CP_LIVE_MAX_CAPITAL"] = "25.0"
os.environ["CP_LIVE_MIN_STAKE"] = "10.0"

from pydantic import ValidationError  # noqa: E402

from app.schemas.exchange import ExchangeCredentialIn  # noqa: E402
from app.services import bot_config, config_builder, exchange_probe  # noqa: E402

_failures: list[str] = []


def check(label: str, condition: bool) -> None:
    """Record a single assertion."""
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        _failures.append(label)


def rejects(label: str, payload: dict, *, dry_run: bool) -> None:
    """Assert ``validate`` refuses ``payload``."""
    try:
        bot_config.validate({**bot_config.effective(None), **payload}, dry_run=dry_run)
    except bot_config.ConfigValidationError as exc:
        print(f"  PASS  {label}\n          -> {exc}")
        return
    print(f"  FAIL  {label} (was accepted)")
    _failures.append(label)


def accepts(label: str, payload: dict, *, dry_run: bool) -> None:
    """Assert ``validate`` accepts ``payload``."""
    try:
        bot_config.validate({**bot_config.effective(None), **payload}, dry_run=dry_run)
    except bot_config.ConfigValidationError as exc:
        print(f"  FAIL  {label} -> {exc}")
        _failures.append(label)
        return
    print(f"  PASS  {label}")


print("\n[1/4] Binance signature (vector published in Binance's SIGNED endpoint examples)")
# Cross-checked against ccxt's independent implementation, which is what Freqtrade itself
# uses to sign live orders. If this fails, every probe would wrongly report a bad key.
VECTOR_SECRET = "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j"
VECTOR_QS = (
    "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1&price=0.1"
    "&recvWindow=5000&timestamp=1499827319559"
)
VECTOR_SIG = "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71"
check("signature matches Binance's published vector", exchange_probe.sign(VECTOR_SECRET, VECTOR_QS) == VECTOR_SIG)
check("RSA/Ed25519 secret is detected, not signed", exchange_probe.looks_like_pem("-----BEGIN PRIVATE KEY-----\nabc"))
check("HMAC secret is not mistaken for PEM", not exchange_probe.looks_like_pem(VECTOR_SECRET))

print("\n[2/4] Live stake / exposure rules (max capital 25, min stake 10)")
rejects("live rejects 'unlimited' stake", {"stake_amount": "unlimited"}, dry_run=False)
accepts("dry-run still allows 'unlimited' stake", {"stake_amount": "unlimited"}, dry_run=True)
rejects("live rejects stake below the minimum", {"stake_amount": 5, "max_open_trades": 1}, dry_run=False)
rejects(
    "live rejects exposure over the cap (10 x 3 = 30)",
    {"stake_amount": 10, "max_open_trades": 3},
    dry_run=False,
)
accepts("live allows exposure at the cap (10 x 2 = 20)", {"stake_amount": 10, "max_open_trades": 2}, dry_run=False)
accepts("live allows the documented first run (15 x 1)", {"stake_amount": 15, "max_open_trades": 1}, dry_run=False)
accepts("dry-run ignores the live caps entirely", {"stake_amount": 10, "max_open_trades": 50}, dry_run=True)

print("\n[3/4] Exchange allowlist")
try:
    ExchangeCredentialIn(exchange_name="kraken", key="k", secret="s")
    check("credentials for a non-allowlisted exchange are refused", False)
except ValidationError:
    check("credentials for a non-allowlisted exchange are refused", True)
check(
    "binance credentials are accepted",
    ExchangeCredentialIn(exchange_name="binance", key="k", secret="s").exchange_name.value == "binance",
)

print("\n[4/4] available_capital ceiling handed to Freqtrade")
_cfg = bot_config.effective(None)
_live = config_builder.build_bot_config(
    username="u", exchange_name="binance", dry_run=False, user_config={**_cfg, "stake_amount": 15.0}
)
_dry = config_builder.build_bot_config(
    username="u", exchange_name="binance", dry_run=True, user_config=_cfg
)
check("live config caps available_capital at 25.0", _live.get("available_capital") == 25.0)
check("live config really is live", _live["dry_run"] is False)
check("dry-run config omits available_capital", "available_capital" not in _dry)
check("BNB stays blacklisted (Freqtrade's Binance recommendation)", "BNB/.*" in _live["exchange"]["pair_blacklist"])

print()
if _failures:
    print(f"FAILED ({len(_failures)}): " + "; ".join(_failures))
    sys.exit(1)
print("All offline guard-rail checks passed.")
