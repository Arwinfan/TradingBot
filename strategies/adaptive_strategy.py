"""Adaptive自适应策略"""
from strategies.base_strategy import BaseStrategy
from utils.logger import get_logger
from utils.indicators import calculate_adx, calculate_ema

logger = get_logger(__name__)


class AdaptiveStrategy(BaseStrategy):
    """根据市场波动率自动调整参数的策略"""

    def __init__(self, config):
        super().__init__(config)
        self.position = False
        self._prev_signal = None
        self._just_closed = False  # 修复: 防止重复平仓

    def analyze(self, df):
        if len(df) < 30:
            return None
        adx = calculate_adx(df, 14).iloc[-1]
        price = df['close'].iloc[-1]
        ema_fast = calculate_ema(df, 9).iloc[-1]
        ema_slow = calculate_ema(df, 21).iloc[-1]
        if adx < 25:
            return None
        if ema_fast > ema_slow and not self.position:
            return {'action': 'buy', 'price': price}
        if ema_fast < ema_slow and self.position:
            return {'action': 'sell', 'price': price}
        return None

    def should_close_position(self, position, df):
        if self._just_closed:
            self._just_closed = False
            return False
        if not position or position.get('amount', 0) <= 0:
            return False
        current_price = df['close'].iloc[-1]
        entry_price = position.get('avg_price', 0)
        if entry_price <= 0:
            return False
        pnl_pct = (current_price - entry_price) / entry_price
        stop_loss = float(self.config.get('stop_loss', 0.02))
        take_profit = float(self.config.get('take_profit', 0.05))
        if pnl_pct <= -stop_loss or pnl_pct >= take_profit:
            self._just_closed = True
            return True
        return False

    def on_position_opened(self):
        self.position = True

    def on_position_closed(self):
        self.position = False

    def execute(self, signal):
        pass
