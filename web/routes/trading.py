"""
交易路由 - 交易操作相关
"""

from flask import render_template, jsonify, request
from datetime import datetime

from . import trading_bp
from config.settings import Config
from config.strategies import StrategyConfig
from strategies import get_strategy_manager, GridStrategy, DCAStrategy, TrendStrategy, FundingArbitrageStrategy, ScalpingStrategy, AdaptiveStrategy
from utils.logger import get_logger

logger = get_logger(__name__)


@trading_bp.route('/trading')
def index():
    """交易页面"""
    return render_template('trading.html',
                          symbols=Config.SYMBOLS)


@trading_bp.route('/api/order', methods=['POST'])
def place_order():
    """
    下单

    请求参数:
        - symbol: 交易对 (如 BTCUSDT)
        - side: BUY/SELL
        - type: market/limit
        - amount: 数量
        - price: 价格 (限价单必填)
    """
    from core.futures_client import get_futures_client

    client = get_futures_client()

    data = request.get_json()

    symbol = data.get('symbol')
    side = data.get('side', '').upper()
    order_type = data.get('type', 'market')
    amount = float(data.get('amount', 0))
    price = float(data.get('price', 0))

    if not all([symbol, side, amount]):
        return jsonify({
            'success': False,
            'error': '缺少必要参数',
        }), 400

    try:
        if order_type == 'market':
            if side == 'BUY':
                result = client.market_buy(symbol, amount)
            else:
                result = client.market_sell(symbol, amount)
        else:
            if price <= 0:
                return jsonify({
                    'success': False,
                    'error': '限价单需要指定价格',
                }), 400

            if side == 'BUY':
                result = client.limit_buy(symbol, amount, price)
            else:
                result = client.limit_sell(symbol, amount, price)

        return jsonify({
            'success': True,
            'message': f"{'买入' if side == 'BUY' else '卖出'}成功",
            'data': result,
        })

    except Exception as e:
        logger.error(f"下单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@trading_bp.route('/api/order/<order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    """取消订单"""
    from core.futures_client import get_futures_client

    client = get_futures_client()

    data = request.get_json()
    symbol = data.get('symbol')

    try:
        result = client.cancel_order(symbol, order_id)

        return jsonify({
            'success': True,
            'message': '订单已取消',
        })

    except Exception as e:
        logger.error(f"取消订单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@trading_bp.route('/api/order/close', methods=['POST'])
def close_position():
    """平仓"""
    from core.futures_client import get_futures_client, APIError
    from utils.logger import get_logger

    _logger = get_logger(__name__)

    data = request.get_json()
    symbol = data.get('symbol')
    side = data.get('side')
    quantity = data.get('quantity')
    order_type = data.get('type', 'market')
    price = data.get('price')

    _logger.info(f"收到平仓请求: symbol={symbol}, side={side}, quantity={quantity}, type={order_type}")

    if not symbol or not side:
        return jsonify({
            'success': False,
            'error': '缺少参数',
        }), 400

    if order_type == 'limit' and (price is None or price <= 0):
        return jsonify({
            'success': False,
            'error': '限价平仓需要指定价格',
        }), 400

    client = get_futures_client()

    try:
        result = client.close_position(symbol, side, quantity=quantity,
                                     order_type=order_type, price=price)
        _logger.info(f"平仓结果: {result}")
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': '平仓成功',
                'result': result,
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '平仓失败'),
            }), 400
    except APIError as e:
        _logger.error(f"平仓API失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500
    except Exception as e:
        _logger.error(f"平仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@trading_bp.route('/api/open-orders')
def get_open_orders():
    """获取未完成订单"""
    from core.futures_client import get_futures_client

    client = get_futures_client()

    symbol = request.args.get('symbol')

    try:
        orders = client.get_open_orders(symbol)
        return jsonify({
            'success': True,
            'orders': orders,
        })
    except Exception as e:
        logger.error(f"获取未完成订单失败: {e}")
        return jsonify({
            'success': False,
            'orders': [],
        })


@trading_bp.route('/api/strategy', methods=['POST'])
def manage_strategy():
    """
    管理策略

    请求参数:
        - action: start/stop/run/update
        - strategy_type: grid/dca/trend
        - params: 策略参数 (可选)
    """
    data = request.get_json()

    action = data.get('action')
    strategy_type = data.get('strategy_type')
    params = data.get('params', {})

    if not action or not strategy_type:
        return jsonify({
            'success': False,
            'error': '缺少必要参数',
        }), 400

    manager = get_strategy_manager()

    # 确保策略已注册
    strategy_map = {
        'grid': GridStrategy,
        'dca': DCAStrategy,
        'trend': TrendStrategy,
        'funding': FundingArbitrageStrategy,
        'scalping': ScalpingStrategy,
        'adaptive': AdaptiveStrategy,
    }
    for stype, strategy_class in strategy_map.items():
        if not manager.get_strategy(strategy_class.__name__):
            manager.register(strategy_class())

    try:
        if action == 'start':
            # 检查策略是否已注册
            existing = manager.get_strategy(strategy_type)
            if existing:
                # 如果传入了新参数，先更新参数再启动
                if params:
                    existing.update_params(params)
                # 启动策略
                manager.start_strategy(strategy_type)
                return jsonify({
                    'success': True,
                    'message': f"{existing.name} 已启动",
                    'strategy': existing.get_status(),
                })

            # 未注册的策略，创建新实例
            strategy_class = strategy_map.get(strategy_type)
            if not strategy_class:
                return jsonify({
                    'success': False,
                    'error': f"未知的策略类型: {strategy_type}",
                }), 400

            # 使用传入的参数或默认参数创建新实例
            strategy = strategy_class(params)
            manager.register(strategy)
            manager.start_strategy(strategy.name)

            return jsonify({
                'success': True,
                'message': f"{strategy.name} 已启动",
                'strategy': strategy.get_status(),
            })

        elif action == 'stop':
            manager.stop_strategy(strategy_type)
            return jsonify({
                'success': True,
                'message': f"{strategy_type} 策略已停止",
            })

        elif action == 'run':
            result = manager.run_strategy(strategy_type)
            return jsonify({
                'success': True,
                'result': result,
            })

        elif action == 'update':
            strategy = manager.get_strategy(strategy_type)
            if strategy:
                strategy.update_params(params)
                return jsonify({
                    'success': True,
                    'message': '参数已更新',
                    'strategy': strategy.get_status(),
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f"策略不存在: {strategy_type}",
                }), 400

        else:
            return jsonify({
                'success': False,
                'error': f"未知操作: {action}",
            }), 400

    except Exception as e:
        logger.error(f"策略操作失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@trading_bp.route('/api/strategies')
def get_strategies():
    """获取所有策略"""
    manager = get_strategy_manager()

    # 注册默认策略(如果未注册)
    if not manager.get_strategy('GridStrategy'):
        grid = GridStrategy()
        manager.register(grid)

    if not manager.get_strategy('DCAStrategy'):
        dca = DCAStrategy()
        manager.register(dca)

    if not manager.get_strategy('TrendStrategy'):
        trend = TrendStrategy()
        manager.register(trend)

    if not manager.get_strategy('FundingArbitrageStrategy'):
        funding = FundingArbitrageStrategy()
        manager.register(funding)

    if not manager.get_strategy('ScalpingStrategy'):
        scalping = ScalpingStrategy()
        manager.register(scalping)

    if not manager.get_strategy('AdaptiveStrategy'):
        adaptive = AdaptiveStrategy()
        manager.register(adaptive)

    strategies = manager.list_strategies()

    return jsonify({
        'success': True,
        'strategies': strategies,
    })


@trading_bp.route('/api/strategy/<name>')
def get_strategy(name):
    """获取单个策略详情"""
    manager = get_strategy_manager()

    strategy = manager.get_strategy(name)

    if strategy:
        return jsonify({
            'success': True,
            'strategy': strategy.get_status(),
        })
    else:
        return jsonify({
            'success': False,
            'error': f"策略不存在: {name}",
        }), 404


@trading_bp.route('/api/strategy/<name>/logs')
def get_strategy_logs(name):
    """获取策略运行日志"""
    from core.data_service import get_data_service
    from strategies import get_strategy_manager

    data = get_data_service()
    manager = get_strategy_manager()

    # 获取策略实例的当前交易对
    strategy = manager.get_strategy(name)
    symbol = None
    if strategy:
        symbol = strategy.symbol

    # 获取策略交易记录 - 按策略名和当前交易对过滤
    limit = request.args.get('limit', 50, type=int)
    if symbol:
        trades = data.get_trades(strategy=name, symbol=symbol, limit=limit)
        summary = data.get_trade_summary(strategy=name, symbol=symbol)
    else:
        trades = data.get_trades(strategy=name, limit=limit)
        summary = data.get_trade_summary(strategy=name)

    # 获取策略状态
    state = data.get_strategy_state(name)

    return jsonify({
        'success': True,
        'strategy': name,
        'state': state,
        'trades': trades,
        'summary': summary,
    })


@trading_bp.route('/api/risk-check', methods=['POST'])
def risk_check():
    """
    风险检查

    请求参数:
        - symbol: 交易对
        - amount: 数量
        - side: BUY/SELL
    """
    from core.futures_client import get_futures_client

    client = get_futures_client()

    data = request.get_json()

    symbol = data.get('symbol')
    amount = float(data.get('amount', 0))
    side = data.get('side', '').upper()

    if not all([symbol, amount, side]):
        return jsonify({
            'success': False,
            'error': '缺少必要参数',
        }), 400

    try:
        # 获取当前价格
        price = client.get_price(symbol)

        # 获取持仓
        position = client.get_position(symbol)

        checks = []

        # 持仓检查
        if side == 'SELL':
            if not position or position['size'] < amount:
                checks.append({
                    'type': '持仓检查',
                    'passed': False,
                    'message': f"持仓不足",
                })
            else:
                checks.append({
                    'type': '持仓检查',
                    'passed': True,
                    'message': f"可卖出: {position['size']}",
                })
        else:
            checks.append({
                'type': '持仓检查',
                'passed': True,
                'message': f"做多",
            })

        # 余额检查
        balance = client.get_balance()
        available = balance.get('free', {}).get('USDT', 0)
        order_value = amount * price

        if side == 'BUY':
            if order_value > available:
                checks.append({
                    'type': '余额检查',
                    'passed': False,
                    'message': f"余额不足: {available:.2f} < {order_value:.2f}",
                })
            else:
                checks.append({
                    'type': '余额检查',
                    'passed': True,
                    'message': f"可用: {available:.2f}",
                })

        all_passed = all(c['passed'] for c in checks)

        return jsonify({
            'success': True,
            'passed': all_passed,
            'checks': checks,
            'summary': {
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': price,
                'value': order_value,
            },
        })

    except Exception as e:
        logger.error(f"风险检查失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@trading_bp.route('/api/leverage', methods=['POST'])
def set_leverage():
    """设置杠杆"""
    from core.futures_client import get_futures_client

    client = get_futures_client()

    data = request.get_json()

    symbol = data.get('symbol')
    leverage = int(data.get('leverage', 10))

    try:
        result = client.set_leverage(symbol, leverage)
        return jsonify({
            'success': True,
            'message': f'{symbol} 杠杆已设置为 {leverage}x',
            'data': result,
        })
    except Exception as e:
        logger.error(f"设置杠杆失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500
