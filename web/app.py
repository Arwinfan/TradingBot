"""
Flask 应用主文件
"""

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
import os

from config.settings import Config

# WebSocket 支持
socketio = SocketIO()

# 蓝图
from .routes.dashboard import dashboard_bp
from .routes.trading import trading_bp
from .routes.settings import settings_bp
from .routes.signals import signals_bp


def create_app():
    """
    创建Flask应用

    Returns:
        Flask应用实例
    """
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
    )

    # 配置
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'trading-system-secret-key')
    app.config['JSON_AS_ASCII'] = False
    app.config['JSON_SORT_KEYS'] = False

    # CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 注册蓝图
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(trading_bp, url_prefix='/')
    app.register_blueprint(settings_bp, url_prefix='/')
    app.register_blueprint(signals_bp, url_prefix='/')

    # WebSocket
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')

    # 错误处理
    @app.errorhandler(404)
    def not_found(e):
        return {'success': False, 'error': '页面不存在'}, 404

    @app.errorhandler(500)
    def internal_error(e):
        return {'success': False, 'error': '服务器内部错误'}, 500

    return app


def run_app():
    """运行应用"""
    from utils.logger import get_logger
    logger = get_logger(__name__)

    app = create_app()

    logger.info(f"启动Web服务: http://{Config.WEB_HOST}:{Config.WEB_PORT}")
    logger.info(f"测试网模式: {Config.USE_TESTNET}")
    logger.info(f"API已配置: {Config.is_configured()}")

    socketio.run(
        app,
        host=Config.WEB_HOST,
        port=Config.WEB_PORT,
        debug=Config.WEB_DEBUG,
        allow_unsafe_werkzeug=True,
    )
