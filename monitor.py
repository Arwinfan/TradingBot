#!/usr/bin/env python3
"""
TradingBot 策略监控脚本
功能：
1. 检查所有策略运行状态
2. 检测异常情况（订单失败、数据异常等）
3. 自动尝试修复常见问题
"""

import sys
import os
import time
import json
import requests
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

API_BASE = "http://localhost/api"

def get_strategies():
    """获取所有策略状态"""
    try:
        resp = requests.get(f"{API_BASE}/strategies", timeout=5)
        return resp.json().get('strategies', [])
    except Exception as e:
        print(f"❌ 获取策略列表失败: {e}")
        return []

def check_strategy_issues(strategy):
    """检查单个策略的问题"""
    issues = []
    name = strategy.get('name', '')
    status = strategy.get('status', '')
    params = strategy.get('params', {})
    symbol = params.get('symbol', '?')
    
    # 基础检查
    if status != 'running':
        return []  # 停止的策略不检查
    
    # 检查策略特定问题
    if name == 'AdaptiveStrategy':
        adaptive = strategy.get('adaptive', {})
        market_mode = adaptive.get('market_mode')
        adx = adaptive.get('adx', 0)
        rsi = adaptive.get('rsi', 0)
        
        # 检查市场数据是否正常
        if adx == 0 and rsi == 0:
            issues.append({
                'severity': 'high',
                'type': 'no_market_data',
                'message': f'市场数据异常 (ADX=0, RSI=0)',
                'action': '检查网络和API连接'
            })
        
        # 检查挂单状态
        pending = adaptive.get('pending_order', {})
        if pending:
            elapsed = time.time() - time.mktime(time.strptime(
                pending.get('created_time', time.strftime('%Y-%m-%d %H:%M:%S')), 
                '%Y-%m-%d %H:%M:%S'
            ))
            if elapsed > 300:  # 超过5分钟
                issues.append({
                    'severity': 'medium',
                    'type': 'stale_pending_order',
                    'message': f'挂单超过5分钟未成交',
                    'action': '可能需要撤销重挂'
                })
        
        # 检查持仓
        position = adaptive.get('position', {})
        if position:
            pnl_pct = position.get('pnl_pct', 0)
            if pnl_pct < -0.05:  # 亏损超过5%
                issues.append({
                    'severity': 'high',
                    'type': 'large_loss',
                    'message': f'持仓亏损 {pnl_pct*100:.1f}%',
                    'action': '检查止损设置'
                })
    
    elif name == 'ScalpingStrategy':
        scalping = strategy.get('scalping', {})
        volatility = scalping.get('volatility', 0)
        
        if volatility == 0:
            issues.append({
                'severity': 'medium',
                'type': 'no_volatility_data',
                'message': '波动率数据为0',
                'action': '检查市场数据API'
            })
    
    # 检查统计
    stats = strategy.get('stats', {})
    total_trades = stats.get('total_trades', 0)
    total_pnl = stats.get('total_pnl', 0)
    
    return issues

def restart_strategy(strategy_type):
    """重启策略"""
    try:
        # 先停止
        requests.post(
            f"{API_BASE}/strategy",
            json={"action": "stop", "strategy_type": strategy_type},
            timeout=5
        )
        time.sleep(1)
        # 再启动
        resp = requests.post(
            f"{API_BASE}/strategy",
            json={"action": "start", "strategy_type": strategy_type},
            timeout=5
        )
        return resp.json().get('success', False)
    except Exception as e:
        print(f"重启失败: {e}")
        return False

def main():
    print("="*60)
    print(f"TradingBot 策略监控")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    strategies = get_strategies()
    if not strategies:
        print("❌ 无法获取策略列表")
        return
    
    all_issues = []
    running_count = 0
    
    for s in strategies:
        name = s.get('name', '')
        status = s.get('status', '')
        params = s.get('params', {})
        symbol = params.get('symbol', '?')
        stats = s.get('stats', {})
        pnl = stats.get('total_pnl', 0)
        trades = stats.get('total_trades', 0)
        
        icon = '🟢' if status == 'running' else '⚪'
        print(f"{icon} [{name}] {symbol}")
        print(f"   状态: {status} | 交易: {trades} | 盈亏: {pnl:+.2f}U")
        
        if status == 'running':
            running_count += 1
        
        issues = check_strategy_issues(s)
        if issues:
            for issue in issues:
                severity_icon = '🔴' if issue['severity'] == 'high' else '🟡'
                print(f"   {severity_icon} {issue['message']}")
                print(f"      建议: {issue['action']}")
                all_issues.append((name, issue))
    
    print()
    print(f"运行中: {running_count}/{len(strategies)}")
    
    if all_issues:
        print()
        print("⚠️ 发现问题:")
        high_count = sum(1 for _, i in all_issues if i['severity'] == 'high')
        medium_count = sum(1 for _, i in all_issues if i['severity'] == 'medium')
        print(f"  🔴 高优先级: {high_count}")
        print(f"  🟡 中优先级: {medium_count}")
        
        # 尝试自动修复
        for name, issue in all_issues:
            if issue['severity'] == 'high' and issue['type'] == 'no_market_data':
                print(f"\n尝试重启 {name}...")
                strategy_map = {
                    'AdaptiveStrategy': 'adaptive',
                    'ScalpingStrategy': 'scalping',
                    'GridStrategy': 'grid',
                    'DCAStrategy': 'dca',
                    'TrendStrategy': 'trend',
                    'FundingArbitrageStrategy': 'funding',
                }
                if name in strategy_map:
                    if restart_strategy(strategy_map[name]):
                        print(f"  ✅ 重启成功")
                    else:
                        print(f"  ❌ 重启失败")
    else:
        print()
        print("✅ 未发现问题")

if __name__ == "__main__":
    main()
