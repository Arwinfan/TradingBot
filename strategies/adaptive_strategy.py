"""
自适应策略 (Adaptive Strategy)
根据市场状态自动切换趋势/震荡交易模式
- ADX > 25: 趋势模式 (EMA金叉死叉)
- ADX < 25: 震荡模式 (RSI + 布林带)
- 50倍杠杆，20U本位
- 分批止盈：20%平50%，30%平50%
- 挂单开仓，3分钟超时撤销
- 50%止损，价格回归后保本
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .base_strategy import BaseStrategy, Signal, SignalType
from utils.logger import get_logger
from config.settings import Config

logger = get_logger(__name__)

# 自适应策略默认配置
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
        'take_profit_1': 2.0,             # 第一止盈(USDT)
        'take_profit_1_ratio': 0.50,     # 第一止盈平50%
        'take_profit_2': 5.0,            # 第二止盈(USDT)
        'pending_timeout': 180,           # 挂单超时秒数 (3分钟)
        'limit_offset': 0.001,            # 限价单偏移量 (0.1%)
        'cooldown_seconds': 300,          # 冷却时间 (5分钟)
        'max_positions': 1,              # 最大持仓数
    }
}


@dataclass
class AdaptivePosition:
    """自适应策略仓位"""
    entry_price: float
    entry_time: datetime
    side: str  # 'long' or 'short'
    amount: float
    position_value: float
    stop_loss_price: float
    take_profit_1_triggered: bool
    take_profit_2_triggered: bool
    breakeven_set: bool  # 是否已设置保本止损


@dataclass
class PendingOrder:
    """挂单信息"""
    order_id: str
    side: str  # 'long' or 'short'
    price: float  # 挂单价格
    amount: float
    created_time: datetime
    signal_reason: str  # 信号原因


class AdaptiveStrategy(BaseStrategy):
    """
    自适应策略

    策略特点：
    - 根据ADX判断市场状态
    - 趋势模式：EMA金叉死叉
    - 震荡模式：RSI + 布林带
    - 50倍杠杆，20U本位
    - 分批止盈：20%平50%，30%平50%
    - 挂单开仓，3分钟超时撤销
    - 50%止损，价格回归后保本
    """

    def __init__(self, params: Dict = None):
        default_params = ADAPTIVE_STRATEGY['default_params'].copy()
        if params:
            default_params.update(params)

        super().__init__('AdaptiveStrategy', default_params)

        # 策略参数
        self.leverage = self.params['leverage']
        self.position_value = self.params['position_value']
        self.stop_loss_pct = self.params['stop_loss_pct']
        self.kline_interval = self.params['kline_interval']
        self.adx_threshold = self.params['adx_threshold']
        self.ema_fast = self.params['ema_fast']
        self.ema_slow = self.params['ema_slow']
        self.rsi_period = self.params.get('rsi_period', 14)
        self.rsi_overbought = self.params.get('rsi_overbought', 70)
        self.rsi_oversold = self.params.get('rsi_oversold', 30)
        self.bollinger_period = self.params.get('bollinger_period', 20)
        self.bollinger_std = self.params.get('bollinger_std', 2)
        self.take_profit_1 = self.params['take_profit_1']
        self.take_profit_1_ratio = self.params['take_profit_1_ratio']
        self.take_profit_2 = self.params['take_profit_2']
        self.pending_timeout = self.params.get('pending_timeout', 180)
        self.limit_offset = self.params.get('limit_offset', 0.001)
        self.cooldown_seconds = self.params['cooldown_seconds']
        self.max_positions = self.params['max_positions']

        # 运行时状态
        self.current_position: AdaptivePosition = None
        self.pending_order: PendingOrder = None  # 挂单中
        self.last_trade_time: datetime = None
        self.trades_today = 0
        self.daily_reset_time: datetime = None

        # 加载状态（不覆盖当前symbol）
        self._load_state()

    def _load_state(self):
        """加载状态"""
        state_data = self._data.get_strategy_state('AdaptiveStrategy')
        if state_data and state_data.get('params'):
            params = state_data['params']
            # 不再从状态恢复symbol，始终使用params中的值
            self.trades_today = params.get('trades_today', 0)
            if params.get('last_trade_time'):
                self.last_trade_time = datetime.fromisoformat(params['last_trade_time'])
            # 恢复挂单状态
            if params.get('pending_order'):
                p = params['pending_order']
                self.pending_order = PendingOrder(
                    order_id=p.get('order_id', ''),
                    side=p.get('side', ''),
                    price=p.get('price', 0),
                    amount=p.get('amount', 0),
                    created_time=datetime.fromisoformat(p['created_time']) if p.get('created_time') else datetime.now(),
                    signal_reason=p.get('signal_reason', ''),
                )

    def _save_state(self):
        """保存状态"""
        pending_order_data = None
        if self.pending_order:
            pending_order_data = {
                'order_id': self.pending_order.order_id,
                'side': self.pending_order.side,
                'price': self.pending_order.price,
                'amount': self.pending_order.amount,
                'created_time': self.pending_order.created_time.isoformat(),
                'signal_reason': self.pending_order.signal_reason,
            }

        state_params = {
            **self.params,
            'trades_today': self.trades_today,
            'last_trade_time': self.last_trade_time.isoformat() if self.last_trade_time else None,
            'pending_order': pending_order_data,
        }
        self._data.save_strategy_state('AdaptiveStrategy', state_params, self.status)

    def start(self):
        """启动策略"""
        self.status = 'running'
        self._reset_daily_stats()
        # 记录启动时间和资金
        from datetime import datetime
        self._start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            self._start_balance = self._trade.get_available_balance('USDT')
            logger.info(f"{self.name}: 策略启动，初始资金: {self._start_balance:.2f} USDT")
        except Exception as e:
            self._start_balance = 0
            logger.warning(f"{self.name}: 获取启动资金失败: {e}")
        # 尝试取消之前的挂单
        self._cancel_pending_order()
        # 同步交易所持仓
        self._sync_position_from_exchange()
        self._save_state()
        logger.info(f"{self.name}: 策略已启动 (自适应模式)")

    def stop(self):
        """停止策略"""
        self.status = 'stopped'
        # 取消挂单
        self._cancel_pending_order()
        # 平掉当前持仓
        if self.current_position:
            self._close_position(reason="策略停止")
        # 生成交易总结
        self._log_trade_summary()
        self._save_state()
        logger.info(f"{self.name}: 策略已停止")

    def _log_trade_summary(self):
        """记录交易总结"""
        try:
            # 获取当前资金
            try:
                end_balance = self._trade.get_available_balance('USDT')
            except:
                end_balance = 0

            # 获取启动资金
            start_balance = getattr(self, '_start_balance', 0) or end_balance

            # 计算盈亏
            balance_pnl = end_balance - start_balance if start_balance else 0

            # 统计交易
            trades = self._data.get_trades(strategy=self.name, limit=100)

            # 过滤本次运行的交易(启动后的交易)
            start_time = getattr(self, '_start_time', None)
            if start_time:
                recent_trades = [t for t in trades if t.get('created_at', '') >= start_time]
            else:
                recent_trades = trades[-10:] if trades else []

            # 统计本次交易的盈亏
            total_pnl = 0
            wins = 0
            losses = 0
            for t in recent_trades:
                pnl = t.get('pnl', 0) or 0
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
                elif pnl < 0:
                    losses += 1

            logger.info(f"{'='*50}")
            logger.info(f"{self.name} 交易总结")
            logger.info(f"{'='*50}")
            logger.info(f"初始资金: {start_balance:.2f} USDT")
            logger.info(f"当前资金: {end_balance:.2f} USDT")
            logger.info(f"资金变化: {balance_pnl:+.2f} USDT ({balance_pnl/start_balance*100:+.2f}%)" if start_balance else "N/A")
            logger.info(f"-")
            logger.info(f"总交易次数: {len(recent_trades)}")
            logger.info(f"盈利次数: {wins}, 亏损次数: {losses}")
            logger.info(f"胜率: {wins/len(recent_trades)*100:.1f}%" if recent_trades else "N/A")
            logger.info(f"{'='*50}")
        except Exception as e:
            logger.warning(f"{self.name}: 生成交易总结失败: {e}")

    def update_params(self, params: Dict):
        """更新策略参数"""
        self.params.update(params)
        for key in ['symbol', 'leverage', 'position_value', 'stop_loss_pct', 'kline_interval',
                    'adx_threshold', 'ema_fast', 'ema_slow', 'rsi_period', 'rsi_overbought',
                    'rsi_oversold', 'bollinger_period', 'bollinger_std', 'take_profit_1',
                    'take_profit_1_ratio', 'take_profit_2', 'pending_timeout', 'limit_offset',
                    'cooldown_seconds', 'max_positions']:
            if key in params:
                setattr(self, key, params[key])
        self._save_state()

    def _reset_daily_stats(self):
        """重置每日统计"""
        now = datetime.now()
        if self.daily_reset_time is None or now.date() > self.daily_reset_time.date():
            self.trades_today = 0
            self.daily_reset_time = now

    def _sync_position_from_exchange(self):
        """从交易所同步持仓状态"""
        from core.futures_client import get_futures_client
        client = get_futures_client()

        try:
            exchange_pos = client.get_position(self.symbol)
            pos_size = float(exchange_pos.get('size', 0)) if exchange_pos else 0

            if pos_size > 0:
                # 交易所有持仓
                side = exchange_pos.get('side', 'long')
                entry_price = float(exchange_pos.get('entry_price', 0))
                amount = abs(pos_size)

                if self.current_position is None:
                    # 本地没有持仓，但交易所有，创建本地持仓记录
                    logger.info(f"{self.name}: 同步交易所持仓 {side} @ {entry_price}, 数量:{amount}")
                    self.current_position = AdaptivePosition(
                        entry_price=entry_price,
                        entry_time=datetime.now(),
                        side=side,
                        amount=amount,
                        position_value=self.position_value,
                        stop_loss_price=entry_price * (1 - self.stop_loss_pct / self.leverage) if side == 'long' else entry_price * (1 + self.stop_loss_pct / self.leverage),
                        take_profit_1_triggered=False,
                        take_profit_2_triggered=False,
                        breakeven_set=False,
                    )
                elif abs(self.current_position.amount - amount) > 0.001:
                    # 持仓数量不一致，更新
                    logger.info(f"{self.name}: 更新持仓数量 {self.current_position.amount} -> {amount}")
                    self.current_position.amount = amount
                    self.current_position.entry_price = entry_price
            elif self.current_position is not None:
                # 本地有持仓，但交易所没了（已平仓）
                logger.info(f"{self.name}: 检测到持仓已平仓，重置本地状态")
                self.current_position = None
                self.trades_today += 1
                self.last_trade_time = datetime.now()

        except Exception as e:
            logger.warning(f"{self.name}: 同步持仓失败: {e}")

        # 保存状态
        self._save_state()

    def _cancel_pending_order(self):
        """取消挂单"""
        if self.pending_order:
            try:
                from core.futures_client import get_futures_client
                client = get_futures_client()
                client.cancel_order(self.symbol, self.pending_order.order_id)
                logger.info(f"{self.name}: 取消挂单 {self.pending_order.order_id}")
            except Exception as e:
                logger.warning(f"{self.name}: 取消挂单失败: {e}")
            finally:
                self.pending_order = None

    def _check_pending_order_status(self, current_price: float) -> Optional[Signal]:
        """检查挂单状态"""
        if not self.pending_order:
            return None

        from core.futures_client import get_futures_client
        client = get_futures_client()

        try:
            # 查询订单状态
            orders = client.get_open_orders(self.symbol)
            order_filled = False

            for order in orders:
                if str(order.get('orderId', '')) == str(self.pending_order.order_id):
                    # 订单还在，检查是否已成交
                    if order.get('status') == 'FILLED':
                        order_filled = True
                        filled_price = float(order.get('avgPrice', self.pending_order.price))
                        filled_amount = float(order.get('executedQty', 0))

                        if filled_amount > 0:
                            # 成交了，创建持仓
                            logger.info(f"{self.name}: 挂单成交 @ {filled_price}, 数量:{filled_amount}")
                            self._create_position(
                                side=self.pending_order.side,
                                entry_price=filled_price,
                                amount=filled_amount
                            )
                            self.pending_order = None
                            return None
                    break

            # 订单不存在了（可能被系统撤销或成交）
            if not order_filled:
                for order in orders:
                    if str(order.get('orderId', '')) == str(self.pending_order.order_id):
                        break
                else:
                    # 订单不在列表中，可能已成交或被取消
                    logger.info(f"{self.name}: 挂单已撤销或失效")
                    self.pending_order = None
                    return None

            # 检查超时
            elapsed = (datetime.now() - self.pending_order.created_time).total_seconds()
            if elapsed >= self.pending_timeout:
                logger.info(f"{self.name}: 挂单超时({elapsed:.0f}秒)，撤销挂单")
                self._cancel_pending_order()
                # 重置冷却时间，从现在开始计算
                self.last_trade_time = datetime.now()
                return None

            return None

        except Exception as e:
            logger.warning(f"{self.name}: 检查挂单状态失败: {e}")
            return None

    def _create_position(self, side: str, entry_price: float, amount: float):
        """创建持仓"""
        if side == 'long':
            stop_loss_price = entry_price * (1 - self.stop_loss_pct / self.leverage)
        else:
            stop_loss_price = entry_price * (1 + self.stop_loss_pct / self.leverage)

        self.current_position = AdaptivePosition(
            entry_price=entry_price,
            entry_time=datetime.now(),
            side=side,
            amount=amount,
            position_value=self.position_value,
            stop_loss_price=stop_loss_price,
            take_profit_1_triggered=False,
            take_profit_2_triggered=False,
            breakeven_set=False,
        )

        logger.info(f"{self.name}: 开仓 {side} @ {entry_price}, 数量:{amount}, 止损:{stop_loss_price:.4f}")

    def analyze(self) -> Signal:
        """分析市场并生成交易信号"""
        self._reset_daily_stats()

        # 每次分析前先同步交易所持仓状态
        self._sync_position_from_exchange()

        ticker = self._market.get_ticker(self.symbol)
        current_price = ticker.get('last', 0)

        # 1. 检查挂单状态
        if self.pending_order:
            self._check_pending_order_status(current_price)
            # 如果有持仓但还有挂单，取消挂单（已有持仓不等挂单）
            if self.current_position:
                self._cancel_pending_order()
                close_signal = self._check_close_conditions(current_price)
                if close_signal:
                    return close_signal
                return Signal(
                    type=SignalType.HOLD,
                    symbol=self.symbol,
                    price=current_price,
                    amount=0,
                    confidence=1.0,
                    reason=f"持仓中，等待平仓信号",
                )
            return Signal(
                type=SignalType.HOLD,
                symbol=self.symbol,
                price=current_price,
                amount=0,
                confidence=1.0,
                reason=f"等待挂单成交",
            )

        # 2. 检查持仓状态
        if self.current_position:
            close_signal = self._check_close_conditions(current_price)
            if close_signal:
                return close_signal

            # 检查是否需要设置止损
            self._check_stop_loss_update(current_price)

        # 3. 没有持仓，检查是否可以开仓
        if not self.current_position:
            entry_signal = self._check_entry_conditions(current_price)
            if entry_signal:
                return entry_signal

        return Signal(
            type=SignalType.HOLD,
            symbol=self.symbol,
            price=current_price,
            amount=0,
            confidence=1.0,
            reason=self._get_hold_reason(current_price),
        )

    def _check_entry_conditions(self, current_price: float) -> Optional[Signal]:
        """检查开仓条件"""
        # 有持仓时不开新仓
        if self.current_position:
            return None

        # 检查冷却时间
        if self.last_trade_time:
            seconds_since = (datetime.now() - self.last_trade_time).total_seconds()
            if seconds_since < self.cooldown_seconds:
                return None

        # 获取K线数据
        ohlcv = self.get_market_data(self.kline_interval, 50)
        if len(ohlcv) < max(self.ema_slow + 5, self.bollinger_period + 5, 15):
            return None

        closes = [k[4] for k in ohlcv]
        highs = [k[2] for k in ohlcv]
        lows = [k[3] for k in ohlcv]

        # 计算市场状态
        adx = self._calculate_adx(ohlcv)
        rsi = self._calculate_rsi(closes, self.rsi_period)
        upper_band, middle_band, lower_band = self._calculate_bollinger(closes)

        # 计算EMA（使用前一根K线数据检测金叉/死叉）
        ema_fast_val = self._calculate_ema(closes, self.ema_fast)
        ema_slow_val = self._calculate_ema(closes, self.ema_slow)

        # 前一根K线的EMA值
        prev_closes = closes[:-1]
        if len(prev_closes) >= self.ema_slow:
            prev_ema_fast = self._calculate_ema(prev_closes, self.ema_fast)
            prev_ema_slow = self._calculate_ema(prev_closes, self.ema_slow)
        else:
            prev_ema_fast = ema_fast_val
            prev_ema_slow = ema_slow_val

        confidence = 0.8

        if adx > self.adx_threshold:
            # ========== 趋势模式 ==========
            # EMA金叉 -> 做多 (fast从下方穿越slow)
            if prev_ema_fast <= prev_ema_slow and ema_fast_val > ema_slow_val:
                confidence += 0.15
                amount = self._calculate_position_amount(current_price)
                # 限价挂单价格
                limit_price = current_price * (1 - self.limit_offset)
                return Signal(
                    type=SignalType.BUY,
                    symbol=self.symbol,
                    price=limit_price,
                    amount=amount,
                    confidence=confidence,
                    reason=f"趋势模式-EMA金叉 ADX={adx:.1f} RSI={rsi:.1f}",
                )

            # EMA死叉 -> 做空 (fast从上方穿越slow)
            if prev_ema_fast >= prev_ema_slow and ema_fast_val < ema_slow_val:
                confidence += 0.15
                amount = self._calculate_position_amount(current_price)
                limit_price = current_price * (1 + self.limit_offset)
                return Signal(
                    type=SignalType.SELL,
                    symbol=self.symbol,
                    price=limit_price,
                    amount=amount,
                    confidence=confidence,
                    reason=f"趋势模式-EMA死叉 ADX={adx:.1f} RSI={rsi:.1f}",
                )

        else:
            # ========== 震荡模式 ==========
            # RSI超卖 + 价格碰布林下轨 -> 做多
            if rsi < self.rsi_oversold and current_price <= lower_band:
                confidence += 0.15
                amount = self._calculate_position_amount(current_price)
                limit_price = current_price * (1 - self.limit_offset)
                return Signal(
                    type=SignalType.BUY,
                    symbol=self.symbol,
                    price=limit_price,
                    amount=amount,
                    confidence=confidence,
                    reason=f"震荡模式-RSI超卖+布林下轨 RSI={rsi:.1f}",
                )

            # RSI超买 + 价格碰布林上轨 -> 做空
            if rsi > self.rsi_overbought and current_price >= upper_band:
                confidence += 0.15
                amount = self._calculate_position_amount(current_price)
                limit_price = current_price * (1 + self.limit_offset)
                return Signal(
                    type=SignalType.SELL,
                    symbol=self.symbol,
                    price=limit_price,
                    amount=amount,
                    confidence=confidence,
                    reason=f"震荡模式-RSI超买+布林上轨 RSI={rsi:.1f}",
                )

        return None

    def _get_actual_pnl(self, current_price: float) -> float:
        """计算实际盈亏(USDT)"""
        if not self.current_position:
            return 0.0
        pos = self.current_position
        if pos.side == 'long':
            pnl_pct = (current_price - pos.entry_price) / pos.entry_price
        else:
            pnl_pct = (pos.entry_price - current_price) / pos.entry_price
        # 实际盈利 = 仓位价值 * 盈亏比例
        position_size = pos.amount * pos.entry_price
        return pnl_pct * position_size

    def _check_close_conditions(self, current_price: float) -> Optional[Signal]:
        """检查平仓条件"""
        if not self.current_position:
            return None

        pos = self.current_position
        ticker = self._market.get_ticker(self.symbol)
        mark_price = ticker.get('last', current_price)

        # 计算盈亏
        if pos.side == 'long':
            pnl_pct = (mark_price - pos.entry_price) / pos.entry_price
            close_type = SignalType.SELL
            price_cond = mark_price <= pos.stop_loss_price
        else:
            pnl_pct = (pos.entry_price - mark_price) / pos.entry_price
            close_type = SignalType.BUY
            price_cond = mark_price >= pos.stop_loss_price

        # 计算实际盈利(USDT)
        actual_pnl = self._get_actual_pnl(mark_price)
        remaining = pos.amount - self._get_closed_amount(pos)

        # ========== 止盈检查(按实际收益) ==========
        # 第一止盈
        if not pos.take_profit_1_triggered and actual_pnl >= self.take_profit_1:
            close_amount = pos.amount * self.take_profit_1_ratio
            pos.take_profit_1_triggered = True
            return Signal(
                type=close_type,
                symbol=self.symbol,
                price=0,  # 市价单
                amount=close_amount,
                confidence=0.95,
                reason=f"止盈1: +{actual_pnl:.2f}U (平{self.take_profit_1_ratio*100:.0f}%)",
            )

        # 第二止盈
        if not pos.take_profit_2_triggered and actual_pnl >= self.take_profit_2:
            if remaining > 0:
                pos.take_profit_2_triggered = True
                return Signal(
                    type=close_type,
                    symbol=self.symbol,
                    price=0,  # 市价单
                    amount=remaining,
                    confidence=0.95,
                    reason=f"止盈2: +{actual_pnl:.2f}U (平剩余)",
                )

        # ========== 止损检查 ==========
        if price_cond and remaining > 0:
            return Signal(
                type=close_type,
                symbol=self.symbol,
                price=0,  # 市价单
                amount=remaining,
                confidence=0.9,
                reason=f"止损: {pnl_pct:.2%}",
            )

        return None

    def _check_stop_loss_update(self, current_price: float):
        """检查是否需要更新止损价（保本）"""
        if not self.current_position:
            return

        pos = self.current_position
        ticker = self._market.get_ticker(self.symbol)
        mark_price = ticker.get('last', current_price)

        # 当 mark_price > entry_price + fees*2 时，止损移至 entry + fees
        fee_rate = self._get_fee_rate()
        breakeven_price = pos.entry_price * (1 + fee_rate * 2)

        if not pos.breakeven_set:
            if pos.side == 'long' and mark_price > breakeven_price:
                pos.stop_loss_price = pos.entry_price * (1 + fee_rate)
                pos.breakeven_set = True
                logger.info(f"{self.name}: 保本止损已设置 @ {pos.stop_loss_price:.4f}")
            elif pos.side == 'short' and mark_price < breakeven_price:
                pos.stop_loss_price = pos.entry_price * (1 - fee_rate)
                pos.breakeven_set = True
                logger.info(f"{self.name}: 保本止损已设置 @ {pos.stop_loss_price:.4f}")

    def _get_closed_amount(self, pos: AdaptivePosition) -> float:
        """获取已平仓数量"""
        closed = 0
        if pos.take_profit_1_triggered:
            closed += pos.amount * self.take_profit_1_ratio
        if pos.take_profit_2_triggered:
            # 第二止盈平的是剩余的 (1 - take_profit_1_ratio) * amount
            closed += pos.amount * (1 - self.take_profit_1_ratio)
        return min(closed, pos.amount)  # 确保不超过总数量

    def _calculate_position_amount(self, current_price: float) -> float:
        """计算开仓数量"""
        position_value = self.position_value * self.leverage
        amount = position_value / current_price
        precision = Config.get_precision(self.symbol)
        return round(amount, precision.get('quantity', 4))

    def _get_fee_rate(self) -> float:
        """获取手续费率（单边）"""
        return 0.0004

    def _calculate_adx(self, ohlcv: List, period: int = 14) -> float:
        """计算ADX"""
        if len(ohlcv) < period + 1:
            return 0

        highs = [k[2] for k in ohlcv]
        lows = [k[3] for k in ohlcv]
        closes = [k[4] for k in ohlcv]

        tr_list = []
        plus_dm_list = []
        minus_dm_list = []

        for i in range(1, len(ohlcv)):
            high = highs[i]
            low = lows[i]
            prev_high = highs[i-1]
            prev_low = lows[i-1]
            prev_close = closes[i-1]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_list.append(tr)

            plus_dm = max(high - prev_high, 0) if (high - prev_high) > (prev_low - low) else 0
            minus_dm = max(prev_low - low, 0) if (prev_low - low) > (high - prev_high) else 0

            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)

        if len(tr_list) < period:
            return 0

        tr_sum = sum(tr_list[:period])
        plus_dm_sum = sum(plus_dm_list[:period])
        minus_dm_sum = sum(minus_dm_list[:period])

        for i in range(period, len(tr_list)):
            tr_sum = tr_sum - tr_sum/period + tr_list[i]
            plus_dm_sum = plus_dm_sum - plus_dm_sum/period + plus_dm_list[i]
            minus_dm_sum = minus_dm_sum - minus_dm_sum/period + minus_dm_list[i]

        if tr_sum == 0:
            return 0

        plus_di = (plus_dm_sum / tr_sum) * 100
        minus_di = (minus_dm_sum / tr_sum) * 100

        if plus_di + minus_di == 0:
            dx = 0
        else:
            dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100

        return dx

    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """计算EMA"""
        if len(prices) < period:
            return prices[-1] if prices else 0

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period

        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """计算RSI"""
        if len(prices) < period + 1:
            return 50.0

        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        if len(gains) < period:
            return 50.0

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_bollinger(self, prices: List[float]):
        """计算布林带"""
        if len(prices) < self.bollinger_period:
            return prices[-1], prices[-1], prices[-1]

        period_prices = prices[-self.bollinger_period:]
        middle = sum(period_prices) / len(period_prices)

        variance = sum((p - middle) ** 2 for p in period_prices) / len(period_prices)
        std = variance ** 0.5

        upper = middle + std * self.bollinger_std
        lower = middle - std * self.bollinger_std

        return upper, middle, lower

    def _get_hold_reason(self, current_price: float) -> str:
        """获取观望原因"""
        reasons = []

        if self.current_position:
            pnl_pct = 0
            if self.current_position.side == 'long':
                pnl_pct = (current_price - self.current_position.entry_price) / self.current_position.entry_price
            else:
                pnl_pct = (self.current_position.entry_price - current_price) / self.current_position.entry_price

            reasons.append(f"持仓:{self.current_position.side} {pnl_pct:.2%}")
            if self.current_position.breakeven_set:
                reasons.append("保本止损")
        else:
            reasons.append("等待信号")

        if self.last_trade_time:
            seconds_since = (datetime.now() - self.last_trade_time).total_seconds()
            if seconds_since < self.cooldown_seconds:
                reasons.append(f"冷却{int(self.cooldown_seconds - seconds_since)}秒")

        return ", ".join(reasons)

    def _close_position(self, reason: str = "手动平仓"):
        """平仓"""
        if not self.current_position:
            return

        self.current_position = None
        self.trades_today += 1
        self.last_trade_time = datetime.now()
        self._save_state()

        logger.info(f"{self.name}: 平仓完成({reason}), 今日:{self.trades_today}次")

    def execute(self, signal: Signal = None) -> Dict:
        """执行交易信号"""
        if signal is None:
            signal = self.analyze()

        # 处理市价平仓单(price=0) - 止盈止损
        if signal.type in [SignalType.BUY, SignalType.SELL] and signal.price == 0:
            from core.futures_client import get_futures_client
            from config.settings import Config

            client = get_futures_client()
            precision = Config.get_precision(self.symbol)
            qty_precision = precision.get('quantity', 3)
            rounded_amount = round(signal.amount, qty_precision)

            try:
                # 设置杠杆
                client.set_leverage(self.symbol, self.leverage)

                # 下市价单
                if signal.type == SignalType.BUY:
                    order = client.market_buy(self.symbol, rounded_amount)
                    action = 'buy'
                else:
                    order = client.market_sell(self.symbol, rounded_amount)
                    action = 'sell'

                logger.info(f"{self.name}: 市价{action}成功 {rounded_amount}")

                # 保存交易记录
                self._data.save_trade({
                    'order_id': order.get('orderId'),
                    'symbol': signal.symbol,
                    'side': action,
                    'order_type': 'market',
                    'price': 0,
                    'amount': signal.amount,
                    'total': rounded_amount * (self.current_position.entry_price if self.current_position else 0),
                    'strategy': self.name,
                    'order_id_exchange': order.get('orderId'),
                    'status': 'closed',
                })

                # 更新策略统计
                self._data.update_strategy_stats(self.name, 0)

                return {
                    'success': True,
                    'result': order,
                    'signal': {
                        'type': signal.type.value,
                        'symbol': signal.symbol,
                        'price': 0,
                        'amount': signal.amount,
                        'reason': signal.reason,
                    }
                }

            except Exception as e:
                logger.error(f"{self.name}: 市价{'买入' if signal.type == SignalType.BUY else '卖出'}失败: {e}")
                return {
                    'success': False,
                    'error': str(e),
                    'result': {},
                    'signal': {}
                }

        # 处理限价挂单
        if signal.type in [SignalType.BUY, SignalType.SELL] and signal.price > 0:
            from core.futures_client import get_futures_client
            from config.settings import Config

            client = get_futures_client()
            precision = Config.get_precision(self.symbol)
            price_precision = precision.get('price', 2)
            qty_precision = precision.get('quantity', 3)

            # 修正精度
            rounded_price = round(signal.price, price_precision)
            rounded_amount = round(signal.amount, qty_precision)

            try:
                # 设置杠杆
                client.set_leverage(self.symbol, self.leverage)

                # 下限价单
                if signal.type == SignalType.BUY:
                    order = client.limit_buy(self.symbol, rounded_amount, rounded_price)
                else:
                    order = client.limit_sell(self.symbol, rounded_amount, rounded_price)

                # 记录挂单
                self.pending_order = PendingOrder(
                    order_id=str(order.get('orderId', '')),
                    side='long' if signal.type == SignalType.BUY else 'short',
                    price=rounded_price,
                    amount=rounded_amount,
                    created_time=datetime.now(),
                    signal_reason=signal.reason,
                )
                self._save_state()

                logger.info(f"{self.name}: 挂单成功 {self.pending_order.side} @ {rounded_price}, 数量:{rounded_amount}, 订单ID:{self.pending_order.order_id}")

                return {
                    'success': True,
                    'result': {'orderId': order.get('orderId'), 'status': 'NEW'},
                    'signal': {
                        'type': signal.type.value,
                        'symbol': signal.symbol,
                        'price': signal.price,
                        'amount': signal.amount,
                        'reason': signal.reason,
                    }
                }

            except Exception as e:
                logger.error(f"{self.name}: 挂单失败: {e}")
                return {
                    'success': False,
                    'error': str(e),
                    'result': {},
                    'signal': {}
                }

        # 处理其他信号(HOLD等)
        result = super().execute(signal)

        # 检查是否完全平仓
        if self.current_position and self._get_closed_amount(self.current_position) >= self.current_position.amount:
            self.current_position = None
            self.trades_today += 1
            self.last_trade_time = datetime.now()
            self._save_state()

        return result

    def get_status(self) -> Dict:
        """获取策略状态"""
        base_status = super().get_status()

        ticker = self._market.get_ticker(self.symbol)
        current_price = ticker.get('last', 0)

        # 获取市场数据
        ohlcv = self.get_market_data(self.kline_interval, 50)
        closes = [k[4] for k in ohlcv] if ohlcv else []
        adx = self._calculate_adx(ohlcv) if len(ohlcv) >= 15 else 0
        rsi = self._calculate_rsi(closes, self.rsi_period) if len(closes) >= self.rsi_period + 1 else 50
        upper, middle, lower = self._calculate_bollinger(closes)

        # 持仓状态
        position_status = {}
        if self.current_position:
            pnl_pct = 0
            if self.current_position.side == 'long':
                pnl_pct = (current_price - self.current_position.entry_price) / self.current_position.entry_price
            else:
                pnl_pct = (self.current_position.entry_price - current_price) / self.current_position.entry_price
            actual_pnl = self._get_actual_pnl(current_price)

            position_status = {
                'side': self.current_position.side,
                'entry_price': self.current_position.entry_price,
                'current_price': current_price,
                'pnl_pct': pnl_pct,
                'actual_pnl': actual_pnl,
                'amount': self.current_position.amount,
                'stop_loss_price': self.current_position.stop_loss_price,
                'take_profit_1_triggered': self.current_position.take_profit_1_triggered,
                'take_profit_2_triggered': self.current_position.take_profit_2_triggered,
                'breakeven_set': self.current_position.breakeven_set,
            }

        # 挂单状态
        pending_status = {}
        if self.pending_order:
            elapsed = (datetime.now() - self.pending_order.created_time).total_seconds()
            remaining = max(0, self.pending_timeout - elapsed)
            pending_status = {
                'side': self.pending_order.side,
                'price': self.pending_order.price,
                'amount': self.pending_order.amount,
                'elapsed_seconds': int(elapsed),
                'remaining_seconds': int(remaining),
                'reason': self.pending_order.signal_reason,
            }

        # 判断市场模式
        market_mode = 'trend' if adx > self.adx_threshold else 'oscillation'

        adaptive_status = {
            'adaptive': {
                'position': position_status,
                'pending_order': pending_status,
                'trades_today': self.trades_today,
                'market_mode': market_mode,
                'adx': adx,
                'rsi': rsi,
                'bollinger': {
                    'upper': upper,
                    'middle': middle,
                    'lower': lower,
                },
                'params': {
                    'leverage': self.leverage,
                    'position_value': self.position_value,
                    'stop_loss_pct': self.stop_loss_pct,
                    'take_profit_1': self.take_profit_1,
                    'take_profit_2': self.take_profit_2,
                    'pending_timeout': self.pending_timeout,
                    'cooldown_seconds': self.cooldown_seconds,
                },
            }
        }

        return {**base_status, **adaptive_status}
