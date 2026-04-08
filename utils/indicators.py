"""
技术指标计算工具
"""

from typing import List, Tuple
import numpy as np


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """
    计算指数移动平均线 (EMA)

    Args:
        prices: 价格列表
        period: 周期

    Returns:
        EMA值列表
    """
    if len(prices) < period:
        return []

    prices = np.array(prices)
    ema = [np.mean(prices[:period])]

    multiplier = 2 / (period + 1)

    for price in prices[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])

    return ema


def calculate_sma(prices: List[float], period: int) -> List[float]:
    """
    计算简单移动平均线 (SMA)

    Args:
        prices: 价格列表
        period: 周期

    Returns:
        SMA值列表
    """
    if len(prices) < period:
        return []

    prices = np.array(prices)
    sma = []

    for i in range(period - 1, len(prices)):
        sma.append(np.mean(prices[i - period + 1:i + 1]))

    return sma


def calculate_macd(prices: List[float], fast_period: int = 12,
                   slow_period: int = 26,
                   signal_period: int = 9) -> Tuple[List[float], List[float], List[float]]:
    """
    计算 MACD 指标

    Args:
        prices: 价格列表
        fast_period: 快线周期
        slow_period: 慢线周期
        signal_period: 信号线周期

    Returns:
        (MACD线, 信号线, 柱状图)
    """
    if len(prices) < slow_period + signal_period:
        return [], [], []

    # 计算快线和慢线 EMA
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)

    # 对齐数据
    offset = slow_period - fast_period
    if offset > 0:
        fast_ema = fast_ema[offset:]

    # 计算 MACD 线
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]

    # 计算信号线 (MACD 的 EMA)
    signal_line = calculate_ema(macd_line, signal_period)

    # 计算柱状图
    macd_offset = slow_period - 1
    signal_offset = signal_period - 1

    if len(macd_line) <= signal_offset:
        return [], [], []

    histogram = []
    for i in range(signal_offset, len(macd_line)):
        idx = i - signal_offset
        if idx < len(signal_line):
            histogram.append(macd_line[i] - signal_line[idx])

    return macd_line, signal_line, histogram


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    计算相对强弱指数 (RSI)

    Args:
        prices: 价格列表
        period: 周期

    Returns:
        RSI值列表
    """
    if len(prices) < period + 1:
        return []

    prices = np.array(prices)
    deltas = np.diff(prices)

    # 分离涨跌
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    # 计算平均收益和平均损失
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    rsi = []

    if avg_loss == 0:
        rsi.append(100)
    else:
        rs = avg_gain / avg_loss
        rsi.append(100 - (100 / (1 + rs)))

    # 逐点计算
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))

    return rsi


def calculate_bollinger_bands(prices: List[float], period: int = 20,
                               std_dev: float = 2.0) -> Tuple[List[float], List[float], List[float]]:
    """
    计算布林带

    Args:
        prices: 价格列表
        period: 周期
        std_dev: 标准差倍数

    Returns:
        (中轨, 上轨, 下轨)
    """
    if len(prices) < period:
        return [], [], []

    prices = np.array(prices)
    middle = calculate_sma(prices.tolist(), period)

    # 计算标准差
    std = []
    for i in range(period - 1, len(prices)):
        std.append(np.std(prices[i - period + 1:i + 1]))

    std = np.array(std)

    upper = [m + std_dev * s for m, s in zip(middle, std)]
    lower = [m - std_dev * s for m, s in zip(middle, std)]

    return middle, upper, lower


def calculate_atr(highs: List[float], lows: List[float],
                   closes: List[float], period: int = 14) -> List[float]:
    """
    计算平均真实波幅 (ATR)

    Args:
        highs: 最高价列表
        lows: 最低价列表
        closes: 收盘价列表
        period: 周期

    Returns:
        ATR值列表
    """
    if len(highs) < period + 1:
        return []

    highs = np.array(highs)
    lows = np.array(lows)
    closes = np.array(closes)

    # 计算真实波幅
    tr = []
    tr.append(highs[1] - lows[1])  # 第一个TR

    for i in range(2, len(highs)):
        h_l = highs[i] - lows[i]
        h_c = abs(highs[i] - closes[i - 1])
        l_c = abs(lows[i] - closes[i - 1])
        tr.append(max(h_l, h_c, l_c))

    # 计算ATR
    atr = [np.mean(tr[:period])]

    for i in range(period, len(tr)):
        atr.append((atr[-1] * (period - 1) + tr[i]) / period)

    return atr


def calculate_stochastic(highs: List[float], lows: List[float],
                         closes: List[float], k_period: int = 14,
                         d_period: int = 3) -> Tuple[List[float], List[float]]:
    """
    计算随机指标 (KDJ)

    Args:
        highs: 最高价列表
        lows: 最低价列表
        closes: 收盘价列表
        k_period: K周期
        d_period: D周期

    Returns:
        (%K, %D)
    """
    if len(highs) < k_period:
        return [], []

    highs = np.array(highs)
    lows = np.array(lows)
    closes = np.array(closes)

    # 计算 %K
    k_values = []
    for i in range(k_period - 1, len(highs)):
        highest_high = np.max(highs[i - k_period + 1:i + 1])
        lowest_low = np.min(lows[i - k_period + 1:i + 1])
        current_close = closes[i]

        if highest_high == lowest_low:
            k_values.append(50)
        else:
            k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100
            k_values.append(k)

    # 计算 %D (K的SMA)
    d_values = calculate_sma(k_values, d_period)

    return k_values, d_values
