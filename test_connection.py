#!/usr/bin/env python3
"""
测试币安API连接 (支持现货和期货)
运行: python test_connection.py
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import Config
import ccxt

def test_connection():
    print("=" * 50)
    print("币安API连接测试")
    print("=" * 50)

    # 检查配置
    print("\n[1] 配置检查:")
    print(f"    交易模式: {'期货 (Futures)' if Config.is_futures() else '现货 (Spot)'}")
    print(f"    API Key: {'已配置' if Config.API_KEY else '未配置'}")
    print(f"    测试网: {'是' if Config.USE_TESTNET else '否'}")
    print(f"    代理: {Config.HTTP_PROXY or '无'}")

    if not Config.API_KEY or not Config.API_SECRET:
        print("\n    ❌ 请先配置API密钥!")
        return False

    # 创建期货交易所实例
    print("\n[2] 初始化期货交易所...")

    proxy = Config.HTTP_PROXY if Config.HTTP_PROXY else None

    if Config.USE_TESTNET:
        exchange = ccxt.binance({
            'apiKey': Config.API_KEY,
            'secret': Config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'futures',
                'testnet': True,
            },
        })
        if proxy:
            exchange.proxies = {'http': proxy, 'https': proxy}
        print("    ✓ 已连接测试网期货API")
    else:
        exchange = ccxt.binance({
            'apiKey': Config.API_KEY,
            'secret': Config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'futures',
            },
        })
        if proxy:
            exchange.proxies = {'http': proxy, 'https': proxy}
        print("    ✓ 已连接主网期货API")

    # 测试获取行情 (公共接口)
    print("\n[3] 测试获取行情数据...")
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']

    success_count = 0
    for symbol in symbols:
        try:
            ticker = exchange.fetch_ticker(symbol)
            change = ticker.get('percentage', 0)
            print(f"    ✓ {symbol}: ${ticker['last']:,.2f} ({change:+.2f}%)")
            success_count += 1
        except ccxt.NetworkError as e:
            print(f"    ❌ {symbol}: 网络错误 - {str(e)[:80]}...")
        except ccxt.ExchangeError as e:
            print(f"    ❌ {symbol}: 交易所错误 - {str(e)[:80]}")
        except Exception as e:
            print(f"    ❌ {symbol}: 未知错误 - {str(e)[:80]}")

    if success_count > 0:
        print(f"\n    ✓ 成功获取 {success_count}/{len(symbols)} 个交易对行情")

    # 测试获取余额
    print("\n[4] 测试获取账户余额...")
    try:
        balance = exchange.fetch_balance()
        # 期货账户USDT余额
        usdt_info = balance.get('USDT', {})
        usdt_free = usdt_info.get('free', 0)
        usdt_total = usdt_info.get('total', 0) or usdt_free
        print(f"    ✓ USDT 可用: {usdt_free}")
        print(f"    ✓ USDT 总计: {usdt_total}")
    except ccxt.AuthenticationError as e:
        print(f"    ⚠️ 认证错误: {str(e)[:80]}")
        print("    提示: 密钥可能无效或权限不足")
    except ccxt.NetworkError as e:
        print(f"    ❌ 网络错误 - {str(e)[:80]}")
    except Exception as e:
        print(f"    ⚠️ 获取余额: {str(e)[:80]}")

    # 测试获取持仓
    print("\n[5] 测试获取期货持仓...")
    try:
        positions = exchange.fetch_positions()
        if positions:
            print(f"    ✓ 当前有 {len(positions)} 个持仓")
            for pos in positions:
                print(f"      - {pos.get('symbol')}: {pos.get('size')} 张, 盈亏: {pos.get('unrealizedPnl', 0):.2f}")
        else:
            print("    ✓ 无持仓 (空仓)")
    except ccxt.AuthenticationError as e:
        print(f"    ⚠️ 认证错误: {str(e)[:80]}")
    except Exception as e:
        print(f"    ⚠️ 获取持仓: {str(e)[:80]}")

    print("\n" + "=" * 50)

    if success_count > 0:
        print("✓ 期货API连接成功!")
        print("  Web界面可以正常显示期货行情")
    else:
        print("❌ 无法连接到币安期货API")
        print("  请检查网络或密钥配置")

    print("=" * 50)
    return success_count > 0

if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)
