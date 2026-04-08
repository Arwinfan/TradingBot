"""
剥头皮策略 (Scalping Strategy)
利用短期价格波动快速小额盈利
"""

from typing import Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import math

from .base_strategy import BaseStrategy, Signal, SignalType
from utils.logger import get_logger
from config.settings import Config

logger = get_logger(__name__)

# 剥头皮策略默认配置
SCALPING_STRATEGY = {
    'name': '剥头皮策略',
    'description': '利用短期波动快速小额盈利',
    'default_params': {
        'symbol': 'BTCUSDT',
        'profit_target': 0.0025,        # 盈利目标 (0.25%)
        'stop_loss': 0.001,             # 止损 (0.1%)
        'max_holding_seconds': 180,      # 最大持仓时间 (秒)
        'min_volatility': 0.0004,       # 最小波动率
        'position_size': 80,            # 仓位大小 (USDT)
        'kline_interval': '1m',         # K线周期
        'ema_fast': 9,                  # 快速EMA
        'ema_slow': 21,                 # 慢速EMA
        'rsi_period': 14,               # RSI周期
        'rsi_overbought': 72,           # RSI超买
        'rsi_oversold': 28,             # RSI超卖
        'max_daily_trades': 25,         # 每日最大交易次数
        'cooldown_seconds': 25,          # 交易间隔冷却时间
        'use_rsi_filter': True,          # 使用RSI过滤
        'use_macd_filter': True,         # 使用MACD过滤
    }
}


@dataclass
class ScalpPosition:
    """剥头皮仓位"""
    entry_price: float
    entry_time: datetime
    side: str  # 'long' or 'short'
    amount: float
    target_profit: float
    stop_loss: float


