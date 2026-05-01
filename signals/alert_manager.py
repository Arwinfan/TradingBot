"""
警报管理器
从 小龙虾交易图形助手 提取并适配
"""

import json
import asyncio
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field

from .signal_types import (
    Alert, AlertType, AlertLevel,
    generate_alert_id, ALERT_LEVEL_CONFIG
)
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AlertConfig:
    """警报配置"""
    # 是否启用警报
    enabled: bool = True
    # 是否启用控制台输出
    console_output: bool = True
    # 是否保存到文件
    save_to_file: bool = True
    # 警报文件路径
    alert_file: str = 'data/alerts.json'
    # QQ Webhook URL
    qq_webhook_url: str = ''
    # 是否启用 QQ 推送
    qq_enabled: bool = False
    # QQ 推送间隔（秒）
    qq_push_interval: int = 60
    # 邮件配置
    email_enabled: bool = False
    email_smtp_host: str = ''
    email_smtp_port: int = 587
    email_from: str = ''
    email_to: str = ''
    # 警报保留天数
    retention_days: int = 30
    # 不同级别是否启用
    enable_info: bool = True
    enable_warning: bool = True
    enable_critical: bool = True


class AlertManager:
    """
    警报管理器
    
    统一管理所有警报的创建、分发、存储和推送
    """
    
    def __init__(self, config: AlertConfig = None):
        self.config = config or AlertConfig()
        self._alerts: List[Alert] = []
        self._callbacks: List[Callable[[Alert], None]] = []
        self._push_history: Dict[str, datetime] = {}  # 追踪推送历史
        self._load_alerts()
    
    @property
    def alerts(self) -> List[Alert]:
        """获取所有警报"""
        return self._alerts
    
    @property
    def unacknowledged_count(self) -> int:
        """获取未确认警报数量"""
        return len([a for a in self._alerts if not a.acknowledged])
    
    @property
    def critical_count(self) -> int:
        """获取严重级别未确认警报数量"""
        return len([
            a for a in self._alerts 
            if a.level == AlertLevel.CRITICAL and not a.acknowledged
        ])
    
    def register_callback(self, callback: Callable[[Alert], None]):
        """注册警报回调"""
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[Alert], None]):
        """取消注册回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self, alert: Alert):
        """通知所有回调"""
        for cb in self._callbacks:
            try:
                cb(alert)
            except Exception as e:
                logger.error(f"警报回调执行失败: {e}")
    
    def _load_alerts(self):
        """从文件加载警报"""
        if not self.config.save_to_file:
            return
        
        try:
            import os
            from pathlib import Path
            
            alert_path = Path(self.config.alert_file)
            if alert_path.exists():
                with open(alert_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self._alerts = [Alert.from_dict(a) for a in data]
                
                # 清理过期警报
                self._cleanup_old_alerts()
                
                logger.info(f"已加载 {len(self._alerts)} 条历史警报")
        except Exception as e:
            logger.warning(f"加载警报失败: {e}")
    
    def _save_alerts(self):
        """保存警报到文件"""
        if not self.config.save_to_file:
            return
        
        try:
            from pathlib import Path
            Path(self.config.alert_file).parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config.alert_file, 'w', encoding='utf-8') as f:
                data = [a.to_dict() for a in self._alerts]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存警报失败: {e}")
    
    def _cleanup_old_alerts(self):
        """清理过期警报"""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=self.config.retention_days)
        original_count = len(self._alerts)
        
        self._alerts = [
            a for a in self._alerts 
            if a.timestamp > cutoff or not a.acknowledged
        ]
        
        if original_count > len(self._alerts):
            logger.info(f"清理了 {original_count - len(self._alerts)} 条过期警报")
    
    # ==================== 警报创建方法 ====================
    
    def create_alert(
        self,
        title: str,
        message: str,
        alert_type: AlertType,
        level: AlertLevel,
        symbol: str = None,
        push: bool = True,
    ) -> Alert:
        """
        创建并发送警报
        
        Args:
            title: 警报标题
            message: 警报消息
            alert_type: 警报类型
            level: 警报级别
            symbol: 相关交易对 (可选)
            push: 是否推送 (默认True)
            
        Returns:
            创建的警报对象
        """
        if not self.config.enabled:
            return None
        
        # 检查级别是否启用
        if level == AlertLevel.INFO and not self.config.enable_info:
            return None
        if level == AlertLevel.WARNING and not self.config.enable_warning:
            return None
        if level == AlertLevel.CRITICAL and not self.config.enable_critical:
            return None
        
        alert = Alert(
            id=generate_alert_id(alert_type),
            type=alert_type,
            level=level,
            title=title,
            message=message,
            symbol=symbol,
            timestamp=datetime.now(),
            acknowledged=False,
        )
        
        # 添加到列表
        self._alerts.insert(0, alert)  # 最新在前
        
        # 限制列表大小
        MAX_ALERTS = 1000
        if len(self._alerts) > MAX_ALERTS:
            self._alerts = self._alerts[:MAX_ALERTS]
        
        # 保存
        self._save_alerts()
        
        # 控制台输出
        if self.config.console_output:
            self._console_output(alert)
        
        # 推送通知
        if push:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._push_alert(alert))
            except RuntimeError:
                # 无运行中的事件循环，在新线程中异步推送
                import threading
                def async_push():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self._push_alert(alert))
                        loop.close()
                    except Exception:
                        pass
                threading.Thread(target=async_push, daemon=True).start()
        
        # 通知回调
        self._notify_callbacks(alert)
        
        logger.info(f"警报: [{level.value}] {title} - {message}")
        return alert
    
    def _console_output(self, alert: Alert):
        """控制台输出"""
        level_cfg = ALERT_LEVEL_CONFIG.get(alert.level, {})
        color = level_cfg.get('color', '')
        label = level_cfg.get('label', '')
        
        symbol_str = f" [{alert.symbol}]" if alert.symbol else ""
        print(f"\n{'='*60}")
        print(f"🔔 警报 [{label}]{symbol_str}")
        print(f"   标题: {alert.title}")
        print(f"   消息: {alert.message}")
        print(f"   时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
    
    async def _push_alert(self, alert: Alert):
        """推送警报"""
        # 检查推送间隔
        alert_key = f"{alert.type.value}_{alert.level.value}"
        last_push = self._push_history.get(alert_key)
        
        if last_push:
            elapsed = (datetime.now() - last_push).total_seconds()
            min_interval = self._get_min_push_interval(alert.level)
            if elapsed < min_interval:
                logger.debug(f"跳过推送 (间隔 {elapsed:.0f}秒 < {min_interval}秒)")
                return
        
        self._push_history[alert_key] = datetime.now()
        
        # QQ 推送
        if self.config.qq_enabled and self.config.qq_webhook_url:
            await self._push_to_qq(alert)
        
        # 邮件推送
        if self.config.email_enabled:
            await self._push_to_email(alert)
    
    def _get_min_push_interval(self, level: AlertLevel) -> int:
        """获取最小推送间隔"""
        if level == AlertLevel.CRITICAL:
            return 30  # 严重警报 30 秒
        elif level == AlertLevel.WARNING:
            return 60  # 警告 60 秒
        return self.config.qq_push_interval
    
    async def _push_to_qq(self, alert: Alert):
        """推送到 QQ"""
        try:
            import httpx
            
            level_cfg = ALERT_LEVEL_CONFIG.get(alert.level, {})
            label = level_cfg.get('label', alert.level.value)
            
            content = f"""🚨 TradingBot 警报 [{label}]
            
