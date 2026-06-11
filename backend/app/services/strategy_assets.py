"""Built-in strategy templates emitted into a user's ``strategies/`` directory.

Each template is a self-contained, valid Freqtrade strategy. Users pick one by key
from their settings; the provisioner writes the matching file and launches the bot
with its class. Config-level overrides (pairs, stoploss, minimal_roi, timeframe,
stake/max_open_trades) are applied on top by ``config_builder``.

These strategies use only pandas (no TA-Lib) so they run on the stock image.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategySpec:
    """A selectable strategy template."""

    key: str
    label: str
    class_name: str
    source: str


_OFF_SOURCE = '''\
"""Default no-op strategy: boots cleanly and never opens a trade."""

from pandas import DataFrame

from freqtrade.strategy import IStrategy


class ControlPlaneDefaultStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    stoploss = -0.10
    minimal_roi = {"0": 0.10}
    process_only_new_candles = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        return dataframe
'''

_EMA_CROSS_SOURCE = '''\
"""Simple EMA crossover strategy (pandas only, no TA-Lib).

Enters long when the fast EMA crosses above the slow EMA, exits on the reverse
cross. ROI / stoploss / timeframe are overridden from the bot config.
"""

from pandas import DataFrame

from freqtrade.strategy import IStrategy


class CPEmaCrossStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    stoploss = -0.10
    minimal_roi = {"0": 0.10}
    process_only_new_candles = True
    startup_candle_count = 40

    fast = 10
    slow = 30

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = dataframe["close"].ewm(span=self.fast, adjust=False).mean()
        dataframe["ema_slow"] = dataframe["close"].ewm(span=self.slow, adjust=False).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_up = (dataframe["ema_fast"] > dataframe["ema_slow"]) & (
            dataframe["ema_fast"].shift(1) <= dataframe["ema_slow"].shift(1)
        )
        dataframe.loc[cross_up, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_down = (dataframe["ema_fast"] < dataframe["ema_slow"]) & (
            dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"].shift(1)
        )
        dataframe.loc[cross_down, "exit_long"] = 1
        return dataframe
'''

STRATEGIES: dict[str, StrategySpec] = {
    "off": StrategySpec("off", "Off (no trading)", "ControlPlaneDefaultStrategy", _OFF_SOURCE),
    "ema_cross": StrategySpec("ema_cross", "EMA crossover", "CPEmaCrossStrategy", _EMA_CROSS_SOURCE),
}

DEFAULT_STRATEGY_KEY = "off"


def get_spec(key: str) -> StrategySpec:
    """Return the strategy spec for ``key`` (falling back to the default)."""
    return STRATEGIES.get(key, STRATEGIES[DEFAULT_STRATEGY_KEY])