class ScalpingStrategy(BaseStrategy):
    """
    剥头皮策略

    策略特点：
    - 持仓时间短（几秒到几分钟）
    - 每次盈利目标小（0.1%-0.5%）
    - 严格止损，风险可控
    - 交易频率高
    - 多指标确认（EMA + RSI + MACD）
    """

    def __init__(self, params: Dict = None):
        """
        初始化剥头皮策略

        Args:
            params: 策略参数
        """
        default_params = SCALPING_STRATEGY['default_params'].copy()
        if params:
            default_params.update(params)

        super().__init__('ScalpingStrategy', default_params)

        # 策略参数
        self.profit_target = self.params['profit_target']
        self.stop_loss_pct = self.params['stop_loss']
        self.max_holding_seconds = self.params['max_holding_seconds']
        self.min_volatility = self.params['min_volatility']
        self.position_size = self.params['position_size']
        self.kline_interval = self.params['kline_interval']
        self.ema_fast = self.params['ema_fast']
        self.ema_slow = self.params['ema_slow']
        self.rsi_period = self.params.get('rsi_period', 14)
        self.rsi_overbought = self.params.get('rsi_overbought', 70)
        self.rsi_oversold = self.params.get('rsi_oversold', 30)
        self.max_daily_trades = self.params['max_daily_trades']
        self.cooldown_seconds = self.params['cooldown_seconds']
        self.use_rsi_filter = self.params.get('use_rsi_filter', True)
        self.use_macd_filter = self.params.get('use_macd_filter', True)

        # 运行时状态
        self.current_position: ScalpPosition = None
        self.trades_today = 0
        self.last_trade_time: datetime = None
        self.daily_reset_time: datetime = None
        self.wins_today = 0
        self.losses_today = 0

        # 从数据库加载已保存的状态
        self._load_state()

    def _load_state(self):
        """加载状态"""
        state_data = self._data.get_strategy_state('ScalpingStrategy')
        if state_data and state_data.get('params'):
            params = state_data['params']
            # 恢复所有参数到 self.params
            for key, value in params.items():
                if key not in ['trades_today', 'wins_today', 'losses_today', 'last_trade_time']:
                    self.params[key] = value
            # 恢复 symbol
            if params.get('symbol'):
                self.symbol = params['symbol']
            # 加载交易统计
            self.trades_today = params.get('trades_today', 0)
            self.wins_today = params.get('wins_today', 0)
            self.losses_today = params.get('losses_today', 0)
            if params.get('last_trade_time'):
                self.last_trade_time = datetime.fromisoformat(params['last_trade_time'])
            # 更新所有策略参数属性
            for key in ['profit_target', 'stop_loss', 'max_holding_seconds',
                       'min_volatility', 'position_size', 'kline_interval',
                       'ema_fast', 'ema_slow', 'rsi_period', 'rsi_overbought',
                       'rsi_oversold', 'max_daily_trades', 'cooldown_seconds',
                       'use_rsi_filter', 'use_macd_filter', 'symbol']:
                if key in self.params:
                    setattr(self, key, self.params[key])

    def _save_state(self):
        """保存状态"""
        state_params = {
            **self.params,
            'trades_today': self.trades_today,
            'wins_today': self.wins_today,
            'losses_today': self.losses_today,
            'last_trade_time': self.last_trade_time.isoformat() if self.last_trade_time else None,
        }
        self._data.save_strategy_state('ScalpingStrategy', state_params, self.status)

    def start(self):
        """启动策略"""
        self.status = 'running'
        self._reset_daily_stats()
        self._save_state()
        logger.info(f"{self.name}: 策略已启动 (剥头皮模式)")

    def stop(self):
        """停止策略"""
        self.status = 'stopped'
        # 平掉当前仓位
        if self.current_position:
            self._close_position(reason="策略停止")
        self._save_state()
        logger.info(f"{self.name}: 策略已停止")

    def update_params(self, params: Dict):
        """更新策略参数"""
        self.params.update(params)
        for key in ['symbol', 'profit_target', 'stop_loss', 'max_holding_seconds',
                   'min_volatility', 'position_size', 'kline_interval',
                   'ema_fast', 'ema_slow', 'rsi_period', 'rsi_overbought',
                   'rsi_oversold', 'max_daily_trades', 'cooldown_seconds',
                   'use_rsi_filter', 'use_macd_filter']:
            if key in params:
                setattr(self, key, params[key])
        self._save_state()

    def _reset_daily_stats(self):
        """重置每日统计"""
        now = datetime.now()
        if self.daily_reset_time is None or now.date() > self.daily_reset_time.date():
            self.trades_today = 0
            self.wins_today = 0
            self.losses_today = 0
            self.daily_reset_time = now

    def analyze(self) -> Signal:
        """
        分析市场并生成交易信号
        """
        # 重置每日统计
        self._reset_daily_stats()

        ticker = self._market.get_ticker(self.symbol)
        current_price = ticker.get('last', 0)

        # 检查是否需要平仓
        if self.current_position:
            close_signal = self._check_close_conditions(current_price)
            if close_signal:
                return close_signal

        # 检查是否可以开仓
        if not self.current_position:
            entry_signal = self._check_entry_conditions(current_price)
            if entry_signal:
                return entry_signal

        return Signal(
            type=SignalType.HOLD,
            symbol=self.symbol,
            price=current_price,
            amount=0,
            confidence=1.0,
            reason=self._get_hold_reason(),
        )

    def _check_close_conditions(self, current_price: float) -> Signal:
        """检查平仓条件"""
        # 同步本地持仓与交易所持仓（策略重启后持仓信息可能丢失）
        if not self.current_position:
            real_pos = self._trade.get_position(self.symbol)
            if real_pos and real_pos.get('amount', 0) > 0:
                # 从交易所同步真实持仓
                self.current_position = ScalpPosition(
                    entry_price=real_pos.get('entry_price', current_price),
                    entry_time=datetime.now(),  # 重启后无法知道精确入场时间
                    side='long' if real_pos.get('amount', 0) > 0 else 'short',
                    amount=real_pos.get('amount', 0),
                    target_profit=self.profit_target,
                    stop_loss=self.stop_loss_pct,
                )
                logger.info(f"{self.name}: 从交易所同步持仓 {self.current_position.amount} BTC")
            else:
                return None

        # 每次平仓前从交易所获取最新持仓数量，避免缓存不一致
        real_pos = self._trade.get_position(self.symbol, force_refresh=True)
        if real_pos and real_pos.get('amount', 0) > 0:
            self.current_position.amount = real_pos.get('amount', 0)
            logger.info(f"{self.name}: 同步最新持仓 {self.current_position.amount} BTC")
        else:
            # 交易所已无持仓，但策略记录还有，清除策略持仓记录
            logger.warning(f"{self.name}: 交易所无持仓但策略记录有持仓，清除记录")
            self.current_position = None
            return None

        pos = self.current_position
        price_change = (current_price - pos.entry_price) / pos.entry_price

        # 计算盈亏
        if pos.side == 'long':
            pnl_percent = price_change
        else:  # short
            pnl_percent = -price_change

        # 止盈
        if pnl_percent >= self.profit_target:
            self.wins_today += 1
            return Signal(
                type=SignalType.SELL if pos.side == 'long' else SignalType.BUY,
                symbol=self.symbol,
                price=current_price,
                amount=pos.amount,  # 使用实际持仓数量
                confidence=0.95,
                reason=f"止盈: +{pnl_percent:.2%}",
            )

        # 止损
        if pnl_percent <= -self.stop_loss_pct:
            self.losses_today += 1
            return Signal(
                type=SignalType.SELL if pos.side == 'long' else SignalType.BUY,
                symbol=self.symbol,
                price=current_price,
                amount=pos.amount,  # 使用实际持仓数量
                confidence=0.9,
                reason=f"止损: {pnl_percent:.2%}",
            )

        # 超时
        holding_seconds = (datetime.now() - pos.entry_time).total_seconds()
        if holding_seconds >= self.max_holding_seconds:
            # 根据当前盈亏决定胜负
            if pnl_percent > 0:
                self.wins_today += 1
            else:
                self.losses_today += 1
            return Signal(
                type=SignalType.SELL if pos.side == 'long' else SignalType.BUY,
                symbol=self.symbol,
                price=current_price,
                amount=pos.amount,  # 使用实际持仓数量
                confidence=0.6,
                reason=f"超时平仓: {int(holding_seconds)}秒, {pnl_percent:.2%}",
            )

        return None

    def _check_entry_conditions(self, current_price: float) -> Signal:
        """检查开仓条件"""
        # 检查交易次数限制
        if self.trades_today >= self.max_daily_trades:
            return None

        # 检查冷却时间
        if self.last_trade_time:
            seconds_since = (datetime.now() - self.last_trade_time).total_seconds()
            if seconds_since < self.cooldown_seconds:
                return None

        # 获取K线数据
        ohlcv = self.get_market_data(self.kline_interval, 50)
        if len(ohlcv) < max(self.ema_slow + 5, self.rsi_period + 5):
            return None

        closes = [k[4] for k in ohlcv]
        highs = [k[2] for k in ohlcv]
        lows = [k[3] for k in ohlcv]

        # 计算EMA
        ema_fast_val = self._calculate_ema(closes, self.ema_fast)
        ema_slow_val = self._calculate_ema(closes, self.ema_slow)

        # 计算波动率
        volatility = self._calculate_volatility(closes[-20:])
        if volatility < self.min_volatility:
            return None

        # 计算RSI
        rsi = self._calculate_rsi(closes, self.rsi_period)

        # 计算MACD
        macd_line, signal_line, histogram = self._calculate_macd(closes)

        # 多指标确认
        # 买入信号: EMA金叉 + RSI不超买 + (MACD确认)
        ema_cross_up = ema_fast_val > ema_slow_val and closes[-1] > closes[-2]
        price_momentum = closes[-1] > closes[-5]  # 短期上涨趋势

        buy_confidence = 0.7
        sell_confidence = 0.7

        if ema_cross_up and price_momentum:
            # RSI过滤
            if self.use_rsi_filter and rsi < self.rsi_overbought:
                buy_confidence += 0.15
            elif not self.use_rsi_filter:
                buy_confidence += 0.15

            # MACD过滤
            if self.use_macd_filter and histogram > 0:
                buy_confidence += 0.15
            elif not self.use_macd_filter:
                buy_confidence += 0.15

            if buy_confidence >= 0.85:
                amount = self.position_size / current_price
                precision = Config.get_precision(self.symbol)
                amount = round(amount, precision.get('quantity', 4))  # 精度处理
                return Signal(
                    type=SignalType.BUY,
                    symbol=self.symbol,
                    price=current_price,
                    amount=amount,
                    confidence=buy_confidence,
                    reason=f"买入信号: EMA金叉, RSI={rsi:.1f}, 波动率={volatility:.3%}",
                )

        # 卖出信号: EMA死叉 + RSI不超卖 + (MACD确认)
        ema_cross_down = ema_fast_val < ema_slow_val and closes[-1] < closes[-2]
        price_down_momentum = closes[-1] < closes[-5]  # 短期下跌趋势

        if ema_cross_down and price_down_momentum:
            # RSI过滤
            if self.use_rsi_filter and rsi > self.rsi_oversold:
                sell_confidence += 0.15
            elif not self.use_rsi_filter:
                sell_confidence += 0.15

            # MACD过滤
            if self.use_macd_filter and histogram < 0:
                sell_confidence += 0.15
            elif not self.use_macd_filter:
                sell_confidence += 0.15

            if sell_confidence >= 0.85:
                amount = self.position_size / current_price
                precision = Config.get_precision(self.symbol)
                amount = round(amount, precision.get('quantity', 4))  # 精度处理
                return Signal(
                    type=SignalType.SELL,
                    symbol=self.symbol,
                    price=current_price,
                    amount=amount,
                    confidence=sell_confidence,
                    reason=f"卖出信号: EMA死叉, RSI={rsi:.1f}, 波动率={volatility:.3%}",
                )

        return None

    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """计算EMA"""
        if len(prices) < period:
            return prices[-1] if prices else 0

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period

        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """计算RSI"""
        if len(prices) < period + 1:
            return 50.0

        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        if len(gains) < period:
            return 50.0

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
        """计算MACD"""
        if len(prices) < slow + signal:
            return 0, 0, 0

        ema_fast = self._calculate_ema(prices, fast)
        ema_slow = self._calculate_ema(prices, slow)

        macd_line = ema_fast - ema_slow

        # 计算信号线 (需要MACD的历史数据)
        macd_hist = []
        for i in range(slow, len(prices)):
            e_f = self._calculate_ema(prices[:i+1], fast)
            e_s = self._calculate_ema(prices[:i+1], slow)
            macd_hist.append(e_f - e_s)

        if len(macd_hist) < signal:
            signal_line = macd_line
        else:
            signal_line = self._calculate_ema(macd_hist, signal)

        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def _calculate_volatility(self, prices: List[float]) -> float:
        """计算波动率 (标准差/均值)"""
        if len(prices) < 2:
            return 0

        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std_dev = variance ** 0.5

        return std_dev / mean if mean > 0 else 0

    def _get_hold_reason(self) -> str:
        """获取持仓/观望原因"""
        reasons = []

        if self.current_position:
            holding_seconds = (datetime.now() - self.current_position.entry_time).total_seconds()
            pnl = self._calculate_pnl()
            reasons.append(f"持仓:{self.current_position.side}, {int(holding_seconds)}秒, {pnl:.2%}")
        else:
            reasons.append("等待信号")

        if self.trades_today >= self.max_daily_trades:
            reasons.append(f"今日上限({self.max_daily_trades}次)")

        if self.last_trade_time:
            seconds_since = (datetime.now() - self.last_trade_time).total_seconds()
            if seconds_since < self.cooldown_seconds:
                reasons.append(f"冷却{int(self.cooldown_seconds - seconds_since)}秒")

        return ", ".join(reasons)

    def _calculate_pnl(self) -> float:
        """计算当前持仓盈亏"""
        if not self.current_position:
            return 0

        ticker = self._market.get_ticker(self.symbol)
        current_price = ticker.get('last', 0)
        pos = self.current_position
        price_change = (current_price - pos.entry_price) / pos.entry_price

        if pos.side == 'long':
            return price_change
        else:
            return -price_change

    def _close_position(self, reason: str = "手动平仓"):
        """平仓"""
        if not self.current_position:
            return

        pos = self.current_position
        self.current_position = None
        self.trades_today += 1
        self.last_trade_time = datetime.now()
        self._save_state()

        logger.info(f"{self.name}: 平仓完成({reason}), 今日:{self.trades_today}次, 胜:{self.wins_today}/负:{self.losses_today}")

    def execute(self, signal: Signal = None) -> Dict:
        """执行交易信号"""
        if signal is None:
            signal = self.analyze()

        result = super().execute(signal)

        # 更新仓位记录
        if signal.type in [SignalType.BUY, SignalType.SELL]:
            if result.get('result', {}).get('success'):
                # 判断是开仓还是平仓
                if self.current_position is None:
                    # 开仓
                    side = 'long' if signal.type == SignalType.BUY else 'short'
                    self.current_position = ScalpPosition(
                        entry_price=signal.price,
                        entry_time=datetime.now(),
                        side=side,
                        amount=signal.amount,
                        target_profit=self.profit_target,
                        stop_loss=self.stop_loss_pct,
                    )
                    logger.info(f"{self.name}: 开仓 {side} @ {signal.price}")
                else:
                    # 平仓
                    self._close_position()

        return result

    def get_status(self) -> Dict:
        """获取策略状态"""
        base_status = super().get_status()

        # 获取市场数据
        ticker = self._market.get_ticker(self.symbol)
        current_price = ticker.get('last', 0)

        # 计算统计数据
        ohlcv = self.get_market_data(self.kline_interval, 50)
        closes = [k[4] for k in ohlcv] if ohlcv else []
        volatility = self._calculate_volatility(closes[-20:]) if len(closes) >= 20 else 0
        rsi = self._calculate_rsi(closes, self.rsi_period) if len(closes) >= self.rsi_period + 1 else 50
        macd, signal, histogram = self._calculate_macd(closes)

        # 当前持仓状态
        position_status = {}
        if self.current_position:
            pnl = self._calculate_pnl()
            holding_seconds = (datetime.now() - self.current_position.entry_time).total_seconds()
            position_status = {
                'side': self.current_position.side,
                'entry_price': self.current_position.entry_price,
                'current_price': current_price,
                'pnl_percent': pnl,
                'holding_seconds': int(holding_seconds),
                'target_profit': self.profit_target,
                'stop_loss': self.stop_loss_pct,
            }

        scalp_status = {
            'scalping': {
                'position': position_status,
                'trades_today': self.trades_today,
                'wins_today': self.wins_today,
                'losses_today': self.losses_today,
                'max_daily_trades': self.max_daily_trades,
                'volatility': volatility,
                'rsi': rsi,
                'macd': {'macd': macd, 'signal': signal, 'histogram': histogram},
                'profit_target': self.profit_target,
                'stop_loss': self.stop_loss_pct,
                'cooldown_seconds': self.cooldown_seconds,
                'params': {
                    'ema_fast': self.ema_fast,
                    'ema_slow': self.ema_slow,
                    'rsi_period': self.rsi_period,
                    'min_volatility': self.min_volatility,
                    'max_holding_seconds': self.max_holding_seconds,
                    'position_size': self.position_size,
                },
            }
        }

        return {**base_status, **scalp_status}
