"""Built-in minimal strategy emitted into a user's ``strategies/`` directory.

This is a safe, valid Freqtrade strategy that defines the schema-required
``timeframe``/``stoploss``/``minimal_roi`` and never generates entries. It lets a
freshly provisioned bot boot (so its REST API answers) without trading until a real
strategy is assigned. Real strategies are uploaded/assigned in later phases.
"""

DEFAULT_STRATEGY_CLASS = "ControlPlaneDefaultStrategy"

DEFAULT_STRATEGY_SOURCE = '''\
"""Auto-generated default strategy for a control-plane provisioned bot.

It boots cleanly and never enters trades. Replace it by assigning a real strategy.
"""

from pandas import DataFrame

from freqtrade.strategy import IStrategy


class ControlPlaneDefaultStrategy(IStrategy):
    """No-op strategy: valid, dry-run-safe, never opens a position."""

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
