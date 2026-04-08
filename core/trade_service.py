"""
交易服务 - 负责订单执行和风险管理
"""

from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

from .futures_client import get_futures_client, APIError
from .market_service import get_market_service
from config.settings import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class TradeService:
    """
    交易服务类
    负责下单、撤单、持仓管理等交易操作
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
        self._market = get_market_service()
        self._positions = {}  # 本地持仓记录
        self._open_orders = {}  # 本地未完成订单记录

    @property
    def is_ready(self) -> bool:
        """检查是否已配置并可用"""
        return self._client.is_configured

    # ==================== 订单操作 ====================

    def market_buy(self, symbol: str, amount: float,
                   check_risk: bool = True) -> Dict:
        """
        市价买入

        Args:
            symbol: 交易对
            amount: 买入数量
            check_risk: 是否进行风险检查

        Returns:
            订单结果
        """
        if not self.is_ready:
            logger.warning("API未配置，返回模拟订单")
            return self._mock_order(symbol, 'buy', 'market', amount)

        try:
            # 风险检查
            if check_risk:
                risk_result = self._check_risk(symbol, amount, 'buy')
                if not risk_result['allowed']:
                    logger.warning(f"风险检查未通过: {risk_result['reason']}")
                    return {
                        'success': False,
                        'error': risk_result['reason'],
                    }

            # 获取当前价格
            ticker = self._market.get_ticker(symbol)
            price = ticker.get('last', 0)

            # 计算下单金额
            order_amount = amount
            precision = Config.get_precision(symbol)
            order_amount = self._round_amount(order_amount, precision)

            # 执行下单
            order = self._client.market_buy(symbol, order_amount)
            order = self._normalize_order(order)

            # 记录持仓
            self._update_position(symbol, 'buy', order_amount, price, order.get('id'))

            logger.info(f"市价买入成功: {symbol} {order_amount} @ {price}")
            return {
                'success': True,
                'order': order,
                'price': price,
                'amount': order_amount,
                'total': order_amount * price,
            }
        except APIError as e:
            logger.error(f"市价买入失败: {e}")
            return {
                'success': False,
                'error': str(e),
            }

    def market_sell(self, symbol: str, amount: float,
                    check_risk: bool = True) -> Dict:
        """
        市价卖出

        Args:
            symbol: 交易对
            amount: 卖出数量
            check_risk: 是否进行风险检查

        Returns:
            订单结果
        """
        if not self.is_ready:
            logger.warning("API未配置，返回模拟订单")
            return self._mock_order(symbol, 'sell', 'market', amount)

        try:
            # 检查持仓
            position = self.get_position(symbol)
            if position['amount'] < amount:
                return {
                    'success': False,
                    'error': f"持仓不足: 当前持仓 {position['amount']}, 尝试卖出 {amount}",
                }

            # 风险检查
            if check_risk:
                risk_result = self._check_risk(symbol, amount, 'sell')
                if not risk_result['allowed']:
                    logger.warning(f"风险检查未通过: {risk_result['reason']}")
                    return {
                        'success': False,
                        'error': risk_result['reason'],
                    }

            # 获取当前价格
            ticker = self._market.get_ticker(symbol)
            price = ticker.get('last', 0)

            # 计算下单数量
            precision = Config.get_precision(symbol)
            order_amount = self._round_amount(amount, precision)

            # 执行下单
            order = self._client.market_sell(symbol, order_amount)
            order = self._normalize_order(order)

            # 更新持仓
            self._update_position(symbol, 'sell', order_amount, price, order.get('id'))

            logger.info(f"市价卖出成功: {symbol} {order_amount} @ {price}")
            return {
                'success': True,
                'order': order,
                'price': price,
                'amount': order_amount,
                'total': order_amount * price,
            }
        except APIError as e:
            logger.error(f"市价卖出失败: {e}")
            return {
                'success': False,
                'error': str(e),
            }

    def limit_buy(self, symbol: str, amount: float, price: float) -> Dict:
        """
        限价买入

        Args:
            symbol: 交易对
            amount: 买入数量
            price: 买入价格

        Returns:
            订单结果
        """
        if not self.is_ready:
            return self._mock_order(symbol, 'buy', 'limit', amount, price)

        try:
            # 风险检查
            risk_result = self._check_risk(symbol, amount * price, 'buy')
            if not risk_result['allowed']:
                return {
                    'success': False,
                    'error': risk_result['reason'],
                }

            # 精度处理
            precision = Config.get_precision(symbol)
            order_amount = self._round_amount(amount, precision)
            order_price = round(price, precision['price'])

            # 下单
            order = self._client.limit_buy(symbol, order_amount, order_price)
            order = self._normalize_order(order)

            # 记录订单
            self._open_orders[order['id']] = {
                'symbol': symbol,
                'side': 'buy',
                'amount': order_amount,
                'price': order_price,
                'type': 'limit',
                'timestamp': datetime.now(),
            }

            logger.info(f"限价买入成功: {symbol} {order_amount} @ {order_price}")
            return {
                'success': True,
                'order': order,
            }
        except APIError as e:
            logger.error(f"限价买入失败: {e}")
            return {
                'success': False,
                'error': str(e),
            }

    def limit_sell(self, symbol: str, amount: float, price: float) -> Dict:
        """
        限价卖出

        Args:
            symbol: 交易对
            amount: 卖出数量
            price: 卖出价格

        Returns:
            订单结果
        """
        if not self.is_ready:
            return self._mock_order(symbol, 'sell', 'limit', amount, price)

        try:
            # 检查持仓
            position = self.get_position(symbol)
            if position['amount'] < amount:
                return {
                    'success': False,
                    'error': f"持仓不足",
                }

            # 精度处理
            precision = Config.get_precision(symbol)
            order_amount = self._round_amount(amount, precision)
            order_price = round(price, precision['price'])

            # 下单
            order = self._client.limit_sell(symbol, order_amount, order_price)
            order = self._normalize_order(order)

            # 记录订单
            self._open_orders[order['id']] = {
                'symbol': symbol,
                'side': 'sell',
                'amount': order_amount,
                'price': order_price,
                'type': 'limit',
                'timestamp': datetime.now(),
            }

            logger.info(f"限价卖出成功: {symbol} {order_amount} @ {order_price}")
            return {
                'success': True,
                'order': order,
            }
        except APIError as e:
            logger.error(f"限价卖出失败: {e}")
            return {
                'success': False,
                'error': str(e),
            }

    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """
        取消订单

        Args:
            order_id: 订单ID
            symbol: 交易对

        Returns:
            取消结果
        """
        if not self.is_ready:
            # 模拟取消
            if order_id in self._open_orders:
                del self._open_orders[order_id]
            return {'success': True, 'message': '模拟订单已取消'}

        try:
            result = self._client.cancel_order(symbol, order_id)
            if order_id in self._open_orders:
                del self._open_orders[order_id]
            logger.info(f"取消订单成功: {order_id}")
            return {'success': True, 'order': result}
        except APIError as e:
            logger.error(f"取消订单失败: {e}")
            return {'success': False, 'error': str(e)}

    def get_order(self, order_id: str, symbol: str) -> Dict:
        """
        查询订单

        Args:
            order_id: 订单ID
            symbol: 交易对

        Returns:
            订单信息
        """
        if not self.is_ready:
            return self._open_orders.get(order_id, {})

        try:
            return self._client.get_order(symbol, order_id)
        except APIError as e:
            logger.error(f"查询订单失败: {e}")
            return {}

    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """
        获取未完成订单

        Args:
            symbol: 交易对

        Returns:
            订单列表
        """
        if not self.is_ready:
            if symbol:
                return [o for o in self._open_orders.values() if o['symbol'] == symbol]
            return list(self._open_orders.values())

        try:
            return self._client.get_open_orders(symbol)
        except APIError as e:
            logger.error(f"获取未完成订单失败: {e}")
            return []

    # ==================== 持仓管理 ====================

    def get_position(self, symbol: str, force_refresh: bool = False) -> Dict:
        """
        获取持仓信息

        Args:
            symbol: 交易对
            force_refresh: 是否强制从交易所刷新（跳过缓存）

        Returns:
            持仓信息
        """
        if symbol in self._positions and not force_refresh:
            pos = self._positions[symbol]
            # 更新市值
            try:
                ticker = self._market.get_ticker(symbol)
                current_price = ticker.get('last', 0)
                pos['market_value'] = pos['amount'] * current_price
                pos['unrealized_pnl'] = pos['market_value'] - pos['cost']
                pos['unrealized_pnl_percent'] = (pos['unrealized_pnl'] / pos['cost'] * 100) if pos['cost'] > 0 else 0
            except Exception:
                pass
            return pos

        # 尝试从API获取
        if self.is_ready:
            try:
                # 期货获取持仓
                positions = self._client.get_positions()
                for pos in positions:
                    if pos['symbol'] == symbol:
                        return {
                            'symbol': symbol,
                            'amount': pos.get('size', 0),
                            'available': pos.get('size', 0),
                            'frozen': 0,
                            'avg_price': pos.get('entry_price', 0),
                            'cost': pos.get('size', 0) * pos.get('entry_price', 0),
                            'market_value': pos.get('size', 0) * pos.get('entry_price', 0),
                            'unrealized_pnl': pos.get('unrealized_pnl', 0),
                            'unrealized_pnl_percent': 0,
                        }
            except Exception as e:
                logger.warning(f"获取持仓失败: {e}")

        # 返回空持仓
        return {
            'symbol': symbol,
            'amount': 0,
            'available': 0,
            'frozen': 0,
            'avg_price': 0,
            'cost': 0,
            'market_value': 0,
            'unrealized_pnl': 0,
            'unrealized_pnl_percent': 0,
        }

    def get_all_positions(self) -> List[Dict]:
        """
        获取所有持仓

        Returns:
            持仓列表
        """
        positions = []
        for symbol in Config.SYMBOLS:
            pos = self.get_position(symbol)
            if pos['amount'] > 0:
                positions.append(pos)
        return positions

    def get_balance(self) -> Dict:
        """
        获取账户余额

        Returns:
            余额信息
        """
        if not self.is_ready:
            # 返回模拟余额
            return {
                'free': {'USDT': 10000},
                'used': {},
                'total': {'USDT': 10000},
            }

        try:
            return self._client.get_balance()
        except APIError as e:
            logger.error(f"获取余额失败: {e}")
            return {}

    def get_available_balance(self, quote: str = 'USDT') -> float:
        """
        获取可用余额

        Args:
            quote: 计价货币

        Returns:
            可用余额
        """
        balance = self.get_balance()
        return balance.get('free', {}).get(quote, 0)

    # ==================== 历史记录 ====================

    def get_trade_history(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """
        获取成交历史

        Args:
            symbol: 交易对
            limit: 数量限制

        Returns:
            成交记录列表
        """
        if not self.is_ready:
            return []

        try:
            return self._client.get_my_trades(symbol, limit)
        except APIError as e:
            logger.error(f"获取成交历史失败: {e}")
            return []

    # ==================== 内部方法 ====================

    def _check_risk(self, symbol: str, amount: float, side: str) -> Dict:
        """
        风险检查

        Args:
            symbol: 交易对
            amount: 数量或金额
            side: 买卖方向

        Returns:
            检查结果
        """
        try:
            ticker = self._market.get_ticker(symbol)
            price = ticker.get('last', 0)

            if side == 'buy':
                order_value = amount * price if price > 0 else amount

                # 检查单笔金额
                if order_value > Config.MAX_TRADE_AMOUNT:
                    return {
                        'allowed': False,
                        'reason': f"单笔金额超过限制: {order_value:.2f} > {Config.MAX_TRADE_AMOUNT}",
                    }

                # 检查总仓位
                position = self.get_position(symbol)
                new_position_value = position.get('market_value', 0) + order_value
                if new_position_value > Config.MAX_POSITION_PER_SYMBOL:
                    return {
                        'allowed': False,
                        'reason': f"持仓金额超过限制: {new_position_value:.2f} > {Config.MAX_POSITION_PER_SYMBOL}",
                    }

                # 检查可用余额
                available = self.get_available_balance('USDT')
                if order_value > available:
                    return {
                        'allowed': False,
                        'reason': f"余额不足: 需要 {order_value:.2f}, 可用 {available:.2f}",
                    }

            elif side == 'sell':
                # 检查持仓是否足够（强制从交易所刷新，避免缓存延迟）
                position = self.get_position(symbol, force_refresh=True)
                if position['amount'] < amount:
                    return {
                        'allowed': False,
                        'reason': f"持仓不足: 需要 {amount}, 持有 {position['amount']}",
                    }

            return {'allowed': True}
        except Exception as e:
            logger.warning(f"风险检查异常: {e}")
            return {'allowed': True}  # 检查异常时放行

    def _update_position(self, symbol: str, side: str, amount: float,
                        price: float, order_id: str):
        """更新持仓记录"""
        if symbol not in self._positions:
            self._positions[symbol] = {
                'symbol': symbol,
                'amount': 0,
                'available': 0,
                'frozen': 0,
                'avg_price': 0,
                'cost': 0,
                'market_value': 0,
                'unrealized_pnl': 0,
                'unrealized_pnl_percent': 0,
            }

        pos = self._positions[symbol]

        if side == 'buy':
            # 买入: 增加持仓
            old_amount = pos['amount']
            old_cost = pos['cost']
            new_amount = old_amount + amount
            new_cost = old_cost + (amount * price)

            pos['amount'] = new_amount
            pos['cost'] = new_cost
            pos['avg_price'] = new_cost / new_amount if new_amount > 0 else 0
            pos['market_value'] = new_amount * price

        elif side == 'sell':
            # 卖出: 减少持仓
            old_amount = pos['amount']
            new_amount = old_amount - amount

            if new_amount <= 0:
                # 全部卖出
                unrealized = pos['cost'] - (amount * price)
                pos['amount'] = 0
                pos['cost'] = 0
                pos['avg_price'] = 0
                pos['market_value'] = 0
                pos['unrealized_pnl'] = unrealized
            else:
                # 部分卖出
                pos['amount'] = new_amount
                pos['market_value'] = new_amount * price

    def _round_amount(self, amount: float, precision: Dict) -> float:
        """四舍五入到指定精度"""
        q = precision.get('quantity', 3)
        return round(amount, q)

    def _normalize_order(self, order: Dict) -> Dict:
        """规范化订单对象，将 orderId 转换为 id"""
        if not order:
            return order
        normalized = order.copy()
        # 将 orderId 转换为 id
        if 'orderId' in normalized and 'id' not in normalized:
            normalized['id'] = normalized['orderId']
        return normalized

    def _mock_order(self, symbol: str, side: str, order_type: str,
                    amount: float, price: float = 0) -> Dict:
        """生成模拟订单"""
        return {
            'success': True,
            'mock': True,
            'order': {
                'id': f"mock_{datetime.now().timestamp()}",
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'amount': amount,
                'price': price or self._market.get_ticker(symbol).get('last', 0),
                'status': 'closed',
                'timestamp': datetime.now().timestamp() * 1000,
            },
        }


# 全局服务实例
_service = None


def get_trade_service() -> TradeService:
    """获取全局交易服务实例"""
    global _service
    if _service is None:
        _service = TradeService()
    return _service
