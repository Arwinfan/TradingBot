"""
配置文件 - 币安量化交易系统
请根据实际情况修改以下配置
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# ==================== 交易模式 ====================
# 现货 (spot) 或 期货 (futures)
TRADING_MODE = 'futures'  # 修改为 'futures' 使用期货

# ==================== API 配置 ====================
# 币安 API 密钥
# 现货测试网: https://testnet.binance.vision/
# 期货测试网: https://testnet.binancefuture.com/
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', 'hwIRU8DD2d8N9CjB1LUbRRTpd6XdUAMGRl1nw528JmhRPSLB90MiKNlLINFVkmzN')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', 'Z4oSHesYnOPGI6urdHqjN8wFMqRQGJwGVyozFuZLPxt83UzjGlZhClx5JA7FjXf6')

# 是否使用测试网
USE_TESTNET = True

# ==================== 代理配置 ====================
# HTTP 代理 (用于访问币安 API)
HTTP_PROXY = ''

# ==================== 交易配置 ====================
# 交易对列表 (期货格式: BTCUSDT 无斜杠)
SYMBOLS_FUTURES = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'DOTUSDT']
SYMBOLS_SPOT = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'DOT/USDT']

# 默认交易对
DEFAULT_SYMBOL_SPOT = 'BTC/USDT'
DEFAULT_SYMBOL_FUTURES = 'ETHUSDT'

# 最小交易数量 (合约)
MIN_QUANTITY = {
    'BTCUSDT': 0.001,
    'ETHUSDT': 0.01,
    'BNBUSDT': 0.1,
    'SOLUSDT': 0.01,
    'XRPUSDT': 1,
    'ADAUSDT': 1,
    'DOGEUSDT': 1,
    'DOTUSDT': 0.1,
}

# 价格精度
PRICE_PRECISION = {
    'BTCUSDT': 2,
    'ETHUSDT': 2,
    'BNBUSDT': 2,
    'SOLUSDT': 2,
    'XRPUSDT': 4,
    'ADAUSDT': 4,
    'DOGEUSDT': 5,
    'DOTUSDT': 2,
}

# 数量精度 (合约乘数) - 与交易所精度一致
QUANTITY_PRECISION = {
    'BTCUSDT': 4,  # stepSize = 0.0001
    'ETHUSDT': 3,  # stepSize = 0.001
    'BNBUSDT': 3,  # stepSize = 0.001
    'SOLUSDT': 2,  # stepSize = 0.01
    'XRPUSDT': 1,  # stepSize = 0.1
    'ADAUSDT': 1,  # stepSize = 0.1
    'DOGEUSDT': 0,  # stepSize = 1
    'DOTUSDT': 2,  # stepSize = 0.01
}

# ==================== 风险管理 ====================
# 单笔交易最大金额 (USDT)
MAX_TRADE_AMOUNT = 1000

# 单个交易对最大持仓 (USDT)
MAX_POSITION_PER_SYMBOL = 5000

# 总仓位上限 (USDT)
MAX_TOTAL_POSITION = 10000

# 最大杠杆倍数 (合约交易)
MAX_LEVERAGE = 10

# ==================== 数据库配置 ====================
DATABASE_PATH = BASE_DIR / 'data' / 'trading.db'
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# ==================== 日志配置 ====================
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = LOG_DIR / 'trading.log'

# ==================== Web 服务配置 ====================
WEB_HOST = '0.0.0.0'
WEB_PORT = 80
WEB_DEBUG = True

# ==================== 策略配置 ====================
STRATEGY_INTERVAL = 60  # 策略执行间隔 (秒)
STRATEGY_ENABLED = True  # 是否启用策略自动执行

# ==================== K线周期配置 ====================
KLINE_INTERVALS = {
    '1m': '1分钟',
    '5m': '5分钟',
    '15m': '15分钟',
    '1h': '1小时',
    '4h': '4小时',
    '1d': '1天',
}

DEFAULT_KLINE_INTERVAL = '1h'  # 默认K线周期

# ==================== 信号扫描配置 ====================
SIGNAL_SCANNER_ENABLED = True  # 是否启用信号扫描
SIGNAL_SCAN_INTERVAL = 300     # 扫描间隔 (秒, 默认5分钟)
SIGNAL_SCAN_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']  # 扫描的交易对
SIGNAL_SCAN_INTERVAL_KLINE = '1h'  # 扫描使用的K线周期
SIGNAL_MIN_CONFIDENCE = 0.5    # 信号最小置信度
SIGNAL_ENABLE_MACD = True       # 启用 MACD 信号
SIGNAL_ENABLE_RSI = True       # 启用 RSI 信号
SIGNAL_ENABLE_BREAKOUT = True  # 启用突破信号
SIGNAL_RSI_OVERSOLD = 30       # RSI 超卖阈值
SIGNAL_RSI_OVERBOUGHT = 70     # RSI 超买阈值
SIGNAL_SCAN_CONCURRENCY = 2    # 扫描并发数

# ==================== 警报配置 ====================
ALERT_ENABLED = True            # 是否启用警报
ALERT_CONSOLE_OUTPUT = True    # 控制台输出警报
ALERT_SAVE_TO_FILE = True      # 保存警报到文件
ALERT_FILE_PATH = BASE_DIR / 'data' / 'alerts.json'
ALERT_RETENTION_DAYS = 30       # 警报保留天数

# QQ Webhook 推送配置
ALERT_QQ_ENABLED = False       # 是否启用 QQ 推送
ALERT_QQ_WEBHOOK_URL = os.getenv('ALERT_QQ_WEBHOOK_URL', '')  # QQ Webhook URL
ALERT_QQ_PUSH_INTERVAL = 60    # QQ 推送间隔 (秒)

# 邮件推送配置
ALERT_EMAIL_ENABLED = False     # 是否启用邮件推送
ALERT_EMAIL_SMTP_HOST = 'smtp.gmail.com'
ALERT_EMAIL_SMTP_PORT = 587
ALERT_EMAIL_FROM = os.getenv('ALERT_EMAIL_FROM', '')
ALERT_EMAIL_TO = os.getenv('ALERT_EMAIL_TO', '')

# 警报级别开关
ALERT_ENABLE_INFO = True        # 提示级警报
ALERT_ENABLE_WARNING = True     # 警告级警报
ALERT_ENABLE_CRITICAL = True   # 严重级警报

# 警报触发阈值
ALERT_PNL_THRESHOLD = 5.0       # 盈亏警报阈值 (%)
ALERT_POSITION_RISK_THRESHOLD = 80.0  # 仓位风险阈值 (%)

# ==================== 邮件/通知配置 (可选) ====================
NOTIFICATION_ENABLED = False
EMAIL_SMTP_HOST = 'smtp.gmail.com'
EMAIL_SMTP_PORT = 587
EMAIL_FROM = ''
EMAIL_TO = ''


class Config:
    """配置类 - 提供统一的配置访问"""

    # 交易模式
    TRADING_MODE = TRADING_MODE

    # API配置
    API_KEY = BINANCE_API_KEY
    API_SECRET = BINANCE_API_SECRET
    USE_TESTNET = USE_TESTNET
    HTTP_PROXY = HTTP_PROXY

    # 交易配置 (根据模式选择)
    SYMBOLS = SYMBOLS_FUTURES if TRADING_MODE == 'futures' else SYMBOLS_SPOT
    DEFAULT_SYMBOL = DEFAULT_SYMBOL_FUTURES if TRADING_MODE == 'futures' else DEFAULT_SYMBOL_SPOT
    MIN_QUANTITY = MIN_QUANTITY
    PRICE_PRECISION = PRICE_PRECISION
    QUANTITY_PRECISION = QUANTITY_PRECISION

    # 风险管理
    MAX_TRADE_AMOUNT = MAX_TRADE_AMOUNT
    MAX_POSITION_PER_SYMBOL = MAX_POSITION_PER_SYMBOL
    MAX_TOTAL_POSITION = MAX_TOTAL_POSITION
    MAX_LEVERAGE = MAX_LEVERAGE

    # 数据库
    DATABASE_PATH = DATABASE_PATH
    DATABASE_URL = f'sqlite:///{DATABASE_PATH}'

    # 日志
    LOG_LEVEL = LOG_LEVEL
    LOG_FILE = str(LOG_FILE)

    # Web服务
    WEB_HOST = WEB_HOST
    WEB_PORT = WEB_PORT
    WEB_DEBUG = WEB_DEBUG

    # 策略
    STRATEGY_INTERVAL = STRATEGY_INTERVAL
    STRATEGY_ENABLED = STRATEGY_ENABLED

    # 信号扫描
    SIGNAL_SCANNER_ENABLED = SIGNAL_SCANNER_ENABLED
    SIGNAL_SCAN_INTERVAL = SIGNAL_SCAN_INTERVAL
    SIGNAL_SCAN_SYMBOLS = SIGNAL_SCAN_SYMBOLS
    SIGNAL_SCAN_INTERVAL_KLINE = SIGNAL_SCAN_INTERVAL_KLINE
    SIGNAL_MIN_CONFIDENCE = SIGNAL_MIN_CONFIDENCE
    SIGNAL_ENABLE_MACD = SIGNAL_ENABLE_MACD
    SIGNAL_ENABLE_RSI = SIGNAL_ENABLE_RSI
    SIGNAL_ENABLE_BREAKOUT = SIGNAL_ENABLE_BREAKOUT
    SIGNAL_RSI_OVERSOLD = SIGNAL_RSI_OVERSOLD
    SIGNAL_RSI_OVERBOUGHT = SIGNAL_RSI_OVERBOUGHT
    SIGNAL_SCAN_CONCURRENCY = SIGNAL_SCAN_CONCURRENCY

    # 警报
    ALERT_ENABLED = ALERT_ENABLED
    ALERT_CONSOLE_OUTPUT = ALERT_CONSOLE_OUTPUT
    ALERT_SAVE_TO_FILE = ALERT_SAVE_TO_FILE
    ALERT_FILE_PATH = ALERT_FILE_PATH
    ALERT_RETENTION_DAYS = ALERT_RETENTION_DAYS
    ALERT_QQ_ENABLED = ALERT_QQ_ENABLED
    ALERT_QQ_WEBHOOK_URL = ALERT_QQ_WEBHOOK_URL
    ALERT_QQ_PUSH_INTERVAL = ALERT_QQ_PUSH_INTERVAL
    ALERT_EMAIL_ENABLED = ALERT_EMAIL_ENABLED
    ALERT_EMAIL_SMTP_HOST = ALERT_EMAIL_SMTP_HOST
    ALERT_EMAIL_SMTP_PORT = ALERT_EMAIL_SMTP_PORT
    ALERT_EMAIL_FROM = ALERT_EMAIL_FROM
    ALERT_EMAIL_TO = ALERT_EMAIL_TO
    ALERT_ENABLE_INFO = ALERT_ENABLE_INFO
    ALERT_ENABLE_WARNING = ALERT_ENABLE_WARNING
    ALERT_ENABLE_CRITICAL = ALERT_ENABLE_CRITICAL
    ALERT_PNL_THRESHOLD = ALERT_PNL_THRESHOLD
    ALERT_POSITION_RISK_THRESHOLD = ALERT_POSITION_RISK_THRESHOLD

    @classmethod
    def is_configured(cls):
        """检查是否已配置API密钥"""
        return bool(cls.API_KEY and cls.API_SECRET)

    @classmethod
    def validate_symbol(cls, symbol):
        """验证交易对是否有效"""
        return symbol in cls.SYMBOLS

    @classmethod
    def get_precision(cls, symbol):
        """获取交易对的精度配置"""
        return {
            'price': cls.PRICE_PRECISION.get(symbol, 2),
            'quantity': cls.QUANTITY_PRECISION.get(symbol, 3),
            'min_quantity': cls.MIN_QUANTITY.get(symbol, 0.001),
        }

    @classmethod
    def is_futures(cls):
        """是否为期货模式"""
        return cls.TRADING_MODE == 'futures'

    @classmethod
    def get_symbol_format(cls, symbol):
        """获取CCXT格式的交易对"""
        if cls.TRADING_MODE == 'futures':
            # 期货格式: BTCUSDT
            return symbol.upper()
        else:
            # 现货格式: BTC/USDT
            base = symbol[:-4]
            quote = symbol[-4:]
            return f"{base}/{quote}"
    
    @classmethod
    def get_alert_config(cls):
        """获取警报配置"""
        from signals.alert_manager import AlertConfig
        return AlertConfig(
            enabled=cls.ALERT_ENABLED,
            console_output=cls.ALERT_CONSOLE_OUTPUT,
            save_to_file=cls.ALERT_SAVE_TO_FILE,
            alert_file=str(cls.ALERT_FILE_PATH),
            retention_days=cls.ALERT_RETENTION_DAYS,
            qq_enabled=cls.ALERT_QQ_ENABLED,
            qq_webhook_url=cls.ALERT_QQ_WEBHOOK_URL,
            qq_push_interval=cls.ALERT_QQ_PUSH_INTERVAL,
            email_enabled=cls.ALERT_EMAIL_ENABLED,
            email_smtp_host=cls.ALERT_EMAIL_SMTP_HOST,
            email_smtp_port=cls.ALERT_EMAIL_SMTP_PORT,
            email_from=cls.ALERT_EMAIL_FROM,
            email_to=cls.ALERT_EMAIL_TO,
            enable_info=cls.ALERT_ENABLE_INFO,
            enable_warning=cls.ALERT_ENABLE_WARNING,
            enable_critical=cls.ALERT_ENABLE_CRITICAL,
        )
    
    @classmethod
    def get_scanner_config(cls):
        """获取信号扫描器配置"""
        from signals.signal_scanner import ScannerConfig
        return ScannerConfig(
            symbols=cls.SIGNAL_SCAN_SYMBOLS,
            interval=cls.SIGNAL_SCAN_INTERVAL_KLINE,
            concurrency=cls.SIGNAL_SCAN_CONCURRENCY,
            min_confidence=cls.SIGNAL_MIN_CONFIDENCE,
            enable_macd=cls.SIGNAL_ENABLE_MACD,
            enable_rsi=cls.SIGNAL_ENABLE_RSI,
            enable_breakout=cls.SIGNAL_ENABLE_BREAKOUT,
            rsi_oversold=cls.SIGNAL_RSI_OVERSOLD,
            rsi_overbought=cls.SIGNAL_RSI_OVERBOUGHT,
            scan_interval=cls.SIGNAL_SCAN_INTERVAL,
        )


# Config Module
from .settings import Config
from .strategies import StrategyConfig

__all__ = ['Config', 'StrategyConfig']
