# Routes Module
from flask import Blueprint

# 创建蓝图
dashboard_bp = Blueprint('dashboard', __name__)
trading_bp = Blueprint('trading', __name__)
settings_bp = Blueprint('settings', __name__)

# 导入路由
from . import dashboard, trading, settings