📌 {alert.title}
📝 {alert.message}
⏰ {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"""
            
            if alert.symbol:
                content += f"\n💹 交易对: {alert.symbol}"
            
            payload = {
                'content': content,
            }
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.config.qq_webhook_url,
                    json=payload,
                    timeout=10,
                )
            
            if resp.status_code == 200:
                logger.info(f"QQ 推送成功")
            else:
                logger.warning(f"QQ 推送失败: {resp.status_code}")
                
        except Exception as e:
            logger.error(f"QQ 推送异常: {e}")
    
    async def _push_to_email(self, alert: Alert):
        """推送邮件"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.header import Header
            
            level_cfg = ALERT_LEVEL_CONFIG.get(alert.level, {})
            label = level_cfg.get('label', alert.level.value)
            
            content = f"""TradingBot 警报 [{label}]

标题: {alert.title}
消息: {alert.message}
时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"""
            
            if alert.symbol:
                content += f"\n交易对: {alert.symbol}"
            
            msg = MIMEText(content, 'plain', 'utf-8')
            msg['Subject'] = Header(f"[{label}] {alert.title}", 'utf-8')
            msg['From'] = self.config.email_from
            msg['To'] = self.config.email_to
            
            with smtplib.SMTP(self.config.email_smtp_host, self.config.email_smtp_port) as server:
                server.starttls()
                server.send_message(msg)
            
            logger.info(f"邮件推送成功")
            
        except Exception as e:
            logger.error(f"邮件推送异常: {e}")
    
    # ==================== 便捷方法 ====================
    
    def price_alert(self, symbol: str, price: float, direction: str):
        """价格警报"""
        direction_map = {'up': '突破', 'down': '跌破'}
        direction_str = direction_map.get(direction, direction)
        self.create_alert(
            title=f"{symbol} {direction_str} {price}",
            message=f"{symbol} 价格{direction_str} {price}",
            alert_type=AlertType.PRICE_BREAK,
            level=AlertLevel.WARNING,
            symbol=symbol,
        )
    
    def risk_alert(self, message: str, symbol: str = None):
        """风控警报"""
        self.create_alert(
            title="风险警报",
            message=message,
            alert_type=AlertType.RISK_LIMIT,
            level=AlertLevel.CRITICAL,
            symbol=symbol,
        )
    
    def pnl_alert(self, pnl: float, pnl_percent: float, symbol: str = None):
        """盈亏警报"""
        level = AlertLevel.CRITICAL if abs(pnl_percent) > 5 else AlertLevel.WARNING
        direction = '盈利' if pnl >= 0 else '亏损'
        self.create_alert(
            title=f"盈亏提醒: {pnl:+.2f} USDT ({pnl_percent:+.2f}%)",
            message=f"当前{direction} {pnl:+.2f} USDT ({pnl_percent:+.2f}%)",
            alert_type=AlertType.PNL_LIMIT,
            level=level,
            symbol=symbol,
        )
    
    def signal_alert(self, signal) -> Alert:
        """信号警报"""
        from .signal_types import OrderSide
        
        side_str = '做多' if signal.side == OrderSide.BUY else '做空'
        level = AlertLevel.INFO if signal.confidence < 0.7 else AlertLevel.WARNING
        
        return self.create_alert(
            title=f"交易信号: {signal.symbol} {side_str}",
            message=f"类型: {signal.type.value}, 置信度: {signal.confidence:.0%}\n"
                    f"入场: {signal.entry_price}, 止损: {signal.stop_loss}, 止盈: {signal.take_profit}\n"
                    f"原因: {signal.reason}",
            alert_type=AlertType.SIGNAL,
            level=level,
            symbol=signal.symbol,
        )
    
    def system_alert(self, message: str, level: AlertLevel = AlertLevel.WARNING):
        """系统警报"""
        self.create_alert(
            title="系统警报",
            message=message,
            alert_type=AlertType.SYSTEM,
            level=level,
        )
    
    def trading_alert(self, message: str, symbol: str = None, level: AlertLevel = AlertLevel.INFO):
        """交易警报"""
        self.create_alert(
            title="交易提醒",
            message=message,
            alert_type=AlertType.TRADING,
            level=level,
            symbol=symbol,
        )
    
    # ==================== 警报管理方法 ====================
    
    def acknowledge(self, alert_id: str) -> bool:
        """确认警报"""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                self._save_alerts()
                logger.info(f"警报已确认: {alert_id}")
                return True
        return False
    
    def acknowledge_all(self):
        """确认所有警报"""
        for alert in self._alerts:
            alert.acknowledged = True
        self._save_alerts()
        logger.info("所有警报已确认")
    
    def delete(self, alert_id: str) -> bool:
        """删除警报"""
        original_len = len(self._alerts)
        self._alerts = [a for a in self._alerts if a.id != alert_id]
        if len(self._alerts) < original_len:
            self._save_alerts()
            return True
        return False
    
    def clear(self, acknowledged: bool = True):
        """
        清除警报
        
        Args:
            acknowledged: 是否只清除已确认的 (默认True)
        """
        if acknowledged:
            self._alerts = [a for a in self._alerts if not a.acknowledged]
        else:
            self._alerts = []
        self._save_alerts()
        logger.info(f"已清除警报 (保留未确认: {acknowledged})")
    
    def get_filtered(
        self,
        level: AlertLevel = None,
        alert_type: AlertType = None,
        symbol: str = None,
        unacknowledged_only: bool = False,
    ) -> List[Alert]:
        """获取过滤后的警报"""
        result = self._alerts
        
        if level:
            result = [a for a in result if a.level == level]
        if alert_type:
            result = [a for a in result if a.type == alert_type]
        if symbol:
            result = [a for a in result if a.symbol == symbol]
        if unacknowledged_only:
            result = [a for a in result if not a.acknowledged]
        
        return result
    
    def to_dict(self) -> List[dict]:
        """导出为字典列表"""
        return [a.to_dict() for a in self._alerts]


# 全局警报管理器实例
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """获取全局警报管理器"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
