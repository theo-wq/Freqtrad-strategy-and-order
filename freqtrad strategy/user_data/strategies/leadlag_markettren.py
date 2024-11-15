# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from typing import Optional, Union
from functools import reduce
import os
from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IStrategy, IntParameter, merge_informative_pair)

# --------------------------------
# Add your lib to import here
import time
import hmac
import hashlib
import requests
import logging
import json
from datetime import datetime, timedelta
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

logger = logging.getLogger(__name__)
# This class is a sample. Feel free to customize it.

class ImprovedLeadlagMarketTrend(IStrategy):

    INTERFACE_VERSION = 3
    can_short: bool = False

    # Minimal ROI and stoploss remain the same
    minimal_roi = {
        "2400": 0.007,
        "1400": 0.009,
        "60": 0.01,
        "30": 0.015
    }
    stoploss = -0.06

    # Trailing stoploss settings remain the same
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    timeframe = '5m'

    # Hyperoptable parameters
    short_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    exit_short_rsi = IntParameter(low=50, high=100, default=70, space='sell', optimize=True, load=True)
    buy_rsi = IntParameter(low=51, high=100, default=70, space='buy', optimize=True, load=True)
    sell_rsi = IntParameter(low=1, high=50, default=30, space='sell', optimize=True, load=True)

    # New parameters for trend determination
    short_ma_period = IntParameter(150, 250, default=200, space='buy', optimize=True)
    long_ma_period = IntParameter(10, 50, default=20, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Keep existing indicators
        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['rsi'] = ta.RSI(dataframe)
        stoch_fast = ta.STOCHF(dataframe)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        dataframe['mfi'] = ta.MFI(dataframe)

        # Add new indicators for trend determination
        dataframe['long_ma'] = ta.SMA(dataframe, timeperiod=self.long_ma_period.value)
        dataframe['short_ma'] = ta.SMA(dataframe, timeperiod=self.short_ma_period.value)
        
        # Add ATR for volatility measurement
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = [
            (dataframe['close'] < dataframe['long_ma']),  # Confirm downtrend
            (dataframe['short_ma'] < dataframe['long_ma']),  # Short-term MA below long-term MA
            (dataframe['rsi'] > self.short_rsi.value),  # RSI overbought
            (dataframe['fastk'] > 80),  # Stochastic overbought
            (dataframe['macd'] < dataframe['macdsignal']),  # MACD bearish
            (dataframe['adx'] > 25),  # Strong trend
            (dataframe['volume'] > 0)  # Ensure volume
        ]

        dataframe.loc[reduce(lambda x, y: x & y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = [
            (dataframe['rsi'] < self.exit_short_rsi.value),  # RSI oversold
            (dataframe['close'] > dataframe['short_ma']),  # Price above short-term MA
            (dataframe['fastk'] < 20),  # Stochastic oversold
            (qtpylib.crossed_above(dataframe['macd'], dataframe['macdsignal'])),  # MACD bullish crossover
            (dataframe['volume'] > 0)  # Ensure volume
        ]

        dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit_short'] = 1
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float, 
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str], 
                            side: str, **kwargs) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        # Additional checks for short entry
        if side == 'short':
            # Check if the market is in a clear downtrend
            if last_candle['close'] > last_candle['long_ma'] or last_candle['adx'] < 25:
                return False
            
            # Check for increased volatility
            if last_candle['atr'] < last_candle['atr'].rolling(window=14).mean():
                return False

        return True