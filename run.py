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
from signals import get_signal_service
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


def signal_scanner_runner():
    """信号扫描线程 - 后台扫描技术信号"""
    signal_service = get_signal_service()
    
    # 注册信号回调
    def on_new_signals(signals):
        logger.info(f"[信号扫描] 发现 {len(signals)} 个交易信号")
        for sig in signals:
            # 发送警报
            signal_service.alert_manager.signal_alert(sig)
            logger.info(f"  - {sig.symbol}: {sig.side.value} @ {sig.entry_price} ({sig.confidence:.0%} 置信度)")
    
    signal_service.register_strategy_callback(on_new_signals)
    
    # 启动服务
    import asyncio
    try:
        asyncio.run(signal_service.start())
    except KeyboardInterrupt:
        signal_service.stop()


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
    print(f"信号扫描: {'开启' if Config.SIGNAL_SCANNER_ENABLED else '关闭'} (间隔 {Config.SIGNAL_SCAN_INTERVAL}秒)")
    print(f"警报系统: {'开启' if Config.ALERT_ENABLED else '关闭'}")
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

    # 启动信号扫描线程
    if Config.SIGNAL_SCANNER_ENABLED:
        signal_thread = threading.Thread(target=signal_scanner_runner, daemon=True)
        signal_thread.start()
        logger.info("信号扫描线程已启动")

    # 启动服务
    run_app()
