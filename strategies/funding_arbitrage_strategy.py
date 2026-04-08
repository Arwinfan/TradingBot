"""
资金费率套利策略 (Funding Rate Arbitrage Strategy)

策略原理：
1. 监控多个币种的资金费率
2. 当资金费率为正且较高时，做多合约 + 做空反向合约
3. 当资金费率为负且较低时，做空合约 + 做多反向合约
4. 持有仓位至资金费率结算，获取费率差收益

适用场景：
- 高波动市场中的稳定套利
- 资金费率较高的币种

注意：此策略为合约对冲套利，需要持有双向仓位
"""

from typing import Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from .base_strategy import BaseStrategy, Signal, SignalType
from config.strategies import StrategyConfig
from utils.logger import get_logger

logger = get_logger(__name__)

# 资金费率套利策略默认配置
FUNDING_ARBITRAGE_STRATEGY = {
    'default_params': {
        'symbol': 'BTCUSDT',
        'min_funding_rate': 0.0001,      # 最小资金费率阈值 (0.01%)
        'max_position_size': 100,         # 最大仓位大小 (USDT)
        'hedge_profit_target': 0.001,     # 对冲止盈目标 (0.1%)
        'max_loss': 0.002,                # 最大亏损 (0.2%)
        'holding_hours': 8,               # 持有时间 (小时，资金费率结算周期)
        'max_positions': 3,               # 最大同时持仓数
        'rebalance_interval': 24,          # 仓位再平衡间隔 (小时)
    }
}


@dataclass
class FundingPosition:
    """资金费率套利仓位"""
    symbol: str
    long_size: float          # 多头仓位
    short_size: float          # 空头仓位
    entry_funding_rate: float # 入场时的资金费率
    entry_price_long: float   # 多头入场价
    entry_price_short: float  # 空头入场价
    entry_time: datetime
    funding_earned: float = 0 # 已获得的资金费率收益


