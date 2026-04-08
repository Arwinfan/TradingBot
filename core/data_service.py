"""
数据服务 - 负责数据存储和持久化
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class DataService:
    """
    数据服务类
    负责交易记录、持仓记录、策略状态等的持久化存储
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
        self._db_path = Config.DATABASE_PATH
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(self._db_path), check_same_thread=False)

    def _init_database(self):
        """初始化数据库表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                price REAL,
                amount REAL,
                total REAL,
                fee REAL DEFAULT 0,
                fee_currency TEXT,
                strategy TEXT,
                order_id_exchange TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 持仓记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                amount REAL DEFAULT 0,
                avg_price REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 策略状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_type TEXT UNIQUE NOT NULL,
                params TEXT,
                status TEXT DEFAULT 'stopped',
                last_run TIMESTAMP,
                total_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 系统日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 风险记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS risk_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                action TEXT,
                amount REAL,
                reason TEXT,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs(level)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_created ON system_logs(created_at)')

        conn.commit()
        conn.close()

        logger.info(f"数据库初始化完成: {self._db_path}")

    # ==================== 交易记录 ====================

    def save_trade(self, trade_data: Dict) -> int:
        """
        保存交易记录

        Args:
            trade_data: 交易数据字典

        Returns:
            记录ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO trades (
                order_id, symbol, side, order_type, price, amount, total,
                fee, fee_currency, strategy, order_id_exchange, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data.get('order_id'),
            trade_data['symbol'],
            trade_data['side'],
            trade_data['order_type'],
            trade_data.get('price'),
            trade_data['amount'],
            trade_data.get('total'),
            trade_data.get('fee', 0),
            trade_data.get('fee_currency'),
            trade_data.get('strategy'),
            trade_data.get('order_id_exchange'),
            trade_data.get('status', 'pending'),
        ))

        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.debug(f"交易记录已保存: {trade_id}")
        return trade_id

    def update_trade(self, trade_id: int, updates: Dict):
        """更新交易记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        for key, value in updates.items():
            cursor.execute(
                f'UPDATE trades SET {key} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (value, trade_id)
            )

        conn.commit()
        conn.close()

    def get_trades(self, symbol: str = None, strategy: str = None,
                   start_date: str = None, end_date: str = None,
                   limit: int = 100) -> List[Dict]:
        """
        获取交易记录

        Args:
            symbol: 交易对
            strategy: 策略类型
            start_date: 开始日期
            end_date: 结束日期
            limit: 数量限制

        Returns:
            交易记录列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM trades WHERE 1=1'
        params = []

        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol)

        if strategy:
            query += ' AND strategy = ?'
            params.append(strategy)

        if start_date:
            query += ' AND created_at >= ?'
            params.append(start_date)

        if end_date:
            query += ' AND created_at <= ?'
            params.append(end_date)

        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        return [dict(zip(columns, row)) for row in rows]

    def get_trade_summary(self, symbol: str = None, strategy: str = None) -> Dict:
        """
        获取交易汇总

        Args:
            symbol: 交易对
            strategy: 策略类型

        Returns:
            汇总数据
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN side = 'buy' THEN total ELSE 0 END) as total_buy,
                SUM(CASE WHEN side = 'sell' THEN total ELSE 0 END) as total_sell,
                SUM(CASE WHEN side = 'sell' THEN total - (amount * price) ELSE 0 END) as total_pnl,
                SUM(fee) as total_fees
            FROM trades
            WHERE status = 'closed'
        '''
        params = []

        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol)

        if strategy:
            query += ' AND strategy = ?'
            params.append(strategy)

        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()

        return {
            'total_trades': row[0] or 0,
            'total_buy': row[1] or 0,
            'total_sell': row[2] or 0,
            'total_pnl': row[3] or 0,
            'total_fees': row[4] or 0,
        }

    # ==================== 持仓记录 ====================

    def save_position(self, symbol: str, amount: float, avg_price: float):
        """保存持仓记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO positions (symbol, amount, avg_price, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (symbol, amount, avg_price))

        conn.commit()
        conn.close()

    def get_positions(self) -> List[Dict]:
        """获取所有持仓记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM positions WHERE amount > 0')
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        return [dict(zip(columns, row)) for row in rows]

    # ==================== 策略状态 ====================

    def save_strategy_state(self, strategy_type: str, params: Dict,
                            status: str = 'stopped'):
        """保存策略状态"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO strategy_states
            (strategy_type, params, status, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (strategy_type, json.dumps(params), status))

        conn.commit()
        conn.close()

    def get_strategy_state(self, strategy_type: str) -> Optional[Dict]:
        """获取策略状态"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            'SELECT * FROM strategy_states WHERE strategy_type = ?',
            (strategy_type,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, row))
            if result.get('params'):
                result['params'] = json.loads(result['params'])
            return result
        return None

    def get_all_strategy_states(self) -> List[Dict]:
        """获取所有策略状态"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM strategy_states')
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        states = []
        for row in rows:
            result = dict(zip(columns, row))
            if result.get('params'):
                result['params'] = json.loads(result['params'])
            states.append(result)

        return states

    def update_strategy_stats(self, strategy_type: str, pnl: float = 0):
        """更新策略统计"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE strategy_states
            SET total_trades = total_trades + 1,
                total_pnl = total_pnl + ?,
                last_run = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE strategy_type = ?
        ''', (pnl, strategy_type))

        conn.commit()
        conn.close()

    # ==================== 系统日志 ====================

    def log_message(self, level: str, message: str, context: Dict = None):
        """记录系统日志"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO system_logs (level, message, context)
            VALUES (?, ?, ?)
        ''', (level, message, json.dumps(context) if context else None))

        conn.commit()
        conn.close()

    def get_logs(self, level: str = None, limit: int = 100) -> List[Dict]:
        """获取系统日志"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if level:
            cursor.execute(
                'SELECT * FROM system_logs WHERE level = ? ORDER BY created_at DESC LIMIT ?',
                (level, limit)
            )
        else:
            cursor.execute(
                'SELECT * FROM system_logs ORDER BY created_at DESC LIMIT ?',
                (limit,)
            )

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        logs = []
        for row in rows:
            result = dict(zip(columns, row))
            if result.get('context'):
                try:
                    result['context'] = json.loads(result['context'])
                except json.JSONDecodeError:
                    pass
            logs.append(result)

        return logs

    def clean_old_logs(self, days: int = 30):
        """清理旧日志"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM system_logs
            WHERE created_at < datetime('now', '-' || ? || ' days')
        ''', (days,))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"已清理 {deleted} 条旧日志")
        return deleted

    # ==================== 风险记录 ====================

    def log_risk_event(self, symbol: str, action: str, amount: float,
                       reason: str, result: str):
        """记录风险事件"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO risk_records (symbol, action, amount, reason, result)
            VALUES (?, ?, ?, ?, ?)
        ''', (symbol, action, amount, reason, result))

        conn.commit()
        conn.close()


# 全局服务实例
_service = None


def get_data_service() -> DataService:
    """获取全局数据服务实例"""
    global _service
    if _service is None:
        _service = DataService()
    return _service
