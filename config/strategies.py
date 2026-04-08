"""
策略配置 - 币安量化交易系统
"""

# ==================== 网格策略配置 ====================
GRID_STRATEGY = {
    'name': '网格策略',
    'description': '在固定价格区间内设置网格，低买高卖',
    'default_params': {
        'symbol': 'BTCUSDT',
        'grid_count': 10,           # 网格数量
        'investment': 1000,         # 总投资金额 (USDT)
        'price_range_low': 0,       # 价格区间下限 (0 = 自动计算)
        'price_range_high': 0,      # 价格区间上限 (0 = 自动计算)
        'stop_loss': 0.05,          # 止损比例 (5%)
        'take_profit': 0.10,       # 止盈比例 (10%)
    },
    'param_ranges': {
        'grid_count': (2, 50),
        'investment': (100, 100000),
        'stop_loss': (0.01, 0.50),
        'take_profit': (0.01, 1.00),
    },
}

# ==================== 定投策略配置 ====================
DCA_STRATEGY = {
    'name': '定投策略',
    'description': '定期定额买入，平均成本',
    'default_params': {
        'symbol': 'BTCUSDT',
        'investment_per_trade': 100,     # 每次买入金额 (USDT)
        'interval_hours': 24,            # 买入间隔 (小时)
        'target_position': 5000,         # 目标持仓 (USDT)
        'max_price': 0,                  # 最高买入价 (0 = 不限制)
        'min_price': 0,                  # 最低买入价 (0 = 不限制)
    },
    'param_ranges': {
        'investment_per_trade': (10, 10000),
        'interval_hours': (1, 720),
        'target_position': (100, 100000),
    },
}

# ==================== 趋势策略配置 ====================
TREND_STRATEGY = {
    'name': '趋势策略',
    'description': '跟随趋势方向交易，MACD + RSI 信号',
    'default_params': {
        'symbol': 'BTCUSDT',
        'investment': 1000,              # 单笔投资金额 (USDT)
        'kline_interval': '1h',         # K线周期
        'fast_ema': 12,                 # 快线 EMA 周期
        'slow_ema': 26,                 # 慢线 EMA 周期
        'signal_ema': 9,               # 信号线 EMA 周期
        'rsi_period': 14,               # RSI 周期
        'rsi_overbought': 70,            # RSI 超买阈值
        'rsi_oversold': 30,              # RSI 超卖阈值
        'stop_loss': 0.02,              # 止损比例 (2%)
        'trailing_stop': 0.01,          # 追踪止损比例 (1%)
    },
    'param_ranges': {
        'investment': (50, 10000),
        'fast_ema': (5, 20),
        'slow_ema': (20, 50),
        'signal_ema': (5, 20),
        'rsi_period': (7, 21),
        'rsi_overbought': (60, 90),
        'rsi_oversold': (10, 40),
        'stop_loss': (0.005, 0.10),
        'trailing_stop': (0.005, 0.05),
    },
}

# ==================== 资金费率套利策略配置 ====================
FUNDING_ARBITRAGE_STRATEGY = {
    'name': '资金费率套利',
    'description': '利用合约资金费率获取稳定收益',
    'default_params': {
        'symbol': 'BTCUSDT',
        'min_funding_rate': 0.0001,      # 最小资金费率阈值 (0.01%)
        'max_position_size': 100,         # 最大仓位大小 (USDT)
        'hedge_profit_target': 0.001,     # 对冲止盈目标 (0.1%)
        'max_loss': 0.002,                # 最大亏损 (0.2%)
        'holding_hours': 8,               # 持有时间 (小时)
        'max_positions': 3,              # 最大同时持仓数
        'rebalance_interval': 24,         # 仓位再平衡间隔 (小时)
    },
    'param_ranges': {
        'min_funding_rate': (0.00001, 0.01),
        'max_position_size': (10, 10000),
        'hedge_profit_target': (0.0005, 0.05),
        'max_loss': (0.0005, 0.05),
        'holding_hours': (1, 72),
        'max_positions': (1, 10),
    },
}