class FundingArbitrageStrategy(BaseStrategy):
    """
    资金费率套利策略

    策略特点：
    - 低风险稳定收益
    - 利用资金费率差获利
    - 自动对冲降低市场风险
    """

    def __init__(self, params: Dict = None):
        """
        初始化资金费率套利策略

        Args:
            params: 策略参数
                - symbol: 交易对
                - min_funding_rate: 最小资金费率阈值
                - max_position_size: 最大仓位大小
                - hedge_profit_target: 对冲止盈目标
                - max_loss: 最大亏损
                - holding_hours: 持有时间
                - max_positions: 最大同时持仓数
                - rebalance_interval: 仓位再平衡间隔
        """
        default_params = FUNDING_ARBITRAGE_STRATEGY['default_params'].copy()
        if params:
            default_params.update(params)

        super().__init__('FundingArbitrageStrategy', default_params)

        # 策略参数
        self.min_funding_rate = self.params['min_funding_rate']
        self.max_position_size = self.params['max_position_size']
        self.hedge_profit_target = self.params['hedge_profit_target']
        self.max_loss = self.params['max_loss']
        self.holding_hours = self.params['holding_hours']
        self.max_positions = self.params['max_positions']
        self.rebalance_interval = self.params['rebalance_interval']

        # 仓位管理
        self.funding_positions: List[FundingPosition] = []
        self.last_rebalance_time: datetime = None

        # 从数据库加载已保存的状态
        self._load_state()

    def _load_state(self):
        """加载状态"""
        state_data = self._data.get_strategy_state('FundingArbitrageStrategy')
        if state_data and state_data.get('params'):
            params = state_data['params']
            # 恢复所有参数到 self.params
            for key, value in params.items():
                if key not in ['positions', 'last_rebalance_time', 'trades_today', 'wins_today', 'losses_today', 'last_trade_time']:
                    self.params[key] = value
            # 恢复 symbol
            if params.get('symbol'):
                self.symbol = params['symbol']
            # 加载仓位
            if 'positions' in params:
                for pos_data in params['positions']:
                    pos = FundingPosition(
                        symbol=pos_data['symbol'],
                        long_size=pos_data['long_size'],
                        short_size=pos_data['short_size'],
                        entry_funding_rate=pos_data['entry_funding_rate'],
                        entry_price_long=pos_data['entry_price_long'],
                        entry_price_short=pos_data['entry_price_short'],
                        entry_time=datetime.fromisoformat(pos_data['entry_time']),
                        funding_earned=pos_data.get('funding_earned', 0)
                    )
                    self.funding_positions.append(pos)
            # 更新所有策略参数属性
            for key in ['symbol', 'min_funding_rate', 'max_position_size', 'hedge_profit_target', 'max_loss', 'holding_hours', 'max_positions', 'rebalance_interval']:
                if key in self.params:
                    setattr(self, key, self.params[key])

    def _save_state(self):
        """保存状态"""
        positions_data = []
        for pos in self.funding_positions:
            positions_data.append({
                'symbol': pos.symbol,
                'long_size': pos.long_size,
                'short_size': pos.short_size,
                'entry_funding_rate': pos.entry_funding_rate,
                'entry_price_long': pos.entry_price_long,
                'entry_price_short': pos.entry_price_short,
                'entry_time': pos.entry_time.isoformat(),
                'funding_earned': pos.funding_earned,
            })

        state_params = {
            **self.params,
            'positions': positions_data,
        }
        self._data.save_strategy_state('FundingArbitrageStrategy', state_params, self.status)

    def start(self):
        """启动策略"""
        self.status = 'running'
        self._save_state()
        logger.info(f"{self.name}: 策略已启动")

    def stop(self):
        """停止策略"""
        self.status = 'stopped'
        # 平掉所有仓位
        self._close_all_positions()
        self._save_state()
        logger.info(f"{self.name}: 策略已停止")

    def update_params(self, params: Dict):
        """更新策略参数"""
        self.params.update(params)
        for key in ['symbol', 'min_funding_rate', 'max_position_size', 'hedge_profit_target',
                   'max_loss', 'holding_hours', 'max_positions', 'rebalance_interval']:
            if key in params:
                setattr(self, key, params[key])
        self._save_state()

    def analyze(self) -> Signal:
        """
        分析市场并生成交易信号
        """
        ticker = self._market.get_ticker(self.symbol)
        current_price = ticker.get('last', 0)

        # 检查是否需要平仓
        close_signal = self._check_close_conditions(current_price)
        if close_signal:
            return close_signal

        # 检查是否需要建仓
        if len(self.funding_positions) < self.max_positions:
            entry_signal = self._check_entry_conditions(current_price)
            if entry_signal:
                return entry_signal

        # 检查是否需要再平衡
        if self._should_rebalance():
            return Signal(
                type=SignalType.HOLD,
                symbol=self.symbol,
                price=current_price,
                amount=0,
                confidence=1.0,
                reason="需要进行仓位再平衡",
            )

        return Signal(
            type=SignalType.HOLD,
            symbol=self.symbol,
            price=current_price,
            amount=0,
            confidence=1.0,
            reason=f"当前持仓数: {len(self.funding_positions)}, 等待资金费率机会",
        )

    def _check_close_conditions(self, current_price: float) -> Signal:
        """检查平仓条件"""
        positions_to_close = []

        for i, pos in enumerate(self.funding_positions):
            # 计算持仓时间
            holding_hours = (datetime.now() - pos.entry_time).total_seconds() / 3600

            # 检查是否到达持有时间
            if holding_hours >= self.holding_hours:
                positions_to_close.append((i, '持有时间到期'))
                continue

            # 计算盈亏
            if pos.long_size > 0 and pos.entry_price_long > 0:
                long_pnl_percent = (current_price - pos.entry_price_long) / pos.entry_price_long
                if long_pnl_percent >= self.hedge_profit_target:
                    positions_to_close.append((i, f'达到止盈目标: {long_pnl_percent:.2%}'))
                    continue
                if long_pnl_percent <= -self.max_loss:
                    positions_to_close.append((i, f'达到止损: {long_pnl_percent:.2%}'))
                    continue

        if positions_to_close:
            i, reason = positions_to_close[0]
            pos = self.funding_positions[i]
            close_amount = pos.long_size + pos.short_size
            return Signal(
                type=SignalType.SELL,
                symbol=self.symbol,
                price=current_price,
                amount=close_amount,
                confidence=0.9,
                reason=f"平仓: {reason}, 预计收益: {pos.funding_earned:.2f} USDT",
            )

        return None

    def _check_entry_conditions(self, current_price: float) -> Signal:
        """检查建仓条件"""
        # 获取资金费率
        funding_rate = self._get_funding_rate()

        if funding_rate is None:
            return None

        logger.info(f"{self.symbol} 当前资金费率: {funding_rate:.4%}")

        # 检查资金费率是否达到阈值
        if abs(funding_rate) < self.min_funding_rate:
            return Signal(
                type=SignalType.HOLD,
                symbol=self.symbol,
                price=current_price,
                amount=0,
                confidence=1.0,
                reason=f"资金费率未达标: {funding_rate:.4%} < {self.min_funding_rate:.4%}",
            )

        # 资金费率为正，做多
        if funding_rate > 0:
            amount = min(self.max_position_size, self._get_available_position_size()) / current_price
            return Signal(
                type=SignalType.BUY,
                symbol=self.symbol,
                price=current_price,
                amount=amount,
                confidence=0.8,
                reason=f"资金费率套利建仓: 费率={funding_rate:.4%}, 预计收益={funding_rate * 3 * amount * current_price:.2f} USDT/周期",
            )

        return None

    def _get_funding_rate(self) -> float:
        """获取当前资金费率"""
        try:
            data = self._market._client._request('GET', '/fapi/v1/premiumIndex', params={'symbol': self.symbol})
            return float(data.get('lastFundingRate', 0))
        except Exception as e:
            logger.warning(f"获取资金费率失败: {e}")
            return None

    def _get_available_position_size(self) -> float:
        """获取可用仓位大小"""
        balance = self._trade.get_balance()
        available = balance.get('free', {}).get('USDT', 0)
        return min(available * 0.5, self.max_position_size)

    def _should_rebalance(self) -> bool:
        """检查是否需要再平衡"""
        if not self.last_rebalance_time:
            return False
        hours_since = (datetime.now() - self.last_rebalance_time).total_seconds() / 3600
        return hours_since >= self.rebalance_interval

    def _close_all_positions(self):
        """平掉所有仓位"""
        for pos in self.funding_positions:
            try:
                if pos.long_size > 0:
                    self._trade.market_sell(self.symbol, pos.long_size)
                if pos.short_size > 0:
                    self._trade.market_buy(self.symbol, pos.short_size)
            except Exception as e:
                logger.error(f"平仓失败: {e}")
        self.funding_positions.clear()

    def execute(self, signal: Signal = None) -> Dict:
        """执行交易信号"""
        if signal is None:
            signal = self.analyze()

        result = super().execute(signal)

        # 更新仓位记录
        if signal.type == SignalType.BUY and result.get('result', {}).get('success'):
            # 记录套利仓位
            funding_rate = self._get_funding_rate()
            position = FundingPosition(
                symbol=self.symbol,
                long_size=signal.amount,
                short_size=0,  # 单边做多
                entry_funding_rate=funding_rate or 0,
                entry_price_long=signal.price,
                entry_price_short=0,
                entry_time=datetime.now(),
            )
            self.funding_positions.append(position)
            self._save_state()

        elif signal.type == SignalType.SELL and result.get('result', {}).get('success'):
            if self.funding_positions:
                pos = self.funding_positions.pop(0)
                # 计算收益
                funding_earned = pos.long_size * pos.entry_funding_rate * pos.entry_price_long * 3
                logger.info(f"资金费率套利完成: 收益={funding_earned:.2f} USDT")
            self._save_state()

        return result

    def get_status(self) -> Dict:
        """获取策略状态"""
        base_status = super().get_status()

        # 计算统计
        total_funding_earned = sum(pos.funding_earned for pos in self.funding_positions)
        current_price = self._market.get_ticker(self.symbol).get('last', 0)
        funding_rate = self._get_funding_rate()

        # 计算预估收益
        estimated_hourly = 0
        if funding_rate and self.funding_positions:
            for pos in self.funding_positions:
                estimated_hourly += pos.long_size * funding_rate * current_price

        arbitrage_status = {
            'funding_arbitrage': {
                'positions': len(self.funding_positions),
                'max_positions': self.max_positions,
                'current_funding_rate': funding_rate,
                'min_funding_rate': self.min_funding_rate,
                'total_funding_earned': total_funding_earned,
                'estimated_hourly_profit': estimated_hourly,
                'next_settlement': self._get_next_funding_time(),
                'params': {
                    'holding_hours': self.holding_hours,
                    'hedge_profit_target': self.hedge_profit_target,
                    'max_loss': self.max_loss,
                    'max_position_size': self.max_position_size,
                },
            }
        }

        return {**base_status, **arbitrage_status}

    def _get_next_funding_time(self) -> str:
        """获取下次资金费率结算时间"""
        now = datetime.now()
        # 资金费率每8小时结算: 0:00, 8:00, 16:00
        hours = now.hour
        if hours < 8:
            next_hour = 8
        elif hours < 16:
            next_hour = 16
        else:
            next_hour = 24  # 下一天0点

        next_time = now.replace(hour=next_hour % 24, minute=0, second=0, microsecond=0)
        if next_hour >= 24:
            next_time += timedelta(days=1)

        return next_time.isoformat()

    def get_estimated_profit(self) -> Dict:
        """获取预估收益"""
        current_price = self._market.get_ticker(self.symbol).get('last', 0)
        funding_rate = self._get_funding_rate()

        if not funding_rate or not self.funding_positions:
            return {
                'hourly': 0,
                'daily': 0,
                'per_funding': 0,
            }

        total_size = sum(pos.long_size for pos in self.funding_positions)
        per_funding = total_size * funding_rate * current_price
        hourly = per_funding / 8  # 每小时平均
        daily = per_funding * 3  # 每天3个结算周期

        return {
            'hourly': hourly,
            'daily': daily,
            'per_funding': per_funding,
            'total_size': total_size,
            'funding_rate': funding_rate,
        }
