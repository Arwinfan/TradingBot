"""Trend趋势策略"""
from strategies.base_strategy import BaseStrategy
from utils.logger import get_logger
from utils.indicators import calculate_macd, calculate_rsi

logger = get_logger(__name__)


class TrendStrategy(BaseStrategy):
    """基于MACD的趋势跟踪策略"""

    def __init__(self, config):
        super().__init__(config)
        self._prev_macd = None
        self._prev_signal = None
        self._just_closed = False  # 修复: 防止重复平仓

    def analyze(self, df):
        if len(df) < 26:
            return None
        macd_line, signal_line, _ = calculate_macd(df)
        rsi = calculate_rsi(df, 14).iloc[-1]
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_price = df['close'].iloc[-1]
        if self._prev_macd is None or self._prev_signal is None:
            self._prev_macd = current_macd
            self._prev_signal = current_signal
            return None
        signal = None
        if current_macd > current_signal and self._prev_macd <= self._prev_signal:
            if rsi < 70:
                signal = {'action': 'buy', 'price': current_price, 'reason': 'MACD golden cross'}
        elif current_macd < current_signal and self._prev_macd >= self._prev_signal:
            if rsi > 30:
                signal = {'action': 'sell', 'price': current_price, 'reason': 'MACD death cross'}
        self._prev_macd = current_macd
        self._prev_signal = current_signal
        return signal

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

    def execute(self, signal):
        pass
