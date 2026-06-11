"""User-editable bot settings: a safe whitelist of Freqtrade parameters.

The user edits only these fields; everything else (api_server, exchange wiring,
secrets) is controlled by the control plane. Values are validated here, stored as a
JSON blob on the BotInstance, and applied by ``config_builder`` + ``provisioning``.
"""

from typing import Any

from app.services import strategy_assets

ALLOWED_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

DEFAULTS: dict[str, Any] = {
    "strategy": strategy_assets.DEFAULT_STRATEGY_KEY,
    "pairs": ["BTC/USDT", "ETH/USDT"],
    "stake_currency": "USDT",
    "stake_amount": "unlimited",
    "max_open_trades": 3,
    "stoploss": -0.10,
    "roi": 0.10,
    "timeframe": "5m",
}


class ConfigValidationError(ValueError):
    """Raised when a user-supplied setting is invalid."""


def effective(instance_config: dict | None) -> dict[str, Any]:
    """Return DEFAULTS merged with a stored per-user config blob."""
    merged = dict(DEFAULTS)
    if instance_config:
        merged.update({k: v for k, v in instance_config.items() if k in DEFAULTS})
    return merged


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise a user-supplied settings dict.

    :raises ConfigValidationError: on any invalid field.
    """
    cfg = effective(None)
    cfg.update({k: v for k, v in payload.items() if k in DEFAULTS})

    if cfg["strategy"] not in strategy_assets.STRATEGIES:
        raise ConfigValidationError(f"unknown strategy '{cfg['strategy']}'")

    pairs = cfg["pairs"]
    if not isinstance(pairs, list) or not pairs or not all(_is_pair(p) for p in pairs):
        raise ConfigValidationError("pairs must be a non-empty list of 'BASE/QUOTE' strings")

    sc = str(cfg["stake_currency"]).upper()
    if not (2 <= len(sc) <= 10 and sc.isalnum()):
        raise ConfigValidationError("invalid stake_currency")
    cfg["stake_currency"] = sc

    sa = cfg["stake_amount"]
    if sa != "unlimited":
        if not _is_positive_number(sa):
            raise ConfigValidationError("stake_amount must be 'unlimited' or a positive number")
        cfg["stake_amount"] = float(sa)

    if not (isinstance(cfg["max_open_trades"], int) and 1 <= cfg["max_open_trades"] <= 50):
        raise ConfigValidationError("max_open_trades must be an int in 1..50")

    if not (isinstance(cfg["stoploss"], (int, float)) and -0.99 < float(cfg["stoploss"]) < 0):
        raise ConfigValidationError("stoploss must be a negative fraction (e.g. -0.10)")
    cfg["stoploss"] = float(cfg["stoploss"])

    if not (isinstance(cfg["roi"], (int, float)) and 0 < float(cfg["roi"]) <= 5):
        raise ConfigValidationError("roi must be a positive fraction (e.g. 0.10)")
    cfg["roi"] = float(cfg["roi"])

    if cfg["timeframe"] not in ALLOWED_TIMEFRAMES:
        raise ConfigValidationError(f"timeframe must be one of {ALLOWED_TIMEFRAMES}")

    return cfg


def _is_pair(p: Any) -> bool:
    return isinstance(p, str) and "/" in p and all(part.isalnum() for part in p.split("/", 1))


def _is_positive_number(v: Any) -> bool:
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False
