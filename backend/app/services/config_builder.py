"""Build the per-user Freqtrade ``config.json`` (non-secret fields only).

Secrets (exchange key/secret, api_server username/password/jwt_secret/ws_token) are
deliberately omitted from the file and injected at container launch via
``FREQTRADE__*`` environment variables, which Freqtrade merges into the config
before schema validation. See ``freqtrade/configuration/environment_vars.py``.
"""

from copy import deepcopy
from typing import Any

from app.config import get_settings

# A minimal, valid base config modelled on Freqtrade's example config.json.
# ``timeframe``, ``stoploss`` and ``minimal_roi`` are supplied by the strategy.
_BASE_CONFIG: dict[str, Any] = {
    "max_open_trades": 3,
    "stake_currency": "USDT",
    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.99,
    # Disabled: fiat conversion calls CoinGecko at startup and would block the bot
    # (and its REST API) where CoinGecko is unreachable. Enable per-deployment if needed.
    "fiat_display_currency": "",
    "dry_run": True,
    "dry_run_wallet": 1000,
    "cancel_open_orders_on_exit": False,
    "trading_mode": "spot",
    "margin_mode": "",
    "unfilledtimeout": {"entry": 10, "exit": 10, "exit_timeout_count": 0, "unit": "minutes"},
    "entry_pricing": {
        "price_side": "same",
        "use_order_book": True,
        "order_book_top": 1,
        "price_last_balance": 0.0,
        "check_depth_of_market": {"enabled": False, "bids_to_ask_delta": 1},
    },
    "exit_pricing": {"price_side": "same", "use_order_book": True, "order_book_top": 1},
    "exchange": {
        "name": "binance",
        "ccxt_config": {},
        "ccxt_async_config": {},
        "pair_whitelist": ["BTC/USDT", "ETH/USDT"],
        "pair_blacklist": ["BNB/.*"],
    },
    "pairlists": [{"method": "StaticPairList"}],
    "initial_state": "stopped",
    "force_entry_enable": False,
    "internals": {"process_throttle_secs": 5},
}


def build_bot_config(
    *,
    username: str,
    exchange_name: str,
    dry_run: bool,
    user_config: dict[str, Any],
) -> dict[str, Any]:
    """Return the config dict to be written to a user's ``config.json``.

    :param username: becomes ``bot_name`` and the CORS/identity label.
    :param exchange_name: ccxt exchange id (e.g. ``binance``).
    :param dry_run: when ``True`` no real orders are placed.
    :param user_config: validated user-editable settings (see ``services.bot_config``):
        pairs, stake_currency, stake_amount, max_open_trades, stoploss, roi, timeframe.
    """
    settings = get_settings()
    config = deepcopy(_BASE_CONFIG)

    config["bot_name"] = username
    config["dry_run"] = dry_run
    config["exchange"]["name"] = exchange_name

    # Apply the user-editable, schema-safe fields.
    config["stake_currency"] = user_config["stake_currency"]
    config["stake_amount"] = user_config["stake_amount"]
    config["max_open_trades"] = user_config["max_open_trades"]
    config["stoploss"] = user_config["stoploss"]
    config["minimal_roi"] = {"0": user_config["roi"]}
    config["timeframe"] = user_config["timeframe"]
    config["exchange"]["pair_whitelist"] = list(user_config["pairs"])

    # api_server: secrets injected via env, so they are intentionally absent here.
    config["api_server"] = {
        "enabled": True,
        "listen_ip_address": "0.0.0.0",  # internal docker network only; no host port
        "listen_port": 8080,
        "verbosity": "info",
        "enable_openapi": False,
        "CORS_origins": [settings.public_origin],
    }
    return config
