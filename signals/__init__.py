"""
信号与警报模块 - TradingBot
从 小龙虾交易图形助手 提取并适配

使用示例:
    from signals import get_signal_service, get_alert_manager
    
    # 获取服务
    signal_service = get_signal_service()
    
    # 发送警报
    signal_service.send_price_alert('BTCUSDT', 67000, 'up')
    signal_service.send_pnl_alert(15.5, 3.2, 'BTCUSDT')
    
    # 获取信号
    signals = signal_service.signals
    
    # 获取警报
    alerts = signal_service.alerts
"""

from .signal_types import (
    SignalType,
    AlertLevel,
    AlertType,
    OrderSide,
    KLineInterval,
    TradingSignal,
    Alert,
    ALERT_LEVEL_CONFIG,
    SIGNAL_TYPE_LABELS,
    generate_signal_id,
    generate_alert_id,
)
from .signal_scanner import (
    TechnicalSignalScanner,
    ScannerConfig,
    get_signal_scanner,
)
from .alert_manager import (
    AlertManager,
    AlertConfig,
    get_alert_manager,
)
from .signal_service import (
    SignalService,
    get_signal_service,
)

__all__ = [
    # 类型定义
    'SignalType',
    'AlertLevel',
    'AlertType',
    'OrderSide',
    'KLineInterval',
    'TradingSignal',
    'Alert',
    'ALERT_LEVEL_CONFIG',
    'SIGNAL_TYPE_LABELS',
    'generate_signal_id',
    'generate_alert_id',
    
    # 扫描器
    'TechnicalSignalScanner',
    'ScannerConfig',
    'get_signal_scanner',
    
    # 警报管理器
    'AlertManager',
    'AlertConfig',
    'get_alert_manager',
    
    # 信号服务
    'SignalService',
    'get_signal_service',
]
