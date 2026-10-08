"""TradingView technical analysis ratings (scanner API, non-official)."""

import math
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
    *,
    exchange: str | None = None,
) -> dict[tuple[str, str], Optional[float]]:
    """Fetch ratings in one batch, indexing each response by its actual column.

    ``exchange`` is an explicit per-bot market; the existing public panel can omit
    it to retain its default-exchange reference. Unsupported symbols stay missing.
    """
    exchange = (exchange or get_settings().default_exchange).upper()
    columns: list[str] = []
    symbols: dict[str, list[tuple[str, str, int]]] = {}
    for timeframe, pairs in pairs_by_timeframe.items():
        suffix = _TIMEFRAME_COLUMN_MAP.get(timeframe)
        if suffix is None:
            continue
        column = f"Recommend.All{suffix}"
        if column not in columns:
            columns.append(column)
        column_index = columns.index(column)
        for pair in sorted(pairs):
            symbol = f"{exchange}:{pair.replace('/', '').upper()}"
            symbols.setdefault(symbol, []).append((pair, timeframe, column_index))
    if not symbols:
        return {}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(
                "https://scanner.tradingview.com/crypto/scan",
                json={"symbols": {"tickers": list(symbols)}, "columns": columns},
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("TradingView scanner failed: %s", exc)
        return {}

    result: dict[tuple[str, str], Optional[float]] = {}
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return result
    for row in data["data"]:
        if not isinstance(row, dict) or not isinstance(row.get("s"), str):
            continue
        values = row.get("d")
        if not isinstance(values, list):
            continue
        for pair, timeframe, index in symbols.get(row["s"], []):
            value = values[index] if index < len(values) else None
            result[(pair, timeframe)] = (
                float(value)
                if type(value) in (int, float) and math.isfinite(value) and -1 <= value <= 1
                else None
            )
    return result
