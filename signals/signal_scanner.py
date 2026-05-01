"""
技术信号扫描引擎
从 小龙虾交易图形助手 提取并适配
"""

import asyncio
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from .signal_types import (
    TradingSignal, SignalType, OrderSide,
    generate_signal_id
)
from utils.logger import get_logger
from config.settings import Config

logger = get_logger(__name__)


@dataclass
class ScannerConfig:
    """扫描器配置"""
    # 扫描的交易对
    symbols: List[str] = None
    # K线周期
    interval: str = '1h'
    # 并发数
    concurrency: int = 2
    # 信号置信度阈值
    min_confidence: float = 0.5
    # 是否启用 MACD 信号
    enable_macd: bool = True
    # 是否启用 RSI 信号
    enable_rsi: bool = True
    # 是否启用突破信号
    enable_breakout: bool = True
    # RSI 超买阈值
    rsi_overbought: float = 70
    # RSI 超卖阈值
    rsi_oversold: float = 30
    # 扫描间隔（秒）
    scan_interval: int = 300  # 5分钟
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = Config.SYMBOLS_FUTURES


class TechnicalSignalScanner:
    """
    技术信号扫描器
    
    扫描多个交易对的技术指标，生成交易信号
    """
    
    def __init__(self, config: ScannerConfig = None):
        self.config = config or ScannerConfig()
        self._running = False
        self._last_scan_time: Optional[datetime] = None
        self._last_signals: List[TradingSignal] = []
        self._callbacks: List[Callable[[List[TradingSignal]], None]] = []
        
    @property
    def signals(self) -> List[TradingSignal]:
        """获取最近一次扫描的信号"""
        return self._last_signals
    
    @property
    def last_scan_time(self) -> Optional[datetime]:
        """获取最近扫描时间"""
        return self._last_scan_time
    
    def register_callback(self, callback: Callable[[List[TradingSignal]], None]):
        """注册信号回调"""
        self._callbacks.append(callback)
        
    def unregister_callback(self, callback: Callable[[List[TradingSignal]], None]):
        """取消注册回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self, signals: List[TradingSignal]):
        """通知所有回调"""
        for cb in self._callbacks:
            try:
                cb(signals)
            except Exception as e:
                logger.error(f"信号回调执行失败: {e}")
    
    async def scan_single(self, symbol: str) -> Optional[TradingSignal]:
        """
        扫描单个交易对
        
        Args:
            symbol: 交易对符号
            
        Returns:
            交易信号或 None
        """
        try:
            from core.futures_service import get_futures_market_service
            market = get_futures_market_service()
            
            # 获取K线数据
            ohlcv = market.get_ohlcv(symbol, self.config.interval, 100)
            if len(ohlcv) < 50:
                logger.warning(f"{symbol}: K线数据不足")
                return None
            
            closes = [k[4] for k in ohlcv]
            highs = [k[2] for k in ohlcv]
            lows = [k[3] for k in ohlcv]
            volumes = [k[5] for k in ohlcv]
            
            last_price = closes[-1]
            
            # 计算技术指标
            indicators = self._calculate_indicators(closes, highs, lows, volumes)
            
            # 生成信号
            signal = self._generate_signal(symbol, last_price, indicators)
            return signal
            
        except Exception as e:
            logger.error(f"{symbol}: 扫描失败 - {e}")
            return None
    
    def _calculate_indicators(self, closes: List[float], highs: List[float], 
                               lows: List[float], volumes: List[float]) -> Dict[str, Any]:
        """
        计算技术指标
        
        Returns:
            包含各项指标的字典
        """
        # RSI
        rsi = self._calculate_rsi(closes, 14)
        
        # MACD
        macd_line, signal_line, histogram = self._calculate_macd(closes)
        
        # EMA
        ema_fast = self._calculate_ema(closes, 9)
        ema_slow = self._calculate_ema(closes, 21)
        
        # 布林带
        upper, middle, lower = self._calculate_bollinger(closes)
        
        # 波动率
        volatility = self._calculate_volatility(closes[-20:])
        
        # 成交量比率
        avg_volume = sum(volumes[-20:]) / 20
        current_volume = volumes[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        # 趋势强度 (ADX简化版)
        adx = self._calculate_adx(closes, highs, lows)
        
        return {
            'rsi': rsi,
            'macd_line': macd_line,
            'signal_line': signal_line,
            'macd_histogram': histogram,
            'ema_fast': ema_fast,
            'ema_slow': ema_slow,
            'bollinger_upper': upper,
            'bollinger_middle': middle,
            'bollinger_lower': lower,
            'volatility': volatility,
            'volume_ratio': volume_ratio,
            'adx': adx,
        }
    
    def _generate_signal(self, symbol: str, last_price: float, 
                        indicators: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        根据技术指标生成交易信号
        """
        rsi = indicators['rsi']
        macd_hist = indicators['macd_histogram']
        macd_line = indicators['macd_line']
        signal_line = indicators['signal_line']
        ema_fast = indicators['ema_fast']
        ema_slow = indicators['ema_slow']
        adx = indicators['adx']
        volume_ratio = indicators['volume_ratio']
        
        signal_type = None
        side = None
        confidence = 0.5
        reason = []
        
        # === MACD 金叉/死叉 ===
        if self.config.enable_macd:
            # MACD 金叉 (快线从下穿越慢线)
            if macd_line > signal_line and ema_fast > ema_slow:
                prev_macd = indicators.get('_prev_macd_line', 0)
                prev_signal = indicators.get('_prev_signal_line', 0)
                if prev_macd <= prev_signal and macd_line > signal_line:
                    signal_type = SignalType.MACD_CROSS
                    side = OrderSide.BUY
                    confidence = min(0.85, 0.5 + adx / 200)
                    reason.append('MACD 金叉确认，多头趋势')
            
            # MACD 死叉 (快线从上穿越慢线)
            elif macd_line < signal_line and ema_fast < ema_slow:
                prev_macd = indicators.get('_prev_macd_line', 0)
                prev_signal = indicators.get('_prev_signal_line', 0)
                if prev_macd >= prev_signal and macd_line < signal_line:
                    signal_type = SignalType.MACD_CROSS
                    side = OrderSide.SELL
                    confidence = min(0.85, 0.5 + adx / 200)
                    reason.append('MACD 死叉确认，空头趋势')
        
        # === RSI 极值 ===
        if self.config.enable_rsi and signal_type is None:
            if rsi < self.config.rsi_oversold:
                signal_type = SignalType.RSI_EXTREME
                side = OrderSide.BUY
                confidence = min(0.8, (30 - rsi) / 50)
                reason.append(f'RSI 超卖 ({rsi:.1f})')
            elif rsi > self.config.rsi_overbought:
                signal_type = SignalType.RSI_EXTREME
                side = OrderSide.SELL
                confidence = min(0.8, (rsi - 70) / 50)
                reason.append(f'RSI 超买 ({rsi:.1f})')
        
        # === 突破信号 ===
        if self.config.enable_breakout and signal_type is None:
            upper = indicators['bollinger_upper']
            lower = indicators['bollinger_lower']
            
            # 价格突破上轨
            if last_price > upper and volume_ratio > 1.5:
                signal_type = SignalType.BREAKOUT
                side = OrderSide.BUY
                confidence = min(0.9, 0.4 + volume_ratio / 4)
                reason.append(f'突破布林上轨，量能放大 ({volume_ratio:.1f}x)')
            
            # 价格突破下轨
            elif last_price < lower and volume_ratio > 1.5:
                signal_type = SignalType.BREAKOUT
                side = OrderSide.SELL
                confidence = min(0.9, 0.4 + volume_ratio / 4)
                reason.append(f'突破布林下轨，量能放大 ({volume_ratio:.1f}x)')
        
        # 无信号
        if signal_type is None:
            return None
        
        # 计算止损止盈
        stop_loss, take_profit = self._calculate_sl_tp(
            last_price, side, indicators
        )
        
        return TradingSignal(
            id=generate_signal_id(symbol, signal_type),
            symbol=symbol,
            type=signal_type,
            side=side,
            confidence=confidence,
            entry_price=last_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason='; '.join(reason),
            interval=self.config.interval,
            timestamp=datetime.now(),
            exchange='binance',
        )
    
    def _calculate_sl_tp(self, price: float, side: OrderSide,
                         indicators: Dict[str, Any]) -> tuple:
        """
        计算止损止盈价格
        """
        volatility = indicators['volatility']
        
        if side == OrderSide.BUY:
            # 做多：止损在支撑位下方
            lower = indicators['bollinger_lower']
            stop_loss = lower * 0.99 if lower > 0 else price * 0.97
            # 止盈 2-3 倍风险
            risk = price - stop_loss
            take_profit = price + risk * 2.5
        else:
            # 做空：止损在上轨上方
            upper = indicators['bollinger_upper']
            stop_loss = upper * 1.01 if upper > 0 else price * 1.03
            # 止盈 2-3 倍风险
            risk = stop_loss - price
            take_profit = price - risk * 2.5
        
        return stop_loss, take_profit
    
    async def scan_all(self) -> List[TradingSignal]:
        """
        扫描所有配置的交易对
        
        Returns:
            生成的信号列表
        """
        signals = []
        semaphore = asyncio.Semaphore(self.config.concurrency)
        
        async def scan_with_limit(symbol: str) -> Optional[TradingSignal]:
            async with semaphore:
                return await self.scan_single(symbol)
        
        tasks = [
            scan_with_limit(symbol) 
            for symbol in self.config.symbols
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, TradingSignal):
                if result.confidence >= self.config.min_confidence:
                    signals.append(result)
            elif isinstance(result, Exception):
                logger.error(f"扫描任务异常: {result}")
        
        # 按置信度排序
        signals.sort(key=lambda s: s.confidence, reverse=True)
        
        self._last_signals = signals
        self._last_scan_time = datetime.now()
        
        logger.info(f"扫描完成: {len(signals)} 个信号")
        return signals
    
    def scan_all_sync(self) -> List[TradingSignal]:
        """同步版本的扫描"""
        return asyncio.run(self.scan_all())
    
    async def start_auto_scan(self):
        """启动自动扫描循环"""
        self._running = True
        logger.info(f"启动自动扫描: {self.config.scan_interval}秒间隔")
        
        while self._running:
            try:
                signals = await self.scan_all()
                self._notify_callbacks(signals)
            except Exception as e:
                logger.error(f"自动扫描异常: {e}")
            
            await asyncio.sleep(self.config.scan_interval)
    
    def stop_auto_scan(self):
        """停止自动扫描"""
        self._running = False
        logger.info("停止自动扫描")
    
    # ==================== 技术指标计算 ====================
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """计算 RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices: List[float], 
                        fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """计算 MACD"""
        if len(prices) < slow + signal:
            return 0.0, 0.0, 0.0
        
        def ema(data: List[float], n: int) -> float:
            k = 2 / (n + 1)
            ema_val = data[0]
            for price in data[1:]:
                ema_val = price * k + ema_val * (1 - k)
            return ema_val
        
        ema_fast = ema(prices, fast)
        ema_slow = ema(prices, slow)
        macd_line = ema_fast - ema_slow
        
        # Signal line
        macd_series = []
        for i in range(slow - 1, len(prices)):
            e = ema(prices[:i+1], fast) - ema(prices[:i+1], slow)
            macd_series.append(e)
        
        if len(macd_series) < signal:
            signal_line = macd_line
        else:
            signal_line = ema(macd_series, signal)
        
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """计算 EMA"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        k = 2 / (period + 1)
        ema_val = sum(prices[:period]) / period
        for price in prices[period:]:
            ema_val = price * k + ema_val * (1 - k)
        return ema_val
    
    def _calculate_bollinger(self, prices: List[float], 
                             period: int = 20, std_dev: int = 2) -> tuple:
        """计算布林带"""
        if len(prices) < period:
            return prices[-1], prices[-1], prices[-1]
        
        recent = prices[-period:]
        middle = sum(recent) / period
        
        variance = sum((p - middle) ** 2 for p in recent) / period
        std = variance ** 0.5
        
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        return upper, middle, lower
    
    def _calculate_volatility(self, prices: List[float]) -> float:
        """计算波动率"""
        if len(prices) < 2:
            return 0.0
        
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return variance ** 0.5
    
    def _calculate_adx(self, closes: List[float], highs: List[float], 
                       lows: List[float], period: int = 14) -> float:
        """计算 ADX (简化版)"""
        if len(closes) < period + 1:
            return 25.0
        
        # +DM 和 -DM
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(closes)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            if high_diff > low_diff and high_diff > 0:
                plus_dm.append(high_diff)
                minus_dm.append(0)
            elif low_diff > high_diff and low_diff > 0:
                plus_dm.append(0)
                minus_dm.append(low_diff)
            else:
                plus_dm.append(0)
                minus_dm.append(0)
        
        # True Range
        tr = []
        for i in range(1, len(closes)):
            tr.append(max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            ))
        
        if len(tr) < period:
            return 25.0
        
        # 平滑
        avg_tr = sum(tr[-period:]) / period
        avg_plus_dm = sum(plus_dm[-period:]) / period
        avg_minus_dm = sum(minus_dm[-period:]) / period
        
        if avg_tr == 0:
            return 25.0
        
        plus_di = (avg_plus_dm / avg_tr) * 100
        minus_di = (avg_minus_dm / avg_tr) * 100
        
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 25.0
        
        dx = abs(plus_di - minus_di) / di_sum * 100
        
        # 简化 ADX
        adx = min(100, max(0, dx))
        return adx


# 全局扫描器实例
_scanner: Optional[TechnicalSignalScanner] = None


def get_signal_scanner() -> TechnicalSignalScanner:
    """获取全局信号扫描器"""
    global _scanner
    if _scanner is None:
        _scanner = TechnicalSignalScanner()
    return _scanner
