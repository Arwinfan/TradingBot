"""Scalping剥头皮策略"""
from strategies.base_strategy import BaseStrategy
from utils.logger import get_logger
from utils.indicators import calculate_ema, calculate_rsi, calculate_macd

logger = get_logger(__name__)


class ScalpingStrategy(BaseStrategy):
    """短周期剥头皮策略"""

    def __init__(self, config):
        super().__init__(config)
        self._prev_signal = None
        self._just_closed = False  # 修复: 防止重复平仓

    def analyze(self, df):
        """分析市场状态"""
        if len(df) < 26:
            return None

        price = df['close'].iloc[-1]
        ema_fast = calculate_ema(df, 9).iloc[-1]
        ema_slow = calculate_ema(df, 21).iloc[-1]
        rsi = calculate_rsi(df, 14).iloc[-1]
        macd_line, signal_line, _ = calculate_macd(df)
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]

        if ema_fast > ema_slow and rsi < 70 and current_macd > current_signal:
            return {'action': 'buy', 'price': price}
        if ema_fast < ema_slow and rsi > 30 and current_macd < current_signal:
            return {'action': 'sell', 'price': price}
        return None

    def should_close_position(self, position, df):
        """检查是否需要平仓"""
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
        stop_loss = float(self.config.get('stop_loss', 0.005))
        take_profit = float(self.config.get('take_profit', 0.01))
        if pnl_pct <= -stop_loss or pnl_pct >= take_profit:
            self._just_closed = True
            return True
        return False

    def execute(self, signal):
        pass
