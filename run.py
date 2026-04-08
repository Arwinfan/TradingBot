#!/usr/bin/env python3
"""
TradingBot 启动文件
"""

import sys
import os
import threading
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import run_app
from config.settings import Config
from strategies import get_strategy_manager
from utils.logger import get_logger

logger = get_logger(__name__)


def strategy_runner():
    """策略自动执行线程"""
    manager = get_strategy_manager()
    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            if Config.STRATEGY_ENABLED:
                # 运行所有正在运行的策略
                results = manager.run_all()
                for name, result in results.items():
                    if result and result.get('success'):
                        signal = result.get('signal', {})
                        action = signal.get('type') if signal else None
                        if action in ['buy', 'sell']:
                            # 检查实际执行结果
                            exec_result = result.get('result', {})
                            if exec_result.get('success'):
                                logger.info(f"[自动交易] {name}: {action.upper()} {signal.get('symbol')} @ {signal.get('price')} - 执行成功")
                            else:
                                logger.warning(f"[自动交易] {name}: {action.upper()} {signal.get('symbol')} - 执行失败: {exec_result.get('error', '未知错误')}")
                consecutive_errors = 0

            time.sleep(Config.STRATEGY_INTERVAL)

        except Exception as e:
            consecutive_errors += 1
            logger.error(f"策略执行出错 ({consecutive_errors}/{max_consecutive_errors}): {e}")
            if consecutive_errors >= max_consecutive_errors:
                logger.warning("连续错误次数过多，暂停策略执行 60 秒")
                time.sleep(60)
                consecutive_errors = 0
            else:
                time.sleep(10)


def log_cleanup_runner():
    """日志清理线程 - 每7天清理一次旧日志"""
    from core.data_service import get_data_service

    data_service = get_data_service()
    cleanup_interval_days = 7
    cleanup_interval_seconds = cleanup_interval_days * 24 * 60 * 60

    while True:
        try:
            logger.info(f"开始清理 {cleanup_interval_days} 天前的旧日志...")
            deleted = data_service.clean_old_logs(days=cleanup_interval_days)
            logger.info(f"日志清理完成，删除了 {deleted} 条记录")
        except Exception as e:
            logger.error(f"日志清理出错: {e}")

        time.sleep(cleanup_interval_seconds)


if __name__ == '__main__':
    print("=" * 50)
    print("TradingBot")
    print("=" * 50)
    print()

    print(f"项目路径: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"测试网模式: {'开启' if Config.USE_TESTNET else '关闭'}")
    print(f"API配置: {'已配置' if Config.is_configured() else '未配置'}")
    print(f"Web服务: http://{Config.WEB_HOST}:{Config.WEB_PORT}")
    print(f"策略自动执行: {'开启' if Config.STRATEGY_ENABLED else '关闭'} (间隔 {Config.STRATEGY_INTERVAL}秒)")
    print()
    print("=" * 50)

    # 启动策略执行线程
    if Config.STRATEGY_ENABLED:
        strategy_thread = threading.Thread(target=strategy_runner, daemon=True)
        strategy_thread.start()
        logger.info("策略自动执行线程已启动")

    # 启动日志清理线程 (每7天清理一次)
    cleanup_thread = threading.Thread(target=log_cleanup_runner, daemon=True)
    cleanup_thread.start()
    logger.info("日志清理线程已启动 (每7天清理一次)")

    # 启动服务
    run_app()
