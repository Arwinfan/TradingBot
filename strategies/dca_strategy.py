"""
定投策略 (DCA - Dollar Cost Averaging) - 定期定额买入
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .base_strategy import BaseStrategy, Signal, SignalType
from config.strategies import DCA_STRATEGY
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DCAState:
    """定投状态"""
    total_invested: float = 0  # 总投入
    total_amount: float = 0    # 总持有数量
    avg_price: float = 0       # 平均成本
    last_buy_time: Optional[datetime] = None
    buy_count: int = 0


class DCAStrategy(BaseStrategy):
    """
    定期定额策略 (Dollar Cost Averaging)

    策略原理:
    - 固定时间间隔投入固定金额
    - 不考虑市场价格，机械式执行
    - 长期来看可以平均买入成本

    适合长期投资，不择时
    """

    def __init__(self, params: Dict = None):
        """
        初始化定投策略

        Args:
            params: 策略参数
                - symbol: 交易对
                - investment_per_trade: 每次买入金额 (USDT)
                - interval_hours: 买入间隔 (小时)
                - target_position: 目标持仓 (USDT)
                - max_price: 最高买入价 (0 = 不限制)
                - min_price: 最低买入价 (0 = 不限制)
        """
        default_params = DCA_STRATEGY['default_params'].copy()
        if params:
            default_params.update(params)

        super().__init__('DCAStrategy', default_params)

        self.investment_per_trade = self.params['investment_per_trade']
        self.interval_hours = self.params['interval_hours']
        self.target_position = self.params['target_position']
        self.max_price = self.params['max_price']
        self.min_price = self.params['min_price']

        # 状态
        self.state = DCAState()
        self._load_state()

    def _load_state(self):
        """加载状态"""
        state_data = self._data.get_strategy_state('DCAStrategy')
        if state_data and state_data.get('params'):
            params = state_data['params']
            # 恢复所有参数到 self.params
            for key, value in params.items():
                if key not in ['total_invested', 'total_amount', 'avg_price', 'buy_count', 'last_buy_time', 'trades_today', 'wins_today', 'losses_today', 'last_trade_time']:
                    self.params[key] = value
            # 加载 DCA 特有状态
            self.state.total_invested = params.get('total_invested', 0)
            self.state.total_amount = params.get('total_amount', 0)
            self.state.avg_price = params.get('avg_price', 0)
            self.state.buy_count = params.get('buy_count', 0)
            if params.get('last_buy_time'):
                self.state.last_buy_time = datetime.fromisoformat(params['last_buy_time'])
            # 恢复 symbol
            if params.get('symbol'):
                self.symbol = params['symbol']
            # 更新所有策略参数属性
            for key in ['symbol', 'investment_per_trade', 'interval_hours', 'target_position', 'max_price', 'min_price']:
                if key in self.params:
                    setattr(self, key, self.params[key])

    def _save_state(self):
        """保存状态"""
        # 合并基本参数和 DCA 特有状态
        state_params = {
            **self.params,  # 包含 symbol 等基本参数
            'total_invested': self.state.total_invested,
            'total_amount': self.state.total_amount,
            'avg_price': self.state.avg_price,
            'buy_count': self.state.buy_count,
            'last_buy_time': self.state.last_buy_time.isoformat() if self.state.last_buy_time else None,
        }
        self._data.save_strategy_state('DCAStrategy', state_params, self.status)

    def start(self):
        """启动策略 - 保存完整状态"""
        self.status = 'running'
        self._save_state()
        logger.info(f"{self.name}: 策略已启动 (symbol={self.symbol})")

    def stop(self):
        """停止策略 - 保存完整状态"""
        self.status = 'stopped'
        self._save_state()
        logger.info(f"{self.name}: 策略已停止")

    def update_params(self, params: Dict):
        """更新策略参数"""
        self.params.update(params)
        # 更新本地属性
        if 'symbol' in params:
            self.symbol = params['symbol']
        if 'investment_per_trade' in params:
            self.investment_per_trade = params['investment_per_trade']
        if 'interval_hours' in params:
            self.interval_hours = params['interval_hours']
        if 'target_position' in params:
            self.target_position = params['target_position']
        if 'max_price' in params:
            self.max_price = params['max_price']
        if 'min_price' in params:
            self.min_price = params['min_price']
        # 保存状态
        self._save_state()

    def analyze(self) -> Signal:
        """
        分析市场并生成交易信号

        Returns:
            交易信号
        """
        ticker = self._market.get_ticker(self.symbol)
        current_price = ticker.get('last', 0)

        # 检查是否应该执行定投
        if not self._should_buy():
            return Signal(
                type=SignalType.HOLD,
                symbol=self.symbol,
                price=current_price,
                amount=0,
                confidence=1.0,
                reason=f"未到定投时间，下次定投时间: {self._next_buy_time().isoformat()}",
            )

        # 价格限制检查
        if self.max_price > 0 and current_price > self.max_price:
            return Signal(
                type=SignalType.HOLD,
                symbol=self.symbol,
                price=current_price,
                amount=0,
                confidence=1.0,
                reason=f"价格超过最高买入价: {current_price:.2f} > {self.max_price:.2f}",
            )

        if self.min_price > 0 and current_price < self.min_price:
            return Signal(
                type=SignalType.HOLD,
                symbol=self.symbol,
                price=current_price,
                amount=0,
                confidence=1.0,
                reason=f"价格低于最低买入价: {current_price:.2f} < {self.min_price:.2f}",
            )

        # 目标持仓检查
        position = self.get_position()
        current_position_value = position.get('cost', 0) + position.get('unrealized_pnl', 0)

        if current_position_value >= self.target_position:
            return Signal(
                type=SignalType.HOLD,
                symbol=self.symbol,
                price=current_price,
                amount=0,
                confidence=1.0,
                reason=f"已达目标持仓: {current_position_value:.2f} >= {self.target_position:.2f}",
            )

        # 计算买入数量
        amount = self.investment_per_trade / current_price

        return Signal(
            type=SignalType.BUY,
            symbol=self.symbol,
            price=current_price,
            amount=amount,
            confidence=1.0,
            reason=f"定时定投: 投入 {self.investment_per_trade} USDT",
        )

    def _should_buy(self) -> bool:
        """
        检查是否应该执行买入

        Returns:
            是否应该买入
        """
        # 首次运行
        if self.state.last_buy_time is None:
            return True

        # 检查间隔
        next_time = self._next_buy_time()
        return datetime.now() >= next_time

    def _next_buy_time(self) -> datetime:
        """
        计算下次买入时间

        Returns:
            下次买入时间
        """
        if self.state.last_buy_time is None:
            return datetime.now()

        return self.state.last_buy_time + timedelta(hours=self.interval_hours)

    def execute(self, signal: Signal = None) -> Dict:
        """
        执行交易信号并更新状态
        """
        if signal is None:
            signal = self.analyze()

        result = super().execute(signal)

        # 更新状态
        if signal.type == SignalType.BUY and result.get('result', {}).get('success'):
            self.state.total_invested += self.investment_per_trade
            self.state.last_buy_time = datetime.now()
            self.state.buy_count += 1

            # 更新平均成本
            ticker = self._market.get_ticker(self.symbol)
            current_price = ticker.get('last', 0)
            amount = self.investment_per_trade / current_price
            self.state.total_amount += amount
            self.state.avg_price = self.state.total_invested / self.state.total_amount if self.state.total_amount > 0 else 0

            self._save_state()

        return result

    def get_status(self) -> Dict:
        """获取策略状态"""
        base_status = super().get_status()

        # 添加DCA特有状态
        position = self.get_position()
        current_price = self._market.get_ticker(self.symbol).get('last', 0)
        current_value = self.state.total_amount * current_price

        dca_status = {
            'dca': {
                'total_invested': self.state.total_invested,
                'total_amount': self.state.total_amount,
                'avg_price': self.state.avg_price,
                'current_value': current_value,
                'profit_loss': current_value - self.state.total_invested,
                'profit_loss_percent': ((current_value / self.state.total_invested) - 1) * 100 if self.state.total_invested > 0 else 0,
                'buy_count': self.state.buy_count,
                'last_buy_time': self.state.last_buy_time.isoformat() if self.state.last_buy_time else None,
                'next_buy_time': self._next_buy_time().isoformat(),
                'investment_per_trade': self.investment_per_trade,
                'interval_hours': self.interval_hours,
                'target_position': self.target_position,
            }
        }

        return {**base_status, **dca_status}

    def get_recommended_amount(self) -> float:
        """
        获取推荐定投金额

        根据当前持仓与目标的比例，推荐本次投入金额

        Returns:
            推荐投入金额
        """
        position = self.get_position()
        current_value = position.get('cost', 0) + position.get('unrealized_pnl', 0)

        if current_value >= self.target_position:
            return 0

        # 每次投入固定金额
        return min(self.investment_per_trade, self.target_position - current_value)
