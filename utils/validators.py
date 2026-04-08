"""
数据验证工具
"""

from typing import Dict, Tuple, Optional
from config.settings import Config


def validate_symbol(symbol: str) -> Tuple[bool, str]:
    """
    验证交易对

    Args:
        symbol: 交易对

    Returns:
        (是否有效, 错误信息)
    """
    if not symbol:
        return False, "交易对不能为空"

    if symbol not in Config.SYMBOLS:
        return False, f"不支持的交易对: {symbol}"

    return True, ""


def validate_amount(symbol: str, amount: float) -> Tuple[bool, str, Optional[float]]:
    """
    验证交易数量

    Args:
        symbol: 交易对
        amount: 交易数量

    Returns:
        (是否有效, 错误信息, 调整后的数量)
    """
    if amount <= 0:
        return False, "交易数量必须大于0", None

    precision = Config.get_precision(symbol)
    min_amount = precision['min_quantity']

    if amount < min_amount:
        return False, f"交易数量低于最小值: {min_amount}", None

    # 四舍五入到指定精度
    q = precision['quantity']
    adjusted = round(amount, q)

    return True, "", adjusted


def validate_price(symbol: str, price: float) -> Tuple[bool, str, Optional[float]]:
    """
    验证价格

    Args:
        symbol: 交易对
        price: 价格

    Returns:
        (是否有效, 错误信息, 调整后的价格)
    """
    if price <= 0:
        return False, "价格必须大于0", None

    precision = Config.get_precision(symbol)
    p = precision['price']

    # 四舍五入到指定精度
    adjusted = round(price, p)

    return True, "", adjusted


def validate_investment(amount: float) -> Tuple[bool, str]:
    """
    验证投资金额

    Args:
        amount: 投资金额

    Returns:
        (是否有效, 错误信息)
    """
    if amount <= 0:
        return False, "投资金额必须大于0"

    if amount > Config.MAX_TRADE_AMOUNT:
        return False, f"投资金额超过单笔限制: {amount} > {Config.MAX_TRADE_AMOUNT}"

    return True, ""


def validate_api_config() -> Tuple[bool, str]:
    """
    验证API配置

    Returns:
        (是否有效, 错误信息)
    """
    if not Config.API_KEY:
        return False, "API密钥未配置"

    if not Config.API_SECRET:
        return False, "API密钥密钥未配置"

    return True, ""


def format_symbol(symbol: str) -> str:
    """
    格式化交易对

    Args:
        symbol: 交易对

    Returns:
        格式化后的交易对
    """
    # 移除空格
    symbol = symbol.strip().upper()

    # 添加分隔符
    if '/' not in symbol:
        if len(symbol) > 3:
            symbol = symbol[:-3] + '/' + symbol[-3:]

    return symbol


def get_symbol_base_quote(symbol: str) -> Tuple[str, str]:
    """
    获取交易对的基础货币和计价货币

    Args:
        symbol: 交易对

    Returns:
        (基础货币, 计价货币)
    """
    parts = symbol.split('/')
    if len(parts) == 2:
        return parts[0], parts[1]
    return symbol, 'USDT'
