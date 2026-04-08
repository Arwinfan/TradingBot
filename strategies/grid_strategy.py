"""
网格策略 - 在固定价格区间内低买高卖
"""

from typing import Dict, List
import numpy as np

from .base_strategy import BaseStrategy, Signal, SignalType
from config.strategies import GRID_STRATEGY
from utils.logger import get_logger

logger = get_logger(__name__)


class GridStrategy(BaseStrategy):
    """
    网格交易策略

    策略原理:
    - 在价格区间内设置等间距网格
    - 价格下跌到网格线时买入
    - 价格上涨到网格线时卖出
    - 每次买卖都是相同的金额

    适合震荡行情，不适合单边趋势
    """

    def __init__(self, params: Dict = None):
        """
        初始化网格策略

        Args:
            params: 策略参数
                - symbol: 交易对
                - grid_count: 网格数量 (默认10)
                - investment: 总投资金额 (USDT)
                - price_range_low: 价格区间下限
                - price_range_high: 价格区间上限
                - stop_loss: 止损比例
                - take_profit: 止盈比例
        """
        default_params = GRID_STRATEGY['default_params'].copy()
        if params:
            default_params.update(params)

        super().__init__('GridStrategy', default_params)

        self.grid_count = self.params['grid_count']
        self.investment = self.params['investment']
        self.price_range_low = self.params['price_range_low']
        self.price_range_high = self.params['price_range_high']
        self.stop_loss = self.params['stop_loss']
        self.take_profit = self.params['take_profit']

        # 网格数据
        self.grids = []
        self.grid_orders = {}  # 记录每个网格的订单
        self.last_price = 0

        # 加载保存的状态
        self._load_state()

    def _init_grids(self):
        """初始化网格"""
        ticker = self._market.get_ticker(self.symbol)
        current_price = ticker.get('last', 0)

        if self.price_range_low == 0 or self.price_range_high == 0:
            # 自动计算价格区间
            stats = self._market.get_price_stats(self.symbol, '1d', 10)
            price_change = stats.get('price_change_percent', 0)

            if self.price_range_low == 0:
                self.price_range_low = current_price * (1 - abs(price_change) / 100 - 0.05)
            if self.price_range_high == 0:
                self.price_range_high = current_price * (1 + abs(price_change) / 100 + 0.05)

        # 生成网格
        self.grids = np.linspace(self.price_range_low, self.price_range_high, self.grid_count + 2)[1:-1]
        self.last_price = current_price

        logger.info(f"网格已初始化: {self.symbol}")
        logger.info(f"价格区间: {self.price_range_low:.2f} - {self.price_range_high:.2f}")
        logger.info(f"网格数量: {len(self.grids)}")
        logger.info(f"当前价格: {current_price:.2f}")

    def _load_state(self):
        """加载状态"""
        state_data = self._data.get_strategy_state('GridStrategy')
        if state_data and state_data.get('params'):
            params = state_data['params']
            # 恢复所有参数到 self.params
            for key, value in params.items():
                if key not in ['grids', 'grid_orders', 'last_price', 'trades_today', 'wins_today', 'losses_today', 'last_trade_time']:
                    self.params[key] = value
            # 恢复 symbol
            if params.get('symbol'):
                self.symbol = params['symbol']
            # 加载网格数据
            if params.get('grids'):
                self.grids = np.array(params['grids'])
            if params.get('grid_orders'):
                self.grid_orders = params['grid_orders']
            if params.get('last_price'):
                self.last_price = params['last_price']
            # 更新所有策略参数属性
            for key in ['grid_count', 'investment', 'price_range_low', 'price_range_high', 'stop_loss', 'take_profit', 'symbol']:
                if key in self.params:
                    setattr(self, key, self.params[key])

    def _save_state(self):
        """保存状态"""
        state_params = {
            **self.params,
            'grids': self.grids.tolist() if hasattr(self.grids, 'tolist') else self.grids,
            'grid_orders': self.grid_orders,
            'last_price': self.last_price,
        }
        self._data.save_strategy_state('GridStrategy', state_params, self.status)

    def start(self):
        """启动策略"""
        self.status = 'running'
        self._save_state()
        logger.info(f"{self.name}: 策略已启动 (symbol={self.symbol})")

    def stop(self):
        """停止策略"""
        self.status = 'stopped'
        self._save_state()
        logger.info(f"{self.name}: 策略已停止")

    def update_params(self, params: Dict):
        """更新策略参数"""
        self.params.update(params)
        # 更新本地属性
        if 'symbol' in params:
            self.symbol = params['symbol']
        if 'grid_count' in params:
            self.grid_count = params['grid_count']
        if 'investment' in params:
            self.investment = params['investment']
        if 'price_range_low' in params:
            self.price_range_low = params['price_range_low']
        if 'price_range_high' in params:
            self.price_range_high = params['price_range_high']
        if 'stop_loss' in params:
            self.stop_loss = params['stop_loss']
        if 'take_profit' in params:
            self.take_profit = params['take_profit']
        # 保存状态
        self._save_state()

    def analyze(self) -> Signal:
        """
        分析市场并生成交易信号

        Returns:
            交易信号
        """
        # 初始化网格
        if not self.grids or len(self.grids) != self.grid_count:
            self._init_grids()

        ticker = self._market.get_ticker(self.symbol)
        current_price = ticker.get('last', 0)
        self.last_price = current_price

        # 检查止损/止盈
        position = self.get_position()

        # 获取持仓成本
        cost = position.get('cost', 0)
        amount = position.get('amount', 0)

        if amount > 0:
            avg_price = cost / amount if amount > 0 else 0
            price_change = (current_price - avg_price) / avg_price if avg_price > 0 else 0

            # 止损检查
            if price_change < -self.stop_loss:
                return Signal(
                    type=SignalType.SELL,
                    symbol=self.symbol,
                    price=current_price,
                    amount=amount,
                    confidence=0.9,
                    reason=f"触发止损: 价格变动 {price_change*100:.2f}%",
                )

            # 止盈检查
            if price_change > self.take_profit:
                return Signal(
                    type=SignalType.SELL,
                    symbol=self.symbol,
                    price=current_price,
                    amount=amount,
                    confidence=0.9,
                    reason=f"触发止盈: 价格变动 {price_change*100:.2f}%",
                )

        # 网格交易逻辑
        investment_per_grid = self.investment / self.grid_count

        # 找到当前价格所在的网格区间
        for i, grid_price in enumerate(self.grids):
            # 检查是否触发了网格
            if self._is_grid_triggered(i, current_price, grid_price):
                # 检查是否在网格上方 (应该买入)
                if current_price >= grid_price and self.last_price < grid_price:
                    amount = investment_per_grid / current_price
                    return Signal(
                        type=SignalType.BUY,
                        symbol=self.symbol,
                        price=current_price,
                        amount=amount,
                        confidence=0.8,
                        reason=f"网格{i+1}触发买入: 价格 {grid_price:.2f}",
                    )

                # 检查是否在网格下方 (应该卖出)
                elif current_price <= grid_price and self.last_price > grid_price:
                    # 检查是否有持仓可以卖出
                    if position['amount'] >= investment_per_grid / avg_price if avg_price > 0 else 0:
                        sell_amount = min(
                            investment_per_grid / current_price,
                            position['amount']
                        )
                        return Signal(
                            type=SignalType.SELL,
                            symbol=self.symbol,
                            price=current_price,
                            amount=sell_amount,
                            confidence=0.8,
                            reason=f"网格{i+1}触发卖出: 价格 {grid_price:.2f}",
                        )

        return Signal(
            type=SignalType.HOLD,
            symbol=self.symbol,
            price=current_price,
            amount=0,
            confidence=1.0,
            reason="价格未触發任何网格",
        )

    def _is_grid_triggered(self, grid_index: int, current_price: float,
                          grid_price: float) -> bool:
        """
        检查网格是否被触发

        Args:
            grid_index: 网格索引
            current_price: 当前价格
            grid_price: 网格价格

        Returns:
            是否触发
        """
        grid_key = f"grid_{grid_index}"

        # 首次运行，初始化网格状态
        if grid_key not in self.grid_orders:
            self.grid_orders[grid_key] = {
                'buy_triggered': False,
                'sell_triggered': False,
            }

        order = self.grid_orders[grid_key]

        # 价格上穿网格线 -> 触发卖出
        if current_price >= grid_price and self.last_price < grid_price:
            if not order['sell_triggered']:
                order['sell_triggered'] = True
                return True

        # 价格下穿网格线 -> 触发买入
        if current_price <= grid_price and self.last_price > grid_price:
            if not order['buy_triggered']:
                order['buy_triggered'] = True
                return True

        return False

    def reset(self):
        """重置策略"""
        self.grids = []
        self.grid_orders = {}
        self.last_price = 0

    def get_grid_info(self) -> Dict:
        """获取网格信息"""
        return {
            'grid_count': self.grid_count,
            'investment': self.investment,
            'investment_per_grid': self.investment / self.grid_count,
            'price_range': {
                'low': self.price_range_low,
                'high': self.price_range_high,
            },
            'grids': self.grids.tolist() if hasattr(self.grids, 'tolist') else self.grids,
            'current_price': self.last_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
        }
