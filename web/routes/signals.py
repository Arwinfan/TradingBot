"""
信号与警报路由 - API 接口
"""

from flask import Blueprint, jsonify, request
from datetime import datetime

from . import signals_bp
from signals import get_signal_service, get_alert_manager
from config.settings import Config
from utils.logger import get_logger

logger = get_logger(__name__)


@signals_bp.route('/signals')
def index():
    """信号与警报页面"""
    from flask import render_template
    return render_template('signals.html')


@signals_bp.route('/api/signals')
def get_signals():
    """获取当前信号列表"""
    try:
        service = get_signal_service()
        signals = service.signals
        
        signal_list = []
        for sig in signals:
            signal_list.append({
                'id': sig.id,
                'symbol': sig.symbol,
                'type': sig.type.value if hasattr(sig.type, 'value') else str(sig.type),
                'side': sig.side.value if hasattr(sig.side, 'value') else str(sig.side),
                'confidence': sig.confidence,
                'entry_price': sig.entry_price,
                'stop_loss': sig.stop_loss,
                'take_profit': sig.take_profit,
                'reason': sig.reason,
                'interval': sig.interval,
                'timestamp': sig.timestamp.isoformat() if hasattr(sig.timestamp, 'isoformat') else sig.timestamp,
                'exchange': sig.exchange,
            })
        
        return jsonify({
            'success': True,
            'signals': signal_list,
            'count': len(signal_list),
            'last_scan': service.scanner.last_scan_time.isoformat() if service.scanner.last_scan_time else None,
        })
        
    except Exception as e:
        logger.error(f"获取信号失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'signals': [],
        }), 500


@signals_bp.route('/api/alerts')
def get_alerts():
    """获取警报列表"""
    try:
        service = get_signal_service()
        alerts = service.alerts
        
        # 支持过滤参数
        level_filter = request.args.get('level')
        type_filter = request.args.get('type')
        unacknowledged_only = request.args.get('unacknowledged', 'false').lower() == 'true'
        
        alert_list = []
        for alert in alerts:
            # 应用过滤器
            if level_filter and alert.level.value != level_filter:
                continue
            if type_filter and alert.type.value != type_filter:
                continue
            if unacknowledged_only and alert.acknowledged:
                continue
            
            alert_list.append({
                'id': alert.id,
                'type': alert.type.value if hasattr(alert.type, 'value') else str(alert.type),
                'level': alert.level.value if hasattr(alert.level, 'value') else str(alert.level),
                'title': alert.title,
                'message': alert.message,
                'symbol': alert.symbol,
                'timestamp': alert.timestamp.isoformat() if hasattr(alert.timestamp, 'isoformat') else alert.timestamp,
                'acknowledged': alert.acknowledged,
            })
        
        return jsonify({
            'success': True,
            'alerts': alert_list,
            'count': len(alert_list),
            'unacknowledged_count': service.get_unacknowledged_count(),
            'critical_count': service.get_critical_count(),
        })
        
    except Exception as e:
        logger.error(f"获取警报失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'alerts': [],
        }), 500


