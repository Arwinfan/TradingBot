"""
趋势策略 - 基于MACD和RSI的趋势跟踪
"""

from typing import Dict, List
import numpy as np

from .base_strategy import BaseStrategy, Signal, SignalType
from config.strategies import TREND_STRATEGY
from utils.logger import get_logger
from utils.indicators import calculate_macd, calculate_rsi, calculate_ema

logger = get_logger(__name__)


class TrendStrategy(BaseStrategy):
    """
    趋势跟踪策略

    策略原理:
    - 使用 MACD 判断趋势方向
    - 使用 RSI 确认超买超卖
    - 趋势确认后顺势交易

    入场条件:
    - MACD 金叉 (快线从下方穿过慢线)
    - RSI 处于正常区间 (非超买)

    出场条件:
    - MACD 死叉 (快线从上方穿过慢线)
    - RSI 进入超买区域
    - 触发止损/追踪止损
    """

    def __init__(self, params: Dict = None):
        """
        初始化趋势策略

        Args:
            params: 策略参数
                - symbol: 交易对
                - investment: 单笔投资金额 (USDT)
                - kline_interval: K线周期
                - fast_ema: 快线 EMA 周期
                - slow_ema: 慢线 EMA 周期
                - signal_ema: 信号线 EMA 周期
                - rsi_period: RSI 周期
                - rsi_overbought: RSI 超买阈值
                - rsi_oversold: RSI 超卖阈值
                - stop_loss: 止损比例
                - trailing_stop: 追踪止损比例
        """
        default_params = TREND_STRATEGY['default_params'].copy()
        if params:
            default_params.update(params)

        super().__init__('TrendStrategy', default_params)

        self.investment = self.params['investment']
        self.kline_interval = self.params['kline_interval']
        self.fast_ema = self.params['fast_ema']
        self.slow_ema = self.params['slow_ema']
        self.signal_ema = self.params['signal_ema']
        self.rsi_period = self.params['rsi_period']
        self.rsi_overbought = self.params['rsi_overbought']
        self.rsi_oversold = self.params['rsi_oversold']
        self.stop_loss = self.params['stop_loss']
        self.trailing_stop = self.params['trailing_stop']

        # 持仓状态
        self.entry_price = 0
        self.highest_price = 0
        self.position_opened = False

        # 加载保存的状态
        self._load_state()

    def _load_state(self):
        """加载状态"""
        state_data = self._data.get_strategy_state('TrendStrategy')
        if state_data and state_data.get('params'):
            params = state_data['params']
            # 恢复所有参数到 self.params
            for key, value in params.items():
                if key not in ['entry_price', 'highest_price', 'position_opened', 'trades_today', 'wins_today', 'losses_today', 'last_trade_time']:
                    self.params[key] = value
            # 恢复 symbol
            if params.get('symbol'):
                self.symbol = params['symbol']
            # 加载持仓状态
            if 'entry_price' in params:
                self.entry_price = params['entry_price']
            if 'highest_price' in params:
                self.highest_price = params['highest_price']
            if 'position_opened' in params:
                self.position_opened = params['position_opened']
            # 更新所有策略参数属性
            for key in ['symbol', 'investment', 'kline_interval', 'fast_ema', 'slow_ema', 'signal_ema', 'rsi_period', 'rsi_overbought', 'rsi_oversold', 'stop_loss', 'trailing_stop']:
                if key in self.params:
                    setattr(self, key, self.params[key])

    def _save_state(self):
        """保存状态"""
        state_params = {
            **self.params,
            'entry_price': self.entry_price,
            'highest_price': self.highest_price,
            'position_opened': self.position_opened,
        }
        self._data.save_strategy_state('TrendStrategy', state_params, self.status)

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
        if 'investment' in params:
            self.investment = params['investment']
        if 'kline_interval' in params:
            self.kline_interval = params['kline_interval']
        if 'fast_ema' in params:
            self.fast_ema = params['fast_ema']
        if 'slow_ema' in params:
            self.slow_ema = params['slow_ema']
        if 'signal_ema' in params:
            self.signal_ema = params['signal_ema']
        if 'rsi_period' in params:
            self.rsi_period = params['rsi_period']
        if 'rsi_overbought' in params:
            self.rsi_overbought = params['rsi_overbought']
        if 'rsi_oversold' in params:
            self.rsi_oversold = params['rsi_oversold']
        if 'stop_loss' in params:
            self.stop_loss = params['stop_loss']
        if 'trailing_stop' in params:
            self.trailing_stop = params['trailing_stop']
        # 保存状态
        self._save_state()

    def analyze(self) -> Signal:
        """
        分析市场并生成交易信号

        Returns:
            交易信号
        """
        # 获取K线数据
        ohlcv = self.get_market_data(self.kline_interval, 100)

        if len(ohlcv) < self.slow_ema + self.signal_ema:
            return Signal(
                type=SignalType.HOLD,
                symbol=self.symbol,
                price=0,
                amount=0,
                confidence=0,
                reason="数据不足",
            )

        # 提取价格数据
        closes = [k[4] for k in ohlcv]
        highs = [k[2] for k in ohlcv]
        lows = [k[3] for k in ohlcv]
        current_price = closes[-1]

        # 计算 MACD
        macd_line, signal_line, histogram = calculate_macd(
            closes,
            fast_period=self.fast_ema,
            slow_period=self.slow_ema,
            signal_period=self.signal_ema
        )

        # 计算 RSI
        rsi = calculate_rsi(closes, self.rsi_period)

        # 获取最新指标值
        macd_current = macd_line[-1] if len(macd_line) > 0 else 0
        macd_prev = macd_line[-2] if len(macd_line) > 1 else 0
        signal_current = signal_line[-1] if len(signal_line) > 0 else 0
        signal_prev = signal_line[-2] if len(signal_line) > 1 else 0
        histogram_current = histogram[-1] if len(histogram) > 0 else 0
        histogram_prev = histogram[-2] if len(histogram) > 1 else 0
        rsi_current = rsi[-1] if len(rsi) > 0 else 50

        # 检查持仓状态
        position = self.get_position()
        amount = position.get('amount', 0)

        # 更新追踪止损
        if amount > 0:
            if current_price > self.highest_price:
                self.highest_price = current_price

            # 追踪止损检查
            trailing_stop_price = self.highest_price * (1 - self.trailing_stop)
            if current_price < trailing_stop_price:
                return Signal(
                    type=SignalType.SELL,
                    symbol=self.symbol,
                    price=current_price,
                    amount=amount,
                    confidence=0.9,
                    reason=f"触发追踪止损: {trailing_stop_price:.2f}",
                )

            # 固定止损检查
            if self.entry_price > 0:
                stop_loss_price = self.entry_price * (1 - self.stop_loss)
                if current_price < stop_loss_price:
                    return Signal(
                        type=SignalType.SELL,
                        symbol=self.symbol,
                        price=current_price,
                        amount=amount,
                        confidence=0.9,
                        reason=f"触发止损: {stop_loss_price:.2f}",
                    )

        # ==================== 卖出信号 ====================
        if amount > 0:
            # MACD 死叉 (卖出信号)
            if macd_prev >= signal_prev and macd_current < signal_current:
                return Signal(
                    type=SignalType.SELL,
                    symbol=self.symbol,
                    price=current_price,
                    amount=amount,
                    confidence=0.8,
                    reason=f"MACD死叉, RSI={rsi_current:.1f}",
                )

            # RSI 超买 (卖出信号)
            if rsi_current > self.rsi_overbought:
                return Signal(
                    type=SignalType.SELL,
                    symbol=self.symbol,
                    price=current_price,
                    amount=amount,
                    confidence=0.7,
                    reason=f"RSI超买: {rsi_current:.1f}",
                )

        # ==================== 买入信号 ====================
        if amount == 0:
            # MACD 金叉 (买入信号)
            if macd_prev <= signal_prev and macd_current > signal_current:
                # RSI 不在超买区域
                if rsi_current < self.rsi_overbought:
                    amount = self.investment / current_price
                    return Signal(
                        type=SignalType.BUY,
                        symbol=self.symbol,
                        price=current_price,
                        amount=amount,
                        confidence=0.8,
                        reason=f"MACD金叉, RSI={rsi_current:.1f}",
                    )

            # RSI 超卖反弹 (买入信号)
            if rsi_current < self.rsi_oversold:
                # MACD 柱状体开始收缩
                if histogram_current > histogram_prev:
                    amount = self.investment / current_price
                    return Signal(
                        type=SignalType.BUY,
                        symbol=self.symbol,
                        price=current_price,
                        amount=amount,
                        confidence=0.6,
                        reason=f"RSI超卖反弹: {rsi_current:.1f}",
                    )

        return Signal(
            type=SignalType.HOLD,
            symbol=self.symbol,
            price=current_price,
            amount=0,
            confidence=1.0,
            reason=f"MACD={macd_current:.2f}, Signal={signal_current:.2f}, RSI={rsi_current:.1f}",
        )

    def execute(self, signal: Signal = None) -> Dict:
        """执行交易信号"""
        if signal is None:
            signal = self.analyze()

        result = super().execute(signal)

        # 更新持仓状态
        if signal.type == SignalType.BUY and result.get('result', {}).get('success'):
            self.entry_price = signal.price
            self.highest_price = signal.price
            self.position_opened = True

        elif signal.type == SignalType.SELL:
            self.entry_price = 0
            self.highest_price = 0
            self.position_opened = False

        return result

    def get_status(self) -> Dict:
        """获取策略状态"""
        base_status = super().get_status()

        # 获取当前指标
        ohlcv = self.get_market_data(self.kline_interval, 50)
        closes = [k[4] for k in ohlcv] if ohlcv else []

        indicators = {}
        if len(closes) > self.slow_ema:
            macd_line, signal_line, histogram = calculate_macd(
                closes, self.fast_ema, self.slow_ema, self.signal_ema
            )
            rsi = calculate_rsi(closes, self.rsi_period)
            indicators = {
                'macd': macd_line[-1] if len(macd_line) > 0 else 0,
                'signal': signal_line[-1] if len(signal_line) > 0 else 0,
                'histogram': histogram[-1] if len(histogram) > 0 else 0,
                'rsi': rsi[-1] if len(rsi) > 0 else 50,
            }

        position = self.get_position()
        current_price = closes[-1] if closes else 0

        trend_status = {
            'trend': {
                'position': {
                    'opened': self.position_opened,
                    'entry_price': self.entry_price,
                    'highest_price': self.highest_price,
                    'amount': position.get('amount', 0),
                    'unrealized_pnl': position.get('unrealized_pnl', 0),
                    'unrealized_pnl_percent': position.get('unrealized_pnl_percent', 0),
                },
                'indicators': indicators,
                'params': {
                    'fast_ema': self.fast_ema,
                    'slow_ema': self.slow_ema,
                    'signal_ema': self.signal_ema,
                    'rsi_period': self.rsi_period,
                    'rsi_overbought': self.rsi_overbought,
                    'rsi_oversold': self.rsi_oversold,
                    'stop_loss': self.stop_loss,
                    'trailing_stop': self.trailing_stop,
                },
                'current_price': current_price,
            }
        }

        return {**base_status, **trend_status}

    def reset_position(self):
        """重置持仓状态"""
        self.entry_price = 0
        self.highest_price = 0
        self.position_opened = False