# ==================== 剥头皮策略配置 ====================
SCALPING_STRATEGY = {
    'name': '剥头皮策略',
    'description': '利用短期波动快速小额盈利，多指标确认',
    'default_params': {
        'symbol': 'BTCUSDT',
        'profit_target': 0.0025,        # 盈利目标 (0.25%)
        'stop_loss': 0.001,             # 止损 (0.1%)
        'max_holding_seconds': 180,      # 最大持仓时间 (秒)
        'min_volatility': 0.0004,       # 最小波动率
        'position_size': 80,            # 仓位大小 (USDT)
        'kline_interval': '1m',         # K线周期
        'ema_fast': 9,                  # 快速EMA (推荐9)
        'ema_slow': 21,                 # 慢速EMA (推荐21)
        'rsi_period': 14,               # RSI周期
        'rsi_overbought': 72,           # RSI超买阈值
        'rsi_oversold': 28,             # RSI超卖阈值
        'max_daily_trades': 25,         # 每日最大交易次数
        'cooldown_seconds': 25,          # 交易间隔冷却时间
        'use_rsi_filter': True,          # 使用RSI过滤
        'use_macd_filter': True,         # 使用MACD过滤
    },
    'param_ranges': {
        'profit_target': (0.001, 0.005),
        'stop_loss': (0.0005, 0.002),
        'max_holding_seconds': (60, 300),
        'min_volatility': (0.0002, 0.001),
        'position_size': (50, 500),
        'ema_fast': (5, 15),
        'ema_slow': (15, 30),
        'rsi_period': (7, 21),
        'rsi_overbought': (60, 80),
        'rsi_oversold': (20, 40),
        'max_daily_trades': (10, 50),
        'cooldown_seconds': (10, 60),
    },
    'presets': {
        'conservative': {
            'profit_target': 0.002,
            'stop_loss': 0.001,
            'max_holding_seconds': 300,
            'position_size': 50,
            'ema_fast': 9,
            'ema_slow': 21,
            'max_daily_trades': 15,
            'cooldown_seconds': 30,
        },
        'moderate': {
            'profit_target': 0.0025,
            'stop_loss': 0.001,
            'max_holding_seconds': 180,
            'position_size': 80,
            'ema_fast': 9,
            'ema_slow': 21,
            'max_daily_trades': 25,
            'cooldown_seconds': 25,
        },
        'aggressive': {
            'profit_target': 0.003,
            'stop_loss': 0.0015,
            'max_holding_seconds': 60,
            'position_size': 150,
            'ema_fast': 5,
            'ema_slow': 15,
            'max_daily_trades': 40,
            'cooldown_seconds': 15,
        },
    },
}

# ==================== 自适应策略配置 ====================
ADAPTIVE_STRATEGY = {
    'name': '自适应策略',
    'description': '根据ADX自动切换趋势/震荡模式，挂单开仓',
    'default_params': {
        'symbol': 'ETHUSDT',
        'leverage': 50,                  # 杠杆倍数
        'position_value': 20,             # 单次开仓本金 (USDT)
        'stop_loss_pct': 0.50,            # 止损50%本金
        'kline_interval': '5m',          # K线周期
        'adx_threshold': 25,              # ADX阈值
        'ema_fast': 9,                    # 快速EMA
        'ema_slow': 21,                   # 慢速EMA
        'rsi_period': 14,                 # RSI周期
        'rsi_overbought': 70,             # RSI超买
        'rsi_oversold': 30,              # RSI超卖
        'bollinger_period': 20,           # 布林带周期
        'bollinger_std': 2,               # 布林带标准差倍数
        'take_profit_1': 0.20,           # 第一止盈20%
        'take_profit_1_ratio': 0.50,     # 第一止盈平50%
        'take_profit_2': 0.30,           # 第二止盈30%
        'pending_timeout': 180,           # 挂单超时秒数 (3分钟)
        'limit_offset': 0.001,            # 限价单偏移量 (0.1%)
        'cooldown_seconds': 300,          # 冷却时间 (5分钟)
        'max_positions': 1,              # 最大持仓数
    },
    'param_ranges': {
        'leverage': (1, 125),
        'position_value': (10, 100),
        'stop_loss_pct': (0.10, 1.00),
        'adx_threshold': (15, 40),
        'ema_fast': (5, 20),
        'ema_slow': (10, 50),
        'rsi_overbought': (60, 85),
        'rsi_oversold': (15, 40),
        'bollinger_period': (10, 30),
        'take_profit_1': (0.10, 0.50),
        'take_profit_2': (0.20, 1.00),
        'pending_timeout': (60, 600),
        'cooldown_seconds': (60, 600),
    },
}

# ==================== 所有策略列表 ====================
ALL_STRATEGIES = {
    'grid': GRID_STRATEGY,
    'dca': DCA_STRATEGY,
    'trend': TREND_STRATEGY,
    'funding': FUNDING_ARBITRAGE_STRATEGY,
    'scalping': SCALPING_STRATEGY,
    'adaptive': ADAPTIVE_STRATEGY,
}


class StrategyConfig:
    """策略配置类"""

    STRATEGIES = ALL_STRATEGIES

    @classmethod
    def get_strategy(cls, strategy_type):
        """获取策略配置"""
        return cls.STRATEGIES.get(strategy_type)

    @classmethod
    def get_all_strategies(cls):
        """获取所有策略列表"""
        return cls.STRATEGIES

    @classmethod
    def get_default_params(cls, strategy_type):
        """获取策略默认参数"""
        strategy = cls.get_strategy(strategy_type)
        return strategy['default_params'].copy() if strategy else {}

    @classmethod
    def validate_params(cls, strategy_type, params):
        """验证策略参数"""
        strategy = cls.get_strategy(strategy_type)
        if not strategy:
            return False, f"未知的策略类型: {strategy_type}"

        ranges = strategy.get('param_ranges', {})
        for param, value in params.items():
            if param in ranges:
                min_val, max_val = ranges[param]
                if not (min_val <= value <= max_val):
                    return False, f"{param} 值必须在 {min_val} 到 {max_val} 之间"

        return True, "参数有效"
