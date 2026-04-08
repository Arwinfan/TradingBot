"""
币安期货 API 客户端 (Demo版)
使用 demo-fapi.binance.com 端点
"""

import requests
import hashlib
import hmac
import time
from typing import Dict, List, Optional, Any
from config.settings import Config


class FuturesClient:
    """
    币安期货 API 客户端
    支持 Demo 和 生产环境
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

        # Demo 端点
        self._demo_base = 'https://demo-fapi.binance.com'
        # 生产端点
        self._prod_base = 'https://fapi.binance.com'

        # 代理
        self._proxies = {}
        if Config.HTTP_PROXY:
            self._proxies = {
                'http': Config.HTTP_PROXY,
                'https': Config.HTTP_PROXY,
            }

    @property
    def base_url(self) -> str:
        """获取API基础URL"""
        if Config.USE_TESTNET:
            return self._demo_base
        return self._prod_base

    @property
    def is_configured(self) -> bool:
        """检查是否已配置API密钥"""
        return bool(Config.API_KEY and Config.API_SECRET)

    def _sign(self, params: str) -> str:
        """生成签名"""
        return hmac.new(
            Config.API_SECRET.encode(),
            params.encode(),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, endpoint: str, signed: bool = False,
                 params: Dict = None) -> Any:
        """发送请求"""
        url = f"{self.base_url}{endpoint}"

        headers = {
            'X-MBX-APIKEY': Config.API_KEY,
        }

        if signed:
            timestamp = int(time.time() * 1000)
            params = params or {}
            params['timestamp'] = timestamp
            params['recvWindow'] = 60000  # 增加recvWindow

            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            signature = self._sign(query_string)
            url = f"{url}?{query_string}&signature={signature}"
        elif params:
            url = f"{url}?" + '&'.join([f"{k}={v}" for k, v in params.items()])

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers,
                                      proxies=self._proxies, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers,
                                       proxies=self._proxies, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers,
                                        proxies=self._proxies, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
                raise APIError(f"{error_data.get('msg', str(e))}")
            except:
                raise APIError(str(e))
        except Exception as e:
            raise APIError(str(e))

    # ==================== 市场数据 ====================

    def get_ticker(self, symbol: str) -> Dict:
        """获取行情"""
        data = self._request('GET', '/fapi/v1/ticker/24hr', params={'symbol': symbol})
        return {
            'symbol': data['symbol'],
            'last': float(data['lastPrice']),
            'bid': float(data.get('bidPrice', 0)),
            'ask': float(data.get('askPrice', 0)),
            'high': float(data.get('highPrice', 0)),
            'low': float(data.get('lowPrice', 0)),
            'volume': float(data.get('volume', 0)),
            'quote_volume': float(data.get('quoteVolume', 0)),
            'change': float(data.get('priceChange', 0)),
            'change_percent': float(data.get('priceChangePercent', 0)),
            'timestamp': data.get('closeTime', 0),
        }

    def get_price(self, symbol: str) -> float:
        """获取最新价格"""
        data = self._request('GET', '/fapi/v1/ticker/price', params={'symbol': symbol})
        return float(data['price'])

    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """获取订单簿"""
        data = self._request('GET', '/fapi/v1/depth',
                           params={'symbol': symbol, 'limit': limit})
        return {
            'bids': [[float(p), float(q)] for p, q in data['bids']],
            'asks': [[float(p), float(q)] for p, q in data['asks']],
        }

    def get_klines(self, symbol: str, interval: str = '1h',
                   limit: int = 100) -> List:
        """获取K线数据"""
        data = self._request('GET', '/fapi/v1/klines', params={
            'symbol': symbol,
            'interval': interval,
            'limit': limit,
        })
        return [[
            d[0],  # timestamp
            float(d[1]),  # open
            float(d[2]),  # high
            float(d[3]),  # low
            float(d[4]),  # close
            float(d[5]),  # volume
        ] for d in data]

    def get_exchange_info(self) -> Dict:
        """获取交易所信息"""
        return self._request('GET', '/fapi/v1/exchangeInfo')

    # ==================== 账户操作 ====================

    def get_balance(self) -> Dict:
        """获取账户余额"""
        data = self._request('GET', '/fapi/v2/balance', signed=True)
        return {
            'free': {item['asset']: float(item['availableBalance']) for item in data},
            'total': {item['asset']: float(item['balance']) for item in data},
        }

    def get_positions(self) -> List[Dict]:
        """获取持仓"""
        data = self._request('GET', '/fapi/v2/positionRisk', signed=True)
        return [{
            'symbol': p['symbol'],
            'side': 'long' if float(p['positionAmt']) > 0 else 'short',
            'size': abs(float(p['positionAmt'])),
            'entry_price': float(p['entryPrice']),
            'unrealized_pnl': float(p['unRealizedProfit']),
            'leverage': int(p['leverage']),
            'margin_type': p['marginType'],
        } for p in data if float(p['positionAmt']) != 0]

    def get_position(self, symbol: str) -> Optional[Dict]:
        """获取指定交易对持仓"""
        positions = self.get_positions()
        for p in positions:
            if p['symbol'] == symbol:
                return p
        return None

    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """设置杠杆"""
        return self._request('POST', '/fapi/v1/leverage',
                            signed=True, params={'symbol': symbol, 'leverage': leverage})

    # ==================== 交易操作 ====================

    def market_buy(self, symbol: str, quantity: float) -> Dict:
        """市价买入/做多"""
        result = self._request('POST', '/fapi/v1/order', signed=True, params={
            'symbol': symbol,
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': quantity,
        })
        result['success'] = True
        return result

    def market_sell(self, symbol: str, quantity: float) -> Dict:
        """市价卖出/做空"""
        result = self._request('POST', '/fapi/v1/order', signed=True, params={
            'symbol': symbol,
            'side': 'SELL',
            'type': 'MARKET',
            'quantity': quantity,
        })
        result['success'] = True
        return result

    def close_position(self, symbol: str, side: str, quantity: float = None,
                       order_type: str = 'market', price: float = None) -> Dict:
        """平仓

        Args:
            symbol: 交易对
            side: long/short
            quantity: 数量，None时自动获取全部
            order_type: market/limit
            price: 限价价格
        """
        from config.settings import Config

        # 重新获取最新持仓信息确保准确
        positions = self.get_positions()
        position_found = False
        actual_size = 0
        for p in positions:
            if p['symbol'] == symbol:
                actual_size = p['size']
                position_found = True
                break

        if not position_found or actual_size == 0:
            return {'success': False, 'error': '没有持仓或持仓已平'}

        # 如果未指定数量，使用实际持仓
        if quantity is None or quantity <= 0:
            quantity = actual_size
        else:
            # 确保不超过实际持仓
            quantity = min(quantity, actual_size)

        if quantity <= 0:
            return {'success': False, 'error': '持仓数量无效'}

        # 根据交易对精度调整数量
        precision = Config.QUANTITY_PRECISION.get(symbol, 3)
        quantity = float(round(quantity, precision))

        # 确保数量不少于最小值
        min_qty = Config.MIN_QUANTITY.get(symbol, 0.001)
        if quantity < min_qty:
            quantity = min_qty

        logger.info(f"平仓: symbol={symbol}, side={side}, quantity={quantity}, order_type={order_type}")

        # 平多仓：卖出，平空仓：买入
        if side == 'long':
            if order_type == 'limit':
                return self.limit_sell(symbol, quantity, price)
            return self.market_sell(symbol, quantity)
        else:
            if order_type == 'limit':
                return self.limit_buy(symbol, quantity, price)
            return self.market_buy(symbol, quantity)

    def limit_buy(self, symbol: str, quantity: float, price: float) -> Dict:
        """限价买入/做多"""
        result = self._request('POST', '/fapi/v1/order', signed=True, params={
            'symbol': symbol,
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': quantity,
            'price': price,
            'timeInForce': 'GTC',
        })
        result['success'] = True
        return result

    def limit_sell(self, symbol: str, quantity: float, price: float) -> Dict:
        """限价卖出/做空"""
        result = self._request('POST', '/fapi/v1/order', signed=True, params={
            'symbol': symbol,
            'side': 'SELL',
            'type': 'LIMIT',
            'quantity': quantity,
            'price': price,
            'timeInForce': 'GTC',
        })
        result['success'] = True
        return result

    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """取消订单"""
        result = self._request('DELETE', '/fapi/v1/order', signed=True, params={
            'symbol': symbol,
            'orderId': order_id,
        })
        result['success'] = True
        return result

    def get_order(self, symbol: str, order_id: str) -> Dict:
        """查询订单"""
        return self._request('GET', '/fapi/v1/order', signed=True, params={
            'symbol': symbol,
            'orderId': order_id,
        })

    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """获取未完成订单"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._request('GET', '/fapi/v1/openOrders', signed=True, params=params)

    def get_my_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """获取成交记录"""
        return self._request('GET', '/fapi/v1/userTrades', signed=True, params={
            'symbol': symbol,
            'limit': limit,
        })


class APIError(Exception):
    """API 错误"""
    pass


# 全局实例
_client = None


def get_futures_client() -> FuturesClient:
    """获取期货客户端实例"""
    global _client
    if _client is None:
        _client = FuturesClient()
    return _client
