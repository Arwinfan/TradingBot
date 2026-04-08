"""
币安 API 客户端封装
支持现货和期货交易
"""

import ccxt
import time
import requests
from typing import Optional, Dict, List, Any
from config.settings import Config


class BinanceClient:
    """
    币安 API 客户端封装类
    支持现货 (spot) 和期货 (futures)
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
        self._exchange = None
        self._exchange_futures = None
        self._testnet_exchange = None
        self._testnet_futures = None
        self._init_exchanges()

    def _init_exchanges(self):
        """初始化交易所实例"""
        proxy = Config.HTTP_PROXY if Config.HTTP_PROXY else None

        # 创建请求会话
        session = requests.Session()
        if proxy:
            session.proxies = {
                'http': proxy,
                'https': proxy,
            }

        # ========== 现货交易 ==========
        spot_config = {
            'apiKey': Config.API_KEY,
            'secret': Config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            },
            'session': session,
        }
        if proxy:
            spot_config['proxy'] = proxy

        self._exchange = ccxt.binance(spot_config)

        # ========== 期货交易 ==========
        futures_config = {
            'apiKey': Config.API_KEY,
            'secret': Config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'futures',  # 重要: 使用期货
            },
            'session': session,
        }
        if proxy:
            futures_config['proxy'] = proxy

        if Config.USE_TESTNET:
            # 测试网期货
            self._testnet_futures = ccxt.binance({
                'apiKey': Config.API_KEY,
                'secret': Config.API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'futures',
                    'testnet': True,
                },
                'session': session,
            })
            if proxy:
                self._testnet_futures.proxies = {'http': proxy, 'https': proxy}
        else:
            # 主网期货
            self._exchange_futures = ccxt.binance(futures_config)

    @property
    def exchange(self):
        """获取当前交易所实例"""
        if Config.is_futures():
            if Config.USE_TESTNET and self._testnet_futures:
                return self._testnet_futures
            return self._exchange_futures or self._exchange
        return self._exchange

    @property
    def is_configured(self):
        """检查是否已配置API密钥"""
        return Config.is_configured()

    @property
    def is_testnet(self):
        """是否使用测试网"""
        return Config.USE_TESTNET

    @property
    def is_futures(self):
        """是否为期货模式"""
        return Config.is_futures()

    def _format_symbol(self, symbol: str) -> str:
        """格式化交易对"""
        if Config.is_futures():
            # 期货格式: BTCUSDT
            return symbol.upper()
        else:
            # 现货格式: BTC/USDT
            return symbol

    # ==================== 市场数据接口 ====================

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """获取单个交易对的实时行情"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            ticker = self.exchange.fetch_ticker(formatted_symbol)
            return {
                'symbol': symbol,
                'last': ticker.get('last'),
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'high': ticker.get('high'),
                'low': ticker.get('low'),
                'volume': ticker.get('baseVolume'),
                'quote_volume': ticker.get('quoteVolume'),
                'change': ticker.get('change'),
                'change_percent': ticker.get('percentage'),
                'timestamp': ticker.get('timestamp'),
            }
        except Exception as e:
            raise APIError(f"获取行情失败: {str(e)}")

    def fetch_tickers(self, symbols: List[str] = None) -> Dict[str, Dict]:
        """获取多个交易对的实时行情"""
        try:
            tickers = {}
            if symbols:
                for symbol in symbols:
                    try:
                        tickers[symbol] = self.fetch_ticker(symbol)
                    except Exception:
                        continue
            else:
                # 获取所有行情
                all_tickers = self.exchange.fetch_tickers()
                for k, v in all_tickers.items():
                    tickers[k] = {
                        'symbol': k,
                        'last': v.get('last'),
                        'bid': v.get('bid'),
                        'ask': v.get('ask'),
                        'high': v.get('high'),
                        'low': v.get('low'),
                        'volume': v.get('baseVolume'),
                        'change_percent': v.get('percentage'),
                        'timestamp': v.get('timestamp'),
                    }
            return tickers
        except Exception as e:
            raise APIError(f"批量获取行情失败: {str(e)}")

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h',
                    limit: int = 100) -> List[List]:
        """获取K线数据"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            ohlcv = self.exchange.fetch_ohlcv(formatted_symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            raise APIError(f"获取K线失败: {str(e)}")

    def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """获取订单簿"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            order_book = self.exchange.fetch_order_book(formatted_symbol, limit)
            return {
                'bids': order_book.get('bids', []),
                'asks': order_book.get('asks', []),
                'timestamp': order_book.get('timestamp'),
            }
        except Exception as e:
            raise APIError(f"获取订单簿失败: {str(e)}")

    def fetch_balance(self) -> Dict:
        """获取账户余额"""
        if not self.is_configured:
            raise APIError("请先配置 API 密钥")

        try:
            balance = self.exchange.fetch_balance()
            return {
                'free': balance.get('free', {}),
                'used': balance.get('used', {}),
                'total': balance.get('total', {}),
                'timestamp': balance.get('timestamp'),
            }
        except Exception as e:
            raise APIError(f"获取余额失败: {str(e)}")

    # ==================== 期货专用接口 ====================

    def fetch_positions(self) -> List[Dict]:
        """获取期货持仓"""
        if not Config.is_futures():
            return []

        try:
            positions = self.exchange.fetch_positions()
            return [{
                'symbol': p.get('symbol'),
                'side': p.get('side'),
                'size': p.get('size'),
                'entryPrice': p.get('entryPrice'),
                'unrealizedPnl': p.get('unrealizedPnl'),
                'leverage': p.get('leverage'),
                'margin': p.get('margin'),
            } for p in positions if p.get('size', 0) != 0]
        except Exception as e:
            raise APIError(f"获取持仓失败: {str(e)}")

    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """设置杠杆"""
        if not Config.is_futures():
            return {}

        try:
            formatted_symbol = self._format_symbol(symbol)
            result = self.exchange.set_leverage(leverage, formatted_symbol)
            return result
        except Exception as e:
            raise APIError(f"设置杠杆失败: {str(e)}")

    # ==================== 交易接口 ====================

    def create_market_buy(self, symbol: str, amount: float) -> Dict:
        """市价买入/做多"""
        if not self.is_configured:
            raise APIError("请先配置 API 密钥")

        try:
            formatted_symbol = self._format_symbol(symbol)
            order = self.exchange.create_market_buy_order(formatted_symbol, amount)
            return self._format_order(order)
        except Exception as e:
            raise APIError(f"市价买入失败: {str(e)}")

    def create_market_sell(self, symbol: str, amount: float) -> Dict:
        """市价卖出/做空"""
        if not self.is_configured:
            raise APIError("请先配置 API 密钥")

        try:
            formatted_symbol = self._format_symbol(symbol)
            order = self.exchange.create_market_sell_order(formatted_symbol, amount)
            return self._format_order(order)
        except Exception as e:
            raise APIError(f"市价卖出失败: {str(e)}")

    def create_limit_buy(self, symbol: str, amount: float, price: float) -> Dict:
        """限价买入/做多"""
        if not self.is_configured:
            raise APIError("请先配置 API 密钥")

        try:
            formatted_symbol = self._format_symbol(symbol)
            order = self.exchange.create_limit_buy_order(formatted_symbol, amount, price)
            return self._format_order(order)
        except Exception as e:
            raise APIError(f"限价买入失败: {str(e)}")

    def create_limit_sell(self, symbol: str, amount: float, price: float) -> Dict:
        """限价卖出/做空"""
        if not self.is_configured:
            raise APIError("请先配置 API 密钥")

        try:
            formatted_symbol = self._format_symbol(symbol)
            order = self.exchange.create_limit_sell_order(formatted_symbol, amount, price)
            return self._format_order(order)
        except Exception as e:
            raise APIError(f"限价卖出失败: {str(e)}")

    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """取消订单"""
        if not self.is_configured:
            raise APIError("请先配置 API 密钥")

        try:
            formatted_symbol = self._format_symbol(symbol)
            order = self.exchange.cancel_order(order_id, formatted_symbol)
            return self._format_order(order)
        except Exception as e:
            raise APIError(f"取消订单失败: {str(e)}")

    def fetch_order(self, order_id: str, symbol: str) -> Dict:
        """查询订单"""
        if not self.is_configured:
            raise APIError("请先配置 API 密钥")

        try:
            formatted_symbol = self._format_symbol(symbol)
            order = self.exchange.fetch_order(order_id, formatted_symbol)
            return self._format_order(order)
        except Exception as e:
            raise APIError(f"查询订单失败: {str(e)}")

    def fetch_open_orders(self, symbol: str = None) -> List[Dict]:
        """获取未完成订单"""
        if not self.is_configured:
            raise APIError("请先配置 API 密钥")

        try:
            if symbol:
                formatted_symbol = self._format_symbol(symbol)
                orders = self.exchange.fetch_open_orders(formatted_symbol)
            else:
                orders = self.exchange.fetch_open_orders()
            return [self._format_order(o) for o in orders]
        except Exception as e:
            raise APIError(f"获取未完成订单失败: {str(e)}")

    def fetch_my_trades(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """获取成交记录"""
        if not self.is_configured:
            raise APIError("请先配置 API 密钥")

        try:
            if symbol:
                formatted_symbol = self._format_symbol(symbol)
                trades = self.exchange.fetch_my_trades(formatted_symbol, limit=limit)
            else:
                trades = self.exchange.fetch_my_trades(limit=limit)
            return [self._format_trade(t) for t in trades]
        except Exception as e:
            raise APIError(f"获取成交记录失败: {str(e)}")

    # ==================== 工具方法 ====================

    def _format_order(self, order: Dict) -> Dict:
        """格式化订单数据"""
        return {
            'id': order.get('id'),
            'symbol': order.get('symbol'),
            'type': order.get('type'),
            'side': order.get('side'),
            'price': order.get('price'),
            'amount': order.get('amount'),
            'filled': order.get('filled', 0),
            'remaining': order.get('remaining', 0),
            'status': order.get('status'),
            'timestamp': order.get('timestamp'),
            'datetime': order.get('datetime'),
        }

    def _format_trade(self, trade: Dict) -> Dict:
        """格式化成交数据"""
        return {
            'id': trade.get('id'),
            'order_id': trade.get('order'),
            'symbol': trade.get('symbol'),
            'side': trade.get('side'),
            'price': trade.get('price'),
            'amount': trade.get('amount'),
            'cost': trade.get('cost'),
            'fee': trade.get('fee'),
            'timestamp': trade.get('timestamp'),
            'datetime': trade.get('datetime'),
        }

    def get_markets(self) -> Dict:
        """获取所有市场信息"""
        try:
            return self.exchange.load_markets()
        except Exception as e:
            raise APIError(f"加载市场信息失败: {str(e)}")

    def get_precision(self, symbol: str) -> Dict:
        """获取交易对精度"""
        markets = self.get_markets()
        formatted_symbol = self._format_symbol(symbol)
        if formatted_symbol in markets:
            market = markets[formatted_symbol]
            return {
                'price': market.get('precision', {}).get('price', 8),
                'amount': market.get('precision', {}).get('amount', 8),
                'min_amount': market.get('limits', {}).get('amount', [{}])[0].get('min', 0),
                'max_amount': market.get('limits', {}).get('amount', [{}])[0].get('max', float('inf')),
            }
        return {'price': 8, 'amount': 8, 'min_amount': 0, 'max_amount': float('inf')}


class APIError(Exception):
    """API 错误异常"""
    pass


# 全局客户端实例
_client = None


def get_client() -> BinanceClient:
    """获取全局API客户端实例"""
    global _client
    if _client is None:
        _client = BinanceClient()
    return _client
