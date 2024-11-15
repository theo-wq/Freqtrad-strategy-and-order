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


class leadlag_markettrend_short(IStrategy):

# in this strategy (we) are trying to optimise the simple leadlag by adding SMA on a 200 period, stochastic, MACD and ATR for volatility
    load_dotenv()

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.cross_margin_pairs = {}
        self.last_update = datetime.min
        self.update_interval = timedelta(hours=1)

        api_key = os.getenv('API_KEY')
        api_secret = os.getenv('API_SECRET')

    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "2400": 0.007,
        "1400": 0.009,
        "60": 0.01,
        "30": 0.015
    }

    stoploss = -0.06

    # Trailing stoploss
    trailing_stop = True
    trailing_stop_positive = 0.01  # 1%
    trailing_stop_positive_offset = 0.02  # 2%
    trailing_only_offset_is_reached = True
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # Optimal timeframe for the strategy.
    timeframe = '5m'

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Hyperoptable parameters
    buy_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    sell_rsi = IntParameter(low=50, high=100, default=70, space='sell', optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)
    exit_short_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    # Optional order type mapping.
    order_types = {
        'entry': 'limit',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    def informative_pairs(self):
        return [(f"BTC/USDT", '1d')]

    # Optional order time in force.
    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }

    plot_config = {
        'main_plot': {
            'tema': {},
            'sar': {'color': 'white'},
        },
        'subplots': {
            "MACD": {
                'macd': {'color': 'blue'},
                'macdsignal': {'color': 'orange'},
            },
            "RSI": {
                'rsi': {'color': 'red'},
            }
        }
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # Momentum Indicators
        # ------------------------------------

        dataframe['adx'] = ta.ADX(dataframe)

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe)

        # Stochastic Fast
        stoch_fast = ta.STOCHF(dataframe)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']

        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # MFI
        dataframe['mfi'] = ta.MFI(dataframe)

        # OverlapStudies
        # ------------------------------------

        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe["bb_percent"] = (
            (dataframe["close"] - dataframe["bb_lowerband"]) /
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"])
        )
        dataframe["bb_width"] = (
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        )

        # Parabolic SAR
        dataframe['sar'] = ta.SAR(dataframe)

        # TEMA - Triple Exponential Moving Average
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)

        # Cycle Indicator
        # ------------------------------------
        # Hilbert Transform Indicator - SineWave
        hilbert = ta.HT_SINE(dataframe)
        dataframe['htsine'] = hilbert['sine']
        dataframe['htleadsine'] = hilbert['leadsine']


        informativebtc = self.dp.get_pair_dataframe(pair=f"BTC/USDT", timeframe="1d")
        informativebtc5 = self.dp.get_pair_dataframe(pair=f"BTC/USDT", timeframe="5m")
        # calculate SMA20 on informative pair
        # Combine the 2 dataframe
        # This will result in a column named 'closeETH' or 'closeBTC' - depending on stake_currency.
        dataframe = merge_informative_pair(dataframe, informativebtc, self.timeframe, "1d", ffill=True,append_timeframe =False, suffix="BTC")
        dataframe = merge_informative_pair(dataframe, informativebtc5, self.timeframe, "5m", ffill=True,append_timeframe =False, suffix="BTC5")

        return dataframe


    def get_binance_signature(self, data):

        return hmac.new(self.binance_api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()

    def update_cross_margin_pairs(self):
        current_time = datetime.now()
        if current_time - self.last_update > self.update_interval:
            try:
                timestamp = int(time.time() * 1000)
                params = f"timestamp={timestamp}"
                signature = self.get_binance_signature(params)

                headers = {
                    'X-MBX-APIKEY': self.binance_api_key
                }

                url = f"https://api.binance.com/sapi/v1/margin/allPairs?{params}&signature={signature}"

                logger.info(f"Envoi de la requête à l'URL : {url}")
                response = requests.get(url, headers=headers)

                logger.info(f"Code de statut de la réponse : {response.status_code}")
                logger.info(f"Contenu de la réponse : {response.text[:200]}...")  # Log des 200 premiers caractères

                if response.status_code == 200:
                    pairs = response.json()
                    self.cross_margin_pairs = {pair['symbol']: pair['isMarginTrade'] for pair in pairs}
                    self.last_update = current_time
                    with open('cross_margin_pairs.json', 'w') as f:
                        json.dump(self.cross_margin_pairs, f)
                    logger.info("Mise à jour des paires cross margin réussie")
                else:
                    logger.error(f"Erreur lors de la récupération des paires cross margin: {response.status_code}")
                    logger.error(f"Message d'erreur: {response.text}")
            except Exception as e:
                logger.error(f"Exception lors de la mise à jour des paires cross margin: {str(e)}")


    def check_cross_margin_short_availability(self, symbol: str) -> bool:
        try:
            self.update_cross_margin_pairs()
            return self.cross_margin_pairs.get(symbol, False)
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de la disponibilité du short pour {symbol}: {str(e)}")
            return False


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        pair = metadata['pair']
        symbol = pair.replace('/', '')
        is_short_available = self.check_cross_margin_short_availability(symbol)


        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            dataframe[col] = pd.to_numeric(dataframe[col], errors='coerce')

        if 'date' in dataframe.columns:
            dataframe['date'] = pd.to_datetime(dataframe['date'], errors='coerce')

        dataframe['sma_200'] = ta.SMA(dataframe['close'], timeperiod=200)
        dataframe['atr'] = ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        dataframe['stoch_k'], dataframe['stoch_d'] = ta.STOCH(dataframe['high'], dataframe['low'], dataframe['close'], fastk_period=14, slowk_period=3, slowd_period=3)

        dataframe['macd'], dataframe['signal'], _ = ta.MACD(dataframe['close'], fastperiod=12, slowperiod=26, signalperiod=9)

        if 'tema' not in dataframe.columns:
            dataframe['tema'] = ta.TEMA(dataframe['close'], timeperiod=9)
        if 'bb_middleband' not in dataframe.columns:
            dataframe['bb_upperband'], dataframe['bb_middleband'], dataframe['bb_lowerband'] = ta.BBANDS(dataframe['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)

        if 'rsi' not in dataframe.columns:
            dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)

        conditions = [
            qtpylib.crossed_above(dataframe['rsi'], self.buy_rsi.value),
            dataframe['tema'] <= dataframe['bb_middleband'],
            dataframe['close'] < dataframe['sma_200'],  # Tendance baissière à long terme ASKIP
            dataframe['stoch_k'] < 20,  # Survendu sur le stochastique
            dataframe['macd'] < dataframe['signal'],  # MACD sous la ligne
            dataframe['volume'] > 0,
            dataframe['atr'] > dataframe['atr'].rolling(window=14).mean(), # Volatilité supérieure à la moyenne
            pd.Series(is_short_available, index=dataframe.index) # commenter la condition pour backtest

        ]

        dataframe['enter_long'] = reduce(lambda x, y: x & y, conditions).astype('int')

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'rsi', 'tema', 'bb_middleband', 'stoch_k', 'macd', 'signal']
        for col in numeric_columns:
            dataframe[col] = pd.to_numeric(dataframe[col], errors='coerce')


        conditions = [
            (dataframe['rsi'] > 50),
            (dataframe['close'] > dataframe['bb_middleband'] * 0.995),
            (dataframe['stoch_k'] > 50),
            (qtpylib.crossed_above(dataframe['macd'], dataframe['signal'])),
            (dataframe['volume'] > 0)
        ]

        dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit_short'] = 1

        return dataframe