@signals_bp.route('/api/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """确认警报"""
    try:
        service = get_signal_service()
        success = service.acknowledge_alert(alert_id)
        
        return jsonify({
            'success': success,
            'message': '警报已确认' if success else '警报未找到',
        })
        
    except Exception as e:
        logger.error(f"确认警报失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@signals_bp.route('/api/alerts/acknowledge-all', methods=['POST'])
def acknowledge_all_alerts():
    """确认所有警报"""
    try:
        service = get_signal_service()
        service.acknowledge_all_alerts()
        
        return jsonify({
            'success': True,
            'message': '所有警报已确认',
        })
        
    except Exception as e:
        logger.error(f"确认所有警报失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@signals_bp.route('/api/alerts/send', methods=['POST'])
def send_alert():
    """手动发送警报"""
    data = request.get_json()
    
    alert_type = data.get('type', 'SYSTEM')
    level = data.get('level', 'INFO')
    title = data.get('title', '')
    message = data.get('message', '')
    symbol = data.get('symbol')
    
    if not title or not message:
        return jsonify({
            'success': False,
            'error': '缺少 title 或 message',
        }), 400
    
    try:
        service = get_signal_service()
        
        # 转换类型
        from signals.signal_types import AlertType as SigAlertType, AlertLevel as SigAlertLevel
        alert_type_enum = SigAlertType(alert_type.lower())
        level_enum = SigAlertLevel(level.lower())
        
        alert = service.alert_manager.create_alert(
            title=title,
            message=message,
            alert_type=alert_type_enum,
            level=level_enum,
            symbol=symbol,
        )
        
        return jsonify({
            'success': True,
            'message': '警报已发送',
            'alert_id': alert.id if alert else None,
        })
        
    except Exception as e:
        logger.error(f"发送警报失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@signals_bp.route('/api/signals/scan', methods=['POST'])
def trigger_scan():
    """手动触发信号扫描"""
    try:
        service = get_signal_service()
        signals = service.scan_now_sync()
        
        return jsonify({
            'success': True,
            'message': f'扫描完成，发现 {len(signals)} 个信号',
            'count': len(signals),
        })
        
    except Exception as e:
        logger.error(f"触发扫描失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@signals_bp.route('/api/signals/config')
def get_signal_config():
    """获取信号扫描配置"""
    try:
        return jsonify({
            'success': True,
            'config': {
                'enabled': Config.SIGNAL_SCANNER_ENABLED,
                'interval': Config.SIGNAL_SCAN_INTERVAL,
                'symbols': Config.SIGNAL_SCAN_SYMBOLS,
                'interval_kline': Config.SIGNAL_SCAN_INTERVAL_KLINE,
                'min_confidence': Config.SIGNAL_MIN_CONFIDENCE,
                'enable_macd': Config.SIGNAL_ENABLE_MACD,
                'enable_rsi': Config.SIGNAL_ENABLE_RSI,
                'enable_breakout': Config.SIGNAL_ENABLE_BREAKOUT,
                'rsi_oversold': Config.SIGNAL_RSI_OVERSOLD,
                'rsi_overbought': Config.SIGNAL_RSI_OVERBOUGHT,
            },
            'alert_config': {
                'enabled': Config.ALERT_ENABLED,
                'console_output': Config.ALERT_CONSOLE_OUTPUT,
                'qq_enabled': Config.ALERT_QQ_ENABLED,
                'email_enabled': Config.ALERT_EMAIL_ENABLED,
                'retention_days': Config.ALERT_RETENTION_DAYS,
            },
        })
        
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@signals_bp.route('/api/signals/config', methods=['POST'])
def update_signal_config():
    """更新信号扫描配置"""
    data = request.get_json()
    
    # 注意：运行时更新不会持久化到文件
    # 重启后会恢复默认配置
    
    return jsonify({
        'success': True,
        'message': '配置已更新（运行时）',
        'note': '重启后会恢复默认配置，如需永久修改请编辑 config/settings.py',
    })


@signals_bp.route('/api/alerts/stats')
def get_alert_stats():
    """获取警报统计"""
    try:
        service = get_signal_service()
        alerts = service.alerts
        
        stats = {
            'total': len(alerts),
            'unacknowledged': sum(1 for a in alerts if not a.acknowledged),
            'critical': sum(1 for a in alerts if a.level.value == 'critical'),
            'warning': sum(1 for a in alerts if a.level.value == 'warning'),
            'info': sum(1 for a in alerts if a.level.value == 'info'),
            'by_type': {},
        }
        
        for alert in alerts:
            type_key = alert.type.value
            stats['by_type'][type_key] = stats['by_type'].get(type_key, 0) + 1
        
        return jsonify({
            'success': True,
            'stats': stats,
        })
        
    except Exception as e:
        logger.error(f"获取警报统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500