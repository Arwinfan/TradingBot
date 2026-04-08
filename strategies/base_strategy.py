"""
策略基类 - 定义策略接口规范
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

from core.futures_service import get_futures_market_service
from core.trade_service import get_trade_service
from core.data_service import get_data_service
from utils.logger import get_logger

logger = get_logger(__name__)


class SignalType(Enum):
    """信号类型"""
    BUY = 'buy'
    SELL = 'sell'
    HOLD = 'hold'


@dataclass
class Signal:
    """交易信号"""
    type: SignalType
    symbol: str
    price: float
    amount: float
    confidence: float  # 置信度 0-1
    reason: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class BaseStrategy(ABC):
    """
    策略基类
    所有策略都应继承此类并实现相应方法
    """

    def __init__(self, name: str, params: Dict):
        """
        初始化策略

        Args:
            name: 策略名称
            params: 策略参数
        """
        self.name = name
        self.params = params
        self.symbol = params.get('symbol', 'BTCUSDT')
        self.status = 'stopped'
        self.last_signal: Optional[Signal] = None
        self.last_run_time: Optional[datetime] = None

        # 服务实例
        self._market = get_futures_market_service()
        self._trade = get_trade_service()
        self._data = get_data_service()

    @abstractmethod
    def analyze(self) -> Signal:
        """
        分析市场数据并生成信号

        Returns:
            交易信号
        """
        pass

    def execute(self, signal: Signal = None) -> Dict:
        """
        执行交易信号

        Args:
            signal: 交易信号，如果为None则自动调用analyze()

        Returns:
            执行结果
        """
        if signal is None:
            signal = self.analyze()

        self.last_signal = signal

        # 转换 Signal 为字典
        def signal_to_dict(s):
            if s is None:
                return None
            return {
                'type': s.type.value if hasattr(s.type, 'value') else str(s.type),
                'symbol': s.symbol,
                'price': s.price,
                'amount': s.amount,
                'confidence': s.confidence,
                'reason': s.reason,
            }

        if signal.type == SignalType.HOLD:
            logger.debug(f"{self.name}: 持仓观望")
            return {'action': 'hold', 'signal': signal_to_dict(signal)}

        try:
            if signal.type == SignalType.BUY:
                result = self._trade.market_buy(
                    signal.symbol,
                    signal.amount,
                    check_risk=True
                )
                action = 'buy'

            elif signal.type == SignalType.SELL:
                result = self._trade.market_sell(
                    signal.symbol,
                    signal.amount,
                    check_risk=True
                )
                action = 'sell'

            else:
                return {'action': 'hold', 'signal': signal_to_dict(signal)}

            # 保存交易记录
            if result.get('success'):
                self._data.save_trade({
                    'order_id': result['order'].get('id'),
                    'symbol': signal.symbol,
                    'side': action,
                    'order_type': 'market',
                    'price': signal.price,
                    'amount': signal.amount,
                    'total': result.get('total', 0),
                    'strategy': self.name,
                    'order_id_exchange': result['order'].get('id'),
                    'status': 'closed',
                })

                # 更新策略统计
                self._data.update_strategy_stats(self.name, 0)

            logger.info(f"{self.name}: {action} 执行结果 {result}")
            return {
                'action': action,
                'signal': signal_to_dict(signal),
                'result': result,
            }

        except Exception as e:
            logger.error(f"{self.name}: 执行失败 {e}")
            return {
                'action': 'error',
                'signal': signal_to_dict(signal),
                'error': str(e),
            }

    def run(self) -> Dict:
        """
        运行策略: 分析 + 执行

        Returns:
            运行结果
        """
        self.last_run_time = datetime.now()

        try:
            signal = self.analyze()
            result = self.execute(signal)

            # 转换 Signal 为可序列化字典
            signal_dict = None
            if signal:
                signal_dict = {
                    'type': signal.type.value if hasattr(signal.type, 'value') else str(signal.type),
                    'symbol': signal.symbol,
                    'price': signal.price,
                    'amount': signal.amount,
                    'confidence': signal.confidence,
                    'reason': signal.reason,
                    'timestamp': signal.timestamp.isoformat() if signal.timestamp else None
                }

            return {
                'success': True,
                'signal': signal_dict,
                'result': result,
                'timestamp': self.last_run_time.isoformat() if self.last_run_time else None,
            }

        except Exception as e:
            logger.error(f"{self.name}: 运行失败 {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': self.last_run_time.isoformat() if self.last_run_time else None,
            }

    def start(self):
        """启动策略"""
        self.status = 'running'
        self._data.save_strategy_state(self.name, self.params, 'running')
        logger.info(f"{self.name}: 策略已启动")

    def stop(self):
        """停止策略"""
        self.status = 'stopped'
        self._data.save_strategy_state(self.name, self.params, 'stopped')
        logger.info(f"{self.name}: 策略已停止")

    def get_status(self) -> Dict:
        """获取策略状态（完整版，包含市场数据）"""
        # 从数据库获取策略统计
        db_state = self._data.get_strategy_state(self.name)
        stats = {}
        if db_state:
            stats = {
                'total_trades': db_state.get('total_trades', 0),
                'total_pnl': db_state.get('total_pnl', 0),
            }
            # 计算盈亏百分比 (基于总投资)
            investment = self.params.get('investment', 0) or self.params.get('investment_per_trade', 0) or 1000
            if investment > 0 and stats.get('total_pnl', 0) != 0:
                stats['pnl_percent'] = (stats['total_pnl'] / investment) * 100
            else:
                stats['pnl_percent'] = 0

        # 获取交易汇总
        trade_summary = self._data.get_trade_summary(strategy=self.name)

        return {
            'name': self.name,
            'status': self.status,
            'symbol': self.symbol,
            'last_run': self.last_run_time.isoformat() if self.last_run_time else None,
            'last_signal': {
                'type': self.last_signal.type.value if self.last_signal else None,
                'price': self.last_signal.price if self.last_signal else None,
                'confidence': self.last_signal.confidence if self.last_signal else None,
                'reason': self.last_signal.reason if self.last_signal else None,
            } if self.last_signal else None,
            'params': self.params,
            'stats': stats,
            'trade_summary': trade_summary,
        }

    def get_simple_status(self) -> Dict:
        """获取策略状态（轻量版，不含市场数据，用于列表展示）"""
        # 从数据库获取策略统计
        db_state = self._data.get_strategy_state(self.name)
        stats = {}
        if db_state:
            stats = {
                'total_trades': db_state.get('total_trades', 0),
                'total_pnl': db_state.get('total_pnl', 0),
            }

        return {
            'name': self.name,
            'status': self.status,
            'symbol': self.symbol,
            'last_run': self.last_run_time.isoformat() if self.last_run_time else None,
            'params': self.params,
            'stats': stats,
        }

    def update_params(self, params: Dict):
        """更新策略参数"""
        self.params.update(params)
        self._data.save_strategy_state(self.name, self.params, self.status)

    def get_position(self) -> Dict:
        """获取当前持仓"""
        return self._trade.get_position(self.symbol)

    def get_market_data(self, timeframe: str = '1h', limit: int = 100) -> List:
        """获取市场数据"""
        return self._market.get_ohlcv(self.symbol, timeframe, limit)


class StrategyManager:
    """
    策略管理器
    统一管理所有策略的运行
    """

    _instance = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._strategies: Dict[str, BaseStrategy] = {}
        self._data = get_data_service()
        self._load_saved_strategies()

    def _load_saved_strategies(self):
        """加载已保存的策略状态"""
        states = self._data.get_all_strategy_states()
        for state in states:
            logger.debug(f"加载策略状态: {state['strategy_type']} - {state['status']}")

    def register(self, strategy: BaseStrategy):
        """注册策略"""
        self._strategies[strategy.name] = strategy
        logger.info(f"策略已注册: {strategy.name}")

    def unregister(self, name: str):
        """取消注册策略"""
        if name in self._strategies:
            self._strategies[name].stop()
            del self._strategies[name]
            logger.info(f"策略已取消: {name}")

    def _normalize_name(self, name: str) -> str:
        """规范化策略名称"""
        name_map = {
            'grid': 'GridStrategy',
            'dca': 'DCAStrategy',
            'trend': 'TrendStrategy',
            'scalping': 'ScalpingStrategy',
            'funding': 'FundingArbitrageStrategy',
        }
        return name_map.get(name.lower(), name)

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """获取策略"""
        strategy_name = self._normalize_name(name)
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            strategy = self._strategies.get(name)
        return strategy

    def list_strategies(self) -> List[Dict]:
        """列出所有策略（使用轻量级状态）"""
        return [s.get_simple_status() for s in self._strategies.values()]

    def start_strategy(self, name: str) -> bool:
        """启动策略"""
        strategy = self.get_strategy(name)
        if strategy:
            strategy.start()
            return True
        return False

    def stop_strategy(self, name: str) -> bool:
        """停止策略"""
        strategy = self.get_strategy(name)
        if strategy:
            strategy.stop()
            return True
        return False

    def run_all(self) -> Dict:
        """运行所有策略"""
        results = {}
        for name, strategy in self._strategies.items():
            if strategy.status == 'running':
                try:
                    results[name] = strategy.run()
                except Exception as e:
                    results[name] = {'success': False, 'error': str(e)}
        return results

    def run_strategy(self, name: str) -> Optional[Dict]:
        """运行单个策略"""
        strategy = self.get_strategy(name)
        if strategy:
            return strategy.run()
        return None


# 全局管理器实例
_manager = None


def get_strategy_manager() -> StrategyManager:
    """获取全局策略管理器"""
    global _manager
    if _manager is None:
        _manager = StrategyManager()
    return _manager
