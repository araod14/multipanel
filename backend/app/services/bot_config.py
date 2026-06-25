"""User-editable bot settings: a safe whitelist of Freqtrade parameters.

The user edits only these fields; everything else (api_server, exchange wiring,
secrets) is controlled by the control plane. Values are validated here, stored as a
JSON blob on the BotInstance, and applied by ``config_builder`` + ``provisioning``.
"""

from typing import Any

from app.services import strategy_assets

ALLOWED_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
PAIRLIST_MODES = ["static", "volume"]

# Curated base coins offered in the manual pair picker (each becomes BASE/USDT).
# BNB is intentionally absent: BNB/.* is in the config pair_blacklist, so it would
# never trade. Extend this list to offer more coins.
COMMON_BASE_COINS = sorted(
    [
        "BTC", "ETH", "SOL", "XRP", "ADA", "AVAX", "DOGE", "DOT", "TRX", "LINK",
        "MATIC", "POL", "LTC", "BCH", "UNI", "ATOM", "XLM", "ETC", "FIL", "APT",
        "ARB", "OP", "NEAR", "INJ", "SUI", "SEI", "TIA", "RNDR", "IMX", "AAVE",
        "MKR", "GRT", "SAND", "MANA", "AXS", "FTM", "ALGO", "EGLD", "FLOW", "CHZ",
        "CRV", "COMP", "SNX", "DYDX", "LDO", "PEPE", "SHIB", "WIF", "BONK", "USDC",
    ]
)

# The quote currency is fixed: every pair is BASE/USDT and stakes are in USDT.
STAKE_CURRENCY = "USDT"

DEFAULTS: dict[str, Any] = {
    "strategy": strategy_assets.DEFAULT_STRATEGY_KEY,
    "pairlist_mode": "static",
    "pairs": ["BTC/USDT", "ETH/USDT"],
    "volume_number_assets": 20,
    "stake_amount": "unlimited",
    "max_open_trades": 3,
    "stoploss": -0.10,
    "roi_table": [{"minutes": 0, "roi": 0.10}],
    "timeframe": "5m",
    "trailing_stop": False,
    "trailing_stop_positive": None,
    "trailing_stop_positive_offset": 0.0,
    "dry_run_wallet": 1000.0,
}


class ConfigValidationError(ValueError):
    """Raised when a user-supplied setting is invalid."""


def effective(instance_config: dict | None) -> dict[str, Any]:
    """Return DEFAULTS merged with a stored per-user config blob.

    Legacy bots stored a single ``roi`` float; transparently upgrade it to a
    one-step ``roi_table`` so old instances keep working without a migration.
    """
    merged = dict(DEFAULTS)
    if instance_config:
        if "roi_table" not in instance_config and "roi" in instance_config:
            merged["roi_table"] = [{"minutes": 0, "roi": instance_config["roi"]}]
        merged.update({k: v for k, v in instance_config.items() if k in DEFAULTS})
    return merged


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise a user-supplied settings dict.

    :raises ConfigValidationError: on any invalid field.
    """
    cfg = effective(None)
    if "roi_table" not in payload and "roi" in payload:  # accept the legacy single value
        cfg["roi_table"] = [{"minutes": 0, "roi": payload["roi"]}]
    cfg.update({k: v for k, v in payload.items() if k in DEFAULTS})

    if cfg["strategy"] not in strategy_assets.STRATEGIES:
        raise ConfigValidationError(f"unknown strategy '{cfg['strategy']}'")

    if cfg["pairlist_mode"] not in PAIRLIST_MODES:
        raise ConfigValidationError(f"pairlist_mode must be one of {PAIRLIST_MODES}")

    if cfg["pairlist_mode"] == "static":
        pairs = cfg["pairs"]
        if not isinstance(pairs, list) or not pairs or not all(_is_pair(p) for p in pairs):
            raise ConfigValidationError("pairs must be a non-empty list of 'BASE/QUOTE' strings")
        cfg["pairs"] = [str(p).upper() for p in pairs]
    else:  # volume
        n = cfg["volume_number_assets"]
        if not (isinstance(n, int) and 1 <= n <= 100):
            raise ConfigValidationError("volume_number_assets must be an int in 1..100")

    cfg["roi_table"] = _validate_roi_table(cfg["roi_table"])

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

    if cfg["timeframe"] not in ALLOWED_TIMEFRAMES:
        raise ConfigValidationError(f"timeframe must be one of {ALLOWED_TIMEFRAMES}")

    _validate_trailing(cfg)

    if not _is_positive_number(cfg["dry_run_wallet"]):
        raise ConfigValidationError("dry_run_wallet must be a positive number")
    cfg["dry_run_wallet"] = float(cfg["dry_run_wallet"])

    return cfg


def _validate_roi_table(table: Any) -> list[dict[str, Any]]:
    """Normalise and validate a multi-step ROI table.

    Each step is ``{"minutes": int >= 0, "roi": float in (0, 5]}``; minutes must be
    unique and include a ``0`` step (the initial take-profit). Returns the table
    sorted ascending by minutes.
    """
    if not isinstance(table, list) or not table:
        raise ConfigValidationError("roi_table must be a non-empty list of steps")
    cleaned: list[dict[str, Any]] = []
    seen: set[int] = set()
    for step in table:
        if not isinstance(step, dict) or "minutes" not in step or "roi" not in step:
            raise ConfigValidationError("each ROI step needs 'minutes' and 'roi'")
        minutes, roi = step["minutes"], step["roi"]
        if not (isinstance(minutes, int) and minutes >= 0):
            raise ConfigValidationError("ROI step 'minutes' must be an int >= 0")
        if minutes in seen:
            raise ConfigValidationError(f"duplicate ROI step at {minutes} minutes")
        if not (isinstance(roi, (int, float)) and 0 < float(roi) <= 5):
            raise ConfigValidationError("ROI step 'roi' must be a positive fraction (e.g. 0.10)")
        seen.add(minutes)
        cleaned.append({"minutes": minutes, "roi": float(roi)})
    if 0 not in seen:
        raise ConfigValidationError("roi_table must include a step at 0 minutes")
    cleaned.sort(key=lambda s: s["minutes"])
    return cleaned


def _validate_trailing(cfg: dict[str, Any]) -> None:
    """Validate the trailing-stop fields in place (Freqtrade semantics)."""
    if not isinstance(cfg["trailing_stop"], bool):
        raise ConfigValidationError("trailing_stop must be true or false")

    pos = cfg["trailing_stop_positive"]
    if pos is not None:
        if not (isinstance(pos, (int, float)) and 0 < float(pos) < 1):
            raise ConfigValidationError(
                "trailing_stop_positive must be a fraction in (0, 1), e.g. 0.01"
            )
        cfg["trailing_stop_positive"] = float(pos)

    offset = cfg["trailing_stop_positive_offset"]
    if not (isinstance(offset, (int, float)) and float(offset) >= 0):
        raise ConfigValidationError("trailing_stop_positive_offset must be a fraction >= 0")
    cfg["trailing_stop_positive_offset"] = float(offset)

    # Freqtrade requires the offset to sit above the trailing positive when both are set.
    if pos is not None and cfg["trailing_stop_positive_offset"] > 0:
        if cfg["trailing_stop_positive_offset"] <= cfg["trailing_stop_positive"]:
            raise ConfigValidationError(
                "trailing_stop_positive_offset must be greater than trailing_stop_positive"
            )


def _is_pair(p: Any) -> bool:
    return isinstance(p, str) and "/" in p and all(part.isalnum() for part in p.split("/", 1))


def _is_positive_number(v: Any) -> bool:
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False
