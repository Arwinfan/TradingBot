"""
信号服务 - 集成信号扫描和警报到 TradingBot
"""

import asyncio
from typing import List, Optional
from datetime import datetime

from signals.signal_types import TradingSignal, Alert, AlertType, AlertLevel
from signals.signal_scanner import TechnicalSignalScanner, ScannerConfig
from signals.alert_manager import AlertManager, AlertConfig
from config.settings import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class SignalService:
    """
    信号服务
    
    整合信号扫描、警报管理和策略信号订阅
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._scanner: Optional[TechnicalSignalScanner] = None
        self._alert_manager: Optional[AlertManager] = None
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        
        # 策略信号回调
        self._strategy_callbacks: List[callable] = []
    
    @property
    def scanner(self) -> TechnicalSignalScanner:
        """获取信号扫描器"""
        if self._scanner is None:
            config = Config.get_scanner_config()
            self._scanner = TechnicalSignalScanner(config)
        return self._scanner
    
    @property
    def alert_manager(self) -> AlertManager:
        """获取警报管理器"""
        if self._alert_manager is None:
            config = Config.get_alert_config()
            self._alert_manager = AlertManager(config)
        return self._alert_manager
    
    @property
    def signals(self) -> List[TradingSignal]:
        """获取当前信号"""
        return self.scanner.signals
    
    @property
    def alerts(self) -> List[Alert]:
        """获取当前警报"""
        return self.alert_manager.alerts
    
    def register_strategy_callback(self, callback: callable):
        """注册策略信号回调"""
        self._strategy_callbacks.append(callback)
        self.scanner.register_callback(self._on_new_signals)
    
    def unregister_strategy_callback(self, callback: callable):
        """取消注册策略回调"""
        if callback in self._strategy_callbacks:
            self._strategy_callbacks.remove(callback)
    
    def _on_new_signals(self, signals: List[TradingSignal]):
        """新信号回调"""
        logger.info(f"收到 {len(signals)} 个新信号")
        
        # 发送警报
        for signal in signals:
            self.alert_manager.signal_alert(signal)
        
        # 通知策略
        for callback in self._strategy_callbacks:
            try:
                callback(signals)
            except Exception as e:
                logger.error(f"策略回调执行失败: {e}")
    
    async def start(self):
        """启动信号服务"""
        if self._running:
            logger.warning("信号服务已在运行")
            return
        
        self._running = True
        
        # 启动自动扫描
        if Config.SIGNAL_SCANNER_ENABLED:
            self._scan_task = asyncio.create_task(self.scanner.start_auto_scan())
            logger.info("信号扫描服务已启动")
        
        logger.info("信号服务已启动")
    
    def stop(self):
        """停止信号服务"""
        if not self._running:
            return
        
        self._running = False
        
        # 停止扫描
        if self._scan_task:
            self._scan_task.cancel()
            self._scan_task = None
        
        self.scanner.stop_auto_scan()
        logger.info("信号服务已停止")
    
    async def scan_now(self) -> List[TradingSignal]:
        """立即扫描"""
        signals = await self.scanner.scan_all()
        logger.info(f"手动扫描完成: {len(signals)} 个信号")
        return signals
    
    def scan_now_sync(self) -> List[TradingSignal]:
        """同步版本的立即扫描"""
        return asyncio.run(self.scan_now())
    
    # ==================== 警报快捷方法 ====================
    
    def send_price_alert(self, symbol: str, price: float, direction: str):
        """发送价格警报"""
        self.alert_manager.price_alert(symbol, price, direction)
    
    def send_risk_alert(self, message: str, symbol: str = None):
        """发送风控警报"""
        self.alert_manager.risk_alert(message, symbol)
    
    def send_pnl_alert(self, pnl: float, pnl_percent: float, symbol: str = None):
        """发送盈亏警报"""
        # 检查阈值
        if abs(pnl_percent) >= Config.ALERT_PNL_THRESHOLD:
            self.alert_manager.pnl_alert(pnl, pnl_percent, symbol)
    
    def send_system_alert(self, message: str, level: AlertLevel = AlertLevel.WARNING):
        """发送系统警报"""
        self.alert_manager.system_alert(message, level)
    
    def send_trading_alert(self, message: str, symbol: str = None, 
                          level: AlertLevel = AlertLevel.INFO):
        """发送交易警报"""
        self.alert_manager.trading_alert(message, symbol, level)
    
    # ==================== 警报管理 ====================
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认警报"""
        return self.alert_manager.acknowledge(alert_id)
    
    def acknowledge_all_alerts(self):
        """确认所有警报"""
        self.alert_manager.acknowledge_all()
    
    def get_unacknowledged_count(self) -> int:
        """获取未确认警报数"""
        return self.alert_manager.unacknowledged_count
    
    def get_critical_count(self) -> int:
        """获取严重警报数"""
        return self.alert_manager.critical_count


# 全局服务实例
_signal_service: Optional[SignalService] = None


def get_signal_service() -> SignalService:
    """获取全局信号服务"""
    global _signal_service
    if _signal_service is None:
        _signal_service = SignalService()
    return _signal_service
