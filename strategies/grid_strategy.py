"""Grid网格策略"""
from strategies.base_strategy import BaseStrategy
from utils.logger import get_logger

logger = get_logger(__name__)


class GridStrategy(BaseStrategy):
    """网格交易策略 - 高卖低买"""

    def __init__(self, config):
        super().__init__(config)
        self.upper = float(config.get('grid_upper', 2500))
        self.lower = float(config.get('grid_lower', 2000))
        self.grid_num = int(config.get('grid_num', 10))
        self.grid_pct = (self.upper - self.lower) / self.grid_num
        self.frozen = False

    def analyze(self, current_price):
        if self.frozen:
            if self.lower <= current_price <= self.upper:
                self.frozen = False
                logger.info("价格回归网格区间，解除冻结")
            else:
                return None
        if current_price > self.upper * 1.05 or current_price < self.lower * 0.95:
            logger.warning(f"价格 {current_price} 严重偏离网格，冻结策略")
            self.frozen = True
            return None
        if current_price > self.upper or current_price < self.lower:
            return None
        level = int((current_price - self.lower) / self.grid_pct)
        buy_price = self.lower + level * self.grid_pct
        sell_price = buy_price + self.grid_pct
        return {
            'action': 'grid',
            'buy_price': buy_price,
            'sell_price': sell_price,
            'level': level
        }

    def should_close_position(self, position, df):
        return False

    def execute(self, signal):
        pass
