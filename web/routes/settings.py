"""
设置路由 - 系统配置相关
"""

from flask import render_template, jsonify, request
import os

from . import settings_bp
from config.settings import Config
from config.strategies import StrategyConfig, ALL_STRATEGIES
from core.data_service import get_data_service
from core.api_client import get_client
from utils.logger import get_logger

logger = get_logger(__name__)


@settings_bp.route('/settings')
def index():
    """设置页面"""
    return render_template('settings.html')


@settings_bp.route('/api/config')
def get_config():
    """获取配置"""
    # 只返回公开配置，不暴露密钥
    return jsonify({
        'success': True,
        'config': {
            'api_configured': Config.is_configured(),
            'use_testnet': Config.USE_TESTNET,
            'symbols': Config.SYMBOLS,
            'default_symbol': Config.DEFAULT_SYMBOL,
            'max_trade_amount': Config.MAX_TRADE_AMOUNT,
            'max_position_per_symbol': Config.MAX_POSITION_PER_SYMBOL,
            'strategy_enabled': Config.STRATEGY_ENABLED,
            'strategy_interval': Config.STRATEGY_INTERVAL,
        },
    })


@settings_bp.route('/api/config', methods=['POST'])
def update_config():
    """更新配置"""
    data = request.get_json()

    # 更新配置项
    if 'USE_TESTNET' in data:
        Config.USE_TESTNET = data['USE_TESTNET']

    if 'MAX_TRADE_AMOUNT' in data:
        Config.MAX_TRADE_AMOUNT = float(data['MAX_TRADE_AMOUNT'])

    if 'MAX_POSITION_PER_SYMBOL' in data:
        Config.MAX_POSITION_PER_SYMBOL = float(data['MAX_POSITION_PER_SYMBOL'])

    if 'STRATEGY_ENABLED' in data:
        Config.STRATEGY_ENABLED = data['STRATEGY_ENABLED']

    if 'STRATEGY_INTERVAL' in data:
        Config.STRATEGY_INTERVAL = int(data['STRATEGY_INTERVAL'])

    return jsonify({
        'success': True,
        'message': '配置已更新',
    })


@settings_bp.route('/api/api-key', methods=['POST'])
def update_api_key():
    """
    更新API密钥

    请求参数:
        - api_key: API密钥
        - api_secret: API密钥
    """
    data = request.get_json()

    api_key = data.get('api_key', '').strip()
    api_secret = data.get('api_secret', '').strip()

    # 更新环境变量
    os.environ['BINANCE_API_KEY'] = api_key
    os.environ['BINANCE_API_SECRET'] = api_secret

    # 更新配置
    Config.API_KEY = api_key
    Config.API_SECRET = api_secret

    # 重置客户端
    global _client
    from core.api_client import BinanceClient
    BinanceClient._instance = None

    logger.info("API密钥已更新")

    return jsonify({
        'success': True,
        'message': 'API密钥已更新，请重启服务以生效',
    })


@settings_bp.route('/api/api-key', methods=['DELETE'])
def delete_api_key():
    """删除API密钥"""
    os.environ.pop('BINANCE_API_KEY', None)
    os.environ.pop('BINANCE_API_SECRET', None)

    Config.API_KEY = ''
    Config.API_SECRET = ''

    from core.api_client import BinanceClient
    BinanceClient._instance = None

    logger.info("API密钥已删除")

    return jsonify({
        'success': True,
        'message': 'API密钥已删除',
    })


@settings_bp.route('/api/strategies/config')
def get_strategies_config():
    """获取策略配置"""
    return jsonify({
        'success': True,
        'strategies': ALL_STRATEGIES,
    })


@settings_bp.route('/api/strategies/validate', methods=['POST'])
def validate_strategy_params():
    """验证策略参数"""
    data = request.get_json()

    strategy_type = data.get('strategy_type')
    params = data.get('params', {})

    valid, message = StrategyConfig.validate_params(strategy_type, params)

    return jsonify({
        'success': True,
        'valid': valid,
        'message': message,
    })


@settings_bp.route('/api/database/cleanup', methods=['POST'])
def cleanup_database():
    """清理数据库"""
    data = get_data_service()

    days = int(request.args.get('days', 30))
    deleted = data.clean_old_logs(days)

    return jsonify({
        'success': True,
        'deleted': deleted,
        'message': f'已清理 {deleted} 条日志',
    })


@settings_bp.route('/api/system/status')
def get_system_status():
    """获取系统状态"""
    client = get_client()

    # 检查API连接
    api_status = {
        'configured': client.is_configured,
        'testnet': client.is_testnet,
        'connected': False,
    }

    if client.is_configured:
        try:
            client.exchange.fetch_ticker('BTC/USDT')
            api_status['connected'] = True
        except Exception as e:
            api_status['error'] = str(e)

    # 数据库状态
    try:
        data = get_data_service()
        trades = data.get_trades(limit=1)
        db_status = {'connected': True, 'tables': True}
    except Exception as e:
        db_status = {'connected': False, 'error': str(e)}

    return jsonify({
        'success': True,
        'status': {
            'api': api_status,
            'database': db_status,
            'testnet_mode': Config.USE_TESTNET,
            'strategy_enabled': Config.STRATEGY_ENABLED,
        },
    })


@settings_bp.route('/api/about')
def get_about():
    """获取关于信息"""
    return jsonify({
        'success': True,
        'about': {
            'name': '币安量化交易系统',
            'version': '1.0.0',
            'description': '基于Flask的币安量化交易平台',
            'features': [
                '实时行情监控',
                '多种交易策略',
                '风险管理',
                'Web界面管理',
            ],
            'technologies': [
                'Flask',
                'CCXT',
                'SQLite',
                'Bootstrap 5',
                'Chart.js',
            ],
        },
    })
