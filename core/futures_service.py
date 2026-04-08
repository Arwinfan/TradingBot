"""
期货市场服务 - 封装期货API调用
"""

from typing import Dict, List
from .futures_client import get_futures_client, APIError
from utils.logger import get_logger

logger = get_logger(__name__)


class FuturesMarketService:
    """
    期货市场服务类
    提供实时行情、K线数据等功能
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._client = get_futures_client()
        self._ticker_cache = {}
        self._cache_expiry = 5

    def get_ticker(self, symbol: str) -> Dict:
        """获取实时行情"""
        try:
            return self._client.get_ticker(symbol)
        except APIError as e:
            logger.error(f"获取行情失败: {e}")
            raise

    def get_tickers(self, symbols: List[str]) -> Dict[str, Dict]:
        """获取多个交易对的行情"""
        tickers = {}
        for symbol in symbols:
            try:
                tickers[symbol] = self._client.get_ticker(symbol)
            except Exception as e:
                logger.warning(f"获取 {symbol} 行情失败: {e}")
                tickers[symbol] = None
        return tickers

    def get_price(self, symbol: str) -> float:
        """获取最新价格"""
        return self._client.get_price(symbol)

    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """获取订单簿"""
        return self._client.get_order_book(symbol, limit)

    def get_ohlcv(self, symbol: str, timeframe: str = '1h',
                  limit: int = 100) -> List[List]:
        """获取K线数据"""
        return self._client.get_klines(symbol, timeframe, limit)

    def get_price_stats(self, symbol: str, timeframe: str = '1h',
                        periods: int = 24) -> Dict:
        """获取价格统计"""
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
            return {}

    def get_market_summary(self) -> Dict:
        """获取市场摘要"""
        from config.settings import Config

        tickers = self.get_tickers(Config.SYMBOLS)

        summary = {
            'timestamp': '',
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


# 全局服务实例
_service = None


def get_futures_market_service() -> FuturesMarketService:
    """获取全局期货市场服务实例"""
    global _service
    if _service is None:
        _service = FuturesMarketService()
    return _service
