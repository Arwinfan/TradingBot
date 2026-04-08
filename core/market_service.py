"""
行情服务 - 提供实时行情和历史数据
"""

import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque

from .futures_client import get_futures_client, APIError
from utils.logger import get_logger

logger = get_logger(__name__)


class MarketService:
    """
    行情服务类
    提供实时行情、K线数据、技术指标计算等功能
    """

    _instance = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._client = get_futures_client()
        self._ticker_cache = {}  # 行情缓存
        self._kline_cache = {}   # K线缓存
        self._cache_expiry = 5   # 缓存过期时间(秒)

    def get_ticker(self, symbol: str, use_cache: bool = True) -> Dict:
        """
        获取实时行情

        Args:
            symbol: 交易对
            use_cache: 是否使用缓存

        Returns:
            行情数据字典
        """
        current_time = time.time()

        # 检查缓存
        if use_cache and symbol in self._ticker_cache:
            cached = self._ticker_cache[symbol]
            if current_time - cached['cache_time'] < self._cache_expiry:
                return cached['data']

        # 获取新数据
        try:
            ticker = self._client.get_ticker(symbol)
            self._ticker_cache[symbol] = {
                'data': ticker,
                'cache_time': current_time,
            }
            return ticker
        except APIError as e:
            logger.error(f"获取行情失败: {e}")
            # 返回缓存数据(如果存在)
            if symbol in self._ticker_cache:
                return self._ticker_cache[symbol]['data']
            raise

    def get_tickers(self, symbols: List[str] = None) -> Dict[str, Dict]:
        """
        获取多个交易对的行情

        Args:
            symbols: 交易对列表

        Returns:
            行情字典
        """
        if symbols is None:
            symbols = []

        tickers = {}
        for symbol in symbols:
            try:
                tickers[symbol] = self.get_ticker(symbol)
            except Exception as e:
                logger.warning(f"获取 {symbol} 行情失败: {e}")
                tickers[symbol] = None

        return tickers

    def get_ohlcv(self, symbol: str, timeframe: str = '1h',
                   limit: int = 100, use_cache: bool = True) -> List[List]:
        """
        获取K线数据

        Args:
            symbol: 交易对
            timeframe: K线周期
            limit: 数据数量
            use_cache: 是否使用缓存

        Returns:
            K线数据列表 [[timestamp, open, high, low, close, volume], ...]
        """
        cache_key = f"{symbol}_{timeframe}_{limit}"
        current_time = time.time()

        # 检查缓存 (K线缓存时间更长)
        if use_cache and cache_key in self._kline_cache:
            cached = self._kline_cache[cache_key]
            if current_time - cached['cache_time'] < 60:  # 1分钟缓存
                return cached['data']

        # 获取新数据
        try:
            ohlcv = self._client.get_klines(symbol, timeframe, limit)
            self._kline_cache[cache_key] = {
                'data': ohlcv,
                'cache_time': current_time,
            }
            return ohlcv
        except APIError as e:
            logger.error(f"获取K线失败: {e}")
            if cache_key in self._kline_cache:
                return self._kline_cache[cache_key]['data']
            raise

    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """
        获取订单簿

        Args:
            symbol: 交易对
            limit: 深度数量

        Returns:
            订单簿数据
        """
        try:
            return self._client.get_order_book(symbol, limit)
        except APIError as e:
            logger.error(f"获取订单簿失败: {e}")
            raise

    def get_price_stats(self, symbol: str, timeframe: str = '1h',
                        periods: int = 24) -> Dict:
        """
        获取价格统计数据

        Args:
            symbol: 交易对
            timeframe: K线周期
            periods: 统计周期数

        Returns:
            价格统计数据
        """
        try:
            ohlcv = self.get_ohlcv(symbol, timeframe, periods)

            if not ohlcv:
                return {}

            closes = [k[4] for k in ohlcv]
            volumes = [k[5] for k in ohlcv]
            highs = [k[2] for k in ohlcv]
            lows = [k[3] for k in ohlcv]

            return {
                'current_price': closes[-1] if closes else 0,
                'price_change': closes[-1] - closes[0] if len(closes) > 1 else 0,
                'price_change_percent': ((closes[-1] / closes[0]) - 1) * 100 if len(closes) > 1 and closes[0] > 0 else 0,
                'high': max(highs) if highs else 0,
                'low': min(lows) if lows else 0,
                'avg_price': sum(closes) / len(closes) if closes else 0,
                'total_volume': sum(volumes) if volumes else 0,
                'avg_volume': sum(volumes) / len(volumes) if volumes else 0,
                'periods': periods,
                'timeframe': timeframe,
            }
        except Exception as e:
            logger.error(f"获取价格统计失败: {e}")
            raise

    def get_support_resistance(self, symbol: str, timeframe: str = '1d',
                                 limit: int = 100) -> Dict:
        """
        计算支撑位和压力位 (使用枢轴点)

        Args:
            symbol: 交易对
            timeframe: K线周期
            limit: 数据数量

        Returns:
            支撑位和压力位数据
        """
        try:
            ohlcv = self.get_ohlcv(symbol, timeframe, limit)

            if len(ohlcv) < 3:
                return {}

            # 使用最近3根K线计算枢轴点
            last_3 = ohlcv[-3:]
            high_prices = [k[2] for k in last_3]
            low_prices = [k[3] for k in last_3]
            close_prices = [k[4] for k in last_3]

            last_high = high_prices[-1]
            last_low = low_prices[-1]
            last_close = close_prices[-1]

            # 枢轴点
            pivot = (last_high + last_low + last_close) / 3

            # 支撑位
            s1 = (2 * pivot) - last_high
            s2 = pivot - (last_high - last_low)
            s3 = last_low - 2 * (last_high - pivot)

            # 压力位
            r1 = (2 * pivot) - last_low
            r2 = pivot + (last_high - last_low)
            r3 = last_high + 2 * (pivot - last_low)

            current_price = self.get_ticker(symbol).get('last', 0)

            return {
                'pivot': pivot,
                'resistance': {
                    'r1': r1,
                    'r2': r2,
                    'r3': r3,
                },
                'support': {
                    's1': s1,
                    's2': s2,
                    's3': s3,
                },
                'current_price': current_price,
                'distance_to_resistance': ((r1 - current_price) / current_price * 100) if current_price > 0 else 0,
                'distance_to_support': ((current_price - s1) / current_price * 100) if current_price > 0 else 0,
            }
        except Exception as e:
            logger.error(f"计算支撑压力位失败: {e}")
            return {}

    def get_market_summary(self) -> Dict:
        """
        获取市场摘要

        Returns:
            市场摘要信息
        """
        from config.settings import Config

        tickers = self.get_tickers(Config.SYMBOLS)

        summary = {
            'timestamp': datetime.now().isoformat(),
            'markets': {},
            'total_markets': len(tickers),
            'online_markets': sum(1 for t in tickers.values() if t is not None),
        }

        for symbol, ticker in tickers.items():
            if ticker:
                summary['markets'][symbol] = {
                    'price': ticker.get('last'),
                    'change_24h': ticker.get('change_percent'),
                    'volume_24h': ticker.get('quote_volume'),
                    'high_24h': ticker.get('high'),
                    'low_24h': ticker.get('low'),
                }

        return summary

    def clear_cache(self):
        """清空缓存"""
        self._ticker_cache.clear()
        self._kline_cache.clear()
        logger.info("行情缓存已清空")


# 全局服务实例
_service = None


def get_market_service() -> MarketService:
    """获取全局行情服务实例"""
    global _service
    if _service is None:
        _service = MarketService()
    return _service
