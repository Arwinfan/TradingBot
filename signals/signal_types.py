"""
信号与警报类型定义
从 小龙虾交易图形助手 提取
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ==================== 信号类型 ====================

class SignalType(Enum):
    """信号类型"""
    BREAKOUT = 'breakout'       # 价格突破
    MACD_CROSS = 'macd_cross'  # MACD 金叉/死叉
    RSI_EXTREME = 'rsi_extreme'  # RSI 极值
    VOLUME_SPIKE = 'volume_spike'  # 量能放大
    CUSTOM = 'custom'           # 自定义


class OrderSide(Enum):
    """订单方向"""
    BUY = 'buy'
    SELL = 'sell'


class KLineInterval(Enum):
    """K线周期"""
    MINUTE_1 = '1m'
    MINUTE_3 = '3m'
    MINUTE_5 = '5m'
    MINUTE_15 = '15m'
    MINUTE_30 = '30m'
    HOUR_1 = '1h'
    HOUR_2 = '2h'
    HOUR_4 = '4h'
    HOUR_6 = '6h'
    HOUR_8 = '8h'
    HOUR_12 = '12h'
    DAY_1 = '1d'
    DAY_3 = '3d'
    WEEK_1 = '1w'
    MONTH_1 = '1M'


@dataclass
class TradingSignal:
    """
    交易信号
    
    Attributes:
        id: 信号唯一ID
        symbol: 交易对符号 (如 BTCUSDT)
        type: 信号类型
        side: 做多/做空
        confidence: 置信度 0-1
        entry_price: 建议入场价格
        stop_loss: 止损价格
        take_profit: 止盈价格
        reason: 信号原因说明
        interval: K线周期
        timestamp: 信号生成时间
        exchange: 交易所
    """
    id: str
    symbol: str
    type: SignalType
    side: OrderSide
    confidence: float  # 0-1
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ''
    interval: str = '1h'
    timestamp: datetime = field(default_factory=datetime.now)
    exchange: str = 'binance'
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'type': self.type.value if isinstance(self.type, Enum) else self.type,
            'side': self.side.value if isinstance(self.side, Enum) else self.side,
            'confidence': self.confidence,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'reason': self.reason,
            'interval': self.interval,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'exchange': self.exchange,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TradingSignal':
        """从字典创建"""
        type_val = data.get('type')
        if isinstance(type_val, str):
            type_val = SignalType(type_val)
        
        side_val = data.get('side')
        if isinstance(side_val, str):
            side_val = OrderSide(side_val.upper())
        
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()
        
        return cls(
            id=data['id'],
            symbol=data['symbol'],
            type=type_val,
            side=side_val,
            confidence=data['confidence'],
            entry_price=data['entry_price'],
            stop_loss=data.get('stop_loss'),
            take_profit=data.get('take_profit'),
            reason=data.get('reason', ''),
            interval=data.get('interval', '1h'),
            timestamp=timestamp,
            exchange=data.get('exchange', 'binance'),
        )


# ==================== 警报类型 ====================

class AlertLevel(Enum):
    """警报级别"""
    INFO = 'info'           # 提示
    WARNING = 'warning'   # 警告
    CRITICAL = 'critical'  # 严重


class AlertType(Enum):
    """警报类型"""
    PRICE_BREAK = 'price_break'   # 价格突破
    RISK_LIMIT = 'risk_limit'     # 风控限制
    PNL_LIMIT = 'pnl_limit'      # 盈亏限制
    SYSTEM = 'system'             # 系统
    SIGNAL = 'signal'             # 信号
    TRADING = 'trading'           # 交易


@dataclass
class Alert:
    """
    警报
    
    Attributes:
        id: 警报唯一ID
        type: 警报类型
        level: 警报级别
        title: 警报标题
        message: 警报消息
        symbol: 相关交易对 (可选)
        timestamp: 警报时间
        acknowledged: 是否已确认
    """
    id: str
    type: AlertType
    level: AlertLevel
    title: str
    message: str
    symbol: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'type': self.type.value if isinstance(self.type, Enum) else self.type,
            'level': self.level.value if isinstance(self.level, Enum) else self.level,
            'title': self.title,
            'message': self.message,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'acknowledged': self.acknowledged,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Alert':
        """从字典创建"""
        type_val = data.get('type')
        if isinstance(type_val, str):
            type_val = AlertType(type_val)
        
        level_val = data.get('level')
        if isinstance(level_val, str):
            level_val = AlertLevel(level_val.lower())
        
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()
        
        return cls(
            id=data['id'],
            type=type_val,
            level=level_val,
            title=data['title'],
            message=data['message'],
            symbol=data.get('symbol'),
            timestamp=timestamp,
            acknowledged=data.get('acknowledged', False),
        )


# ==================== 警报级别配置 ====================

ALERT_LEVEL_CONFIG = {
    AlertLevel.INFO: {
        'label': '提示',
        'color': '#3b82f6',  # 蓝色
    },
    AlertLevel.WARNING: {
        'label': '警告',
        'color': '#f97316',  # 橙色
    },
    AlertLevel.CRITICAL: {
        'label': '严重',
        'color': '#ef4444',  # 红色
    },
}


# ==================== 信号类型配置 ====================

SIGNAL_TYPE_LABELS = {
    SignalType.BREAKOUT: '突破',
    SignalType.MACD_CROSS: 'MACD交叉',
    SignalType.RSI_EXTREME: 'RSI极值',
    SignalType.VOLUME_SPIKE: '量能放大',
    SignalType.CUSTOM: '自定义',
}


# ==================== 工具函数 ====================

def generate_signal_id(symbol: str, signal_type: SignalType) -> str:
    """生成信号ID"""
    from uuid import uuid4
    return f"sig-{symbol.lower()}-{signal_type.value}-{uuid4().hex[:8]}"


def generate_alert_id(alert_type: AlertType) -> str:
    """生成警报ID"""
    from uuid import uuid4
    return f"alert-{alert_type.value}-{uuid4().hex[:8]}"
