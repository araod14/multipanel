"""TradingView technical analysis ratings (scanner API, non-official)."""

import asyncio
import logging
from typing import Optional

import httpx

from ..config import get_settings

logger = logging.getLogger("control_plane.tradingview")

_TIMEOUT_S = 10.0

# Map freqtrade timeframes to TradingView scanner columns.
# TradingView columns: "Recommend.All" = 1d, "|1|5|15|30|60|120|240|1W|1M" (in minutes or W/M).
_TIMEFRAME_COLUMN_MAP = {
    "1m": "|1",
    "5m": "|5",
    "15m": "|15",
    "30m": "|30",
    "1h": "|60",
    "2h": "|120",
    "4h": "|240",
    "1d": "",  # "Recommend.All" (default)
    "1w": "|1W",
    "1M": "|1M",
}


def label(value: Optional[float]) -> Optional[str]:
    """Map TradingView rating value to Spanish label.

    Values are in range [-1, 1], approximately:
      >= 0.5: Compra fuerte
      >= 0.1: Compra
      > -0.1: Neutral
      > -0.5: Venta
      <= -0.5: Venta fuerte
    """
    if value is None:
        return None
    if value >= 0.5:
        return "Compra fuerte"
    if value >= 0.1:
        return "Compra"
    if value > -0.1:
        return "Neutral"
    if value > -0.5:
        return "Venta"
    return "Venta fuerte"


async def ratings(
    pairs_by_timeframe: dict[str, set[str]],
) -> dict[tuple[str, str], Optional[float]]:
    """Fetch TradingView technical ratings for pairs across timeframes.

    Args:
        pairs_by_timeframe: {timeframe -> set of pairs in BASE/USDT format}

    Returns:
        {(pair, timeframe): rating_value or None}
        Pairs with no rating (unknown symbol) are omitted.
    """
    if not pairs_by_timeframe:
        return {}

    settings = get_settings()
    exchange = settings.default_exchange.upper()

    # Build symbol list for each timeframe: EXCHANGE:BASEUSDT
    symbols_by_column: dict[str, list[tuple[str, str]]] = {}
    for timeframe, pairs in pairs_by_timeframe.items():
        column = _TIMEFRAME_COLUMN_MAP.get(timeframe)
        if column is None:
            logger.debug(f"Timeframe {timeframe} not mapped; skipping.")
            continue
        full_column = f"Recommend.All{column}"
        if full_column not in symbols_by_column:
            symbols_by_column[full_column] = []
        for pair in pairs:
            # pair is "BASE/USDT"; drop the quote.
            base = pair.split("/")[0].upper()
            symbol = f"{exchange}:{base}USDT"
            symbols_by_column[full_column].append((symbol, pair, timeframe))

    result: dict[tuple[str, str], Optional[float]] = {}

    # Batch all symbols and columns into one POST.
    tickers = []
    symbol_to_info: dict[str, list[tuple[str, str]]] = {}  # symbol -> [(pair, timeframe), ...]
    for col, pairs_info in symbols_by_column.items():
        for symbol, pair, timeframe in pairs_info:
            if symbol not in symbol_to_info:
                tickers.append(symbol)
                symbol_to_info[symbol] = []
            symbol_to_info[symbol].append((pair, timeframe))

    if not tickers:
        return {}

    payload = {
        "symbols": {"tickers": tickers},
        "columns": list(symbols_by_column.keys()),
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(
                "https://scanner.tradingview.com/crypto/scan",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.warning(f"TradingView scanner failed: {e}")
        return {}

    # Parse response: {"data": [{"s": "BINANCE:BTCUSDT", "d": [0.22, ...]}, ...]}
    try:
        for row in data.get("data", []):
            symbol = row.get("s")
            values = row.get("d", [])
            if not symbol or not values:
                continue

            # values[i] corresponds to symbols_by_column.keys()[i]
            for (pair, timeframe), value in zip(
                symbol_to_info.get(symbol, []), values
            ):
                result[(pair, timeframe)] = value if isinstance(value, (int, float)) else None
    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"TradingView response parse error: {e}")

    return result
