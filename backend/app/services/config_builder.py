"""Build the per-user Freqtrade ``config.json`` (non-secret fields only).

Secrets (exchange key/secret, api_server username/password/jwt_secret/ws_token) are
deliberately omitted from the file and injected at container launch via
``FREQTRADE__*`` environment variables, which Freqtrade merges into the config
before schema validation. See ``freqtrade/configuration/environment_vars.py``.
"""

from copy import deepcopy
from typing import Any

from app.config import get_settings
from app.services import bot_config

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
        # BNB is blacklisted on Freqtrade's own recommendation for Binance (docs/
        # exchanges.md "Binance Blacklist recommendation"): the account pays fees in BNB,
        # so a trade holding BNB can become unsellable once fees eat into the position.
        # ``bot_config.COMMON_BASE_COINS`` omits BNB to match.
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
        pairlist_mode, pairs, volume_number_assets, stake_amount, max_open_trades,
        stoploss, roi_table, timeframe, trailing_stop*, dry_run_wallet.
    """
    settings = get_settings()
    config = deepcopy(_BASE_CONFIG)

    config["bot_name"] = username
    config["dry_run"] = dry_run
    config["dry_run_wallet"] = user_config["dry_run_wallet"]
    config["exchange"]["name"] = exchange_name

    # Real money: bound the total capital the bot may ever deploy. Freqtrade computes
    # available capital as ``available_capital + closed profit`` and ignores the real
    # wallet balance entirely (freqtrade/wallets.py get_total_stake_amount), so this holds
    # even if the exchange account is funded with far more. This is a second, independent
    # guard: ``bot_config.validate`` already refused unsafe live settings upstream.
    # Note it supersedes ``tradable_balance_ratio`` above, which stays for the dry-run path
    # (see freqtrade docs/configuration.md "Incompatible with tradable_balance_ratio").
    if not dry_run:
        config["available_capital"] = settings.live_max_capital

    # Apply the user-editable, schema-safe fields. The quote currency is fixed to USDT.
    config["stake_currency"] = bot_config.STAKE_CURRENCY
    config["stake_amount"] = user_config["stake_amount"]
    config["max_open_trades"] = user_config["max_open_trades"]
    config["stoploss"] = user_config["stoploss"]
    config["minimal_roi"] = {str(s["minutes"]): s["roi"] for s in user_config["roi_table"]}
    config["timeframe"] = user_config["timeframe"]

    # Trailing stop: only emit the positive/offset knobs when actually enabled.
    config["trailing_stop"] = user_config["trailing_stop"]
    if user_config["trailing_stop"] and user_config["trailing_stop_positive"] is not None:
        config["trailing_stop_positive"] = user_config["trailing_stop_positive"]
        if user_config["trailing_stop_positive_offset"] > 0:
            config["trailing_stop_positive_offset"] = user_config["trailing_stop_positive_offset"]
            config["trailing_only_offset_is_reached"] = True

    # Pairlist: a manual static whitelist, or top-N-by-volume auto-discovery.
    if user_config["pairlist_mode"] == "volume":
        config["pairlists"] = [
            {
                "method": "VolumePairList",
                "number_assets": user_config["volume_number_assets"],
                "sort_key": "quoteVolume",
                "refresh_period": 1800,
            }
        ]
        config["exchange"]["pair_whitelist"] = []  # VolumePairList generates it
    else:
        config["pairlists"] = [{"method": "StaticPairList"}]
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
