"""
仪表盘路由 - 主页和数据展示
"""

from flask import render_template, jsonify, request
from datetime import datetime

from . import dashboard_bp
from config.settings import Config
from utils.logger import get_logger

logger = get_logger(__name__)


@dashboard_bp.route('/')
def index():
    """主页"""
    return render_template('dashboard.html',
                          symbols=Config.SYMBOLS,
                          default_symbol=Config.DEFAULT_SYMBOL)


@dashboard_bp.route('/api/dashboard')
def get_dashboard_data():
    """获取仪表盘数据"""
    from core.futures_client import get_futures_client
    from core.futures_service import get_futures_market_service
    from core.data_service import get_data_service
    from strategies import get_strategy_manager

    client = get_futures_client()
    market = get_futures_market_service()

    # 获取所有交易对的行情
    tickers = market.get_tickers(Config.SYMBOLS)

    # 获取持仓
    try:
        positions = client.get_positions()
        # 为持仓添加当前价格
        for pos in positions:
            symbol = pos.get('symbol')
            if symbol:
                ticker = market.get_ticker(symbol)
                pos['current_price'] = ticker.get('last', pos.get('entry_price', 0))
    except Exception as e:
        logger.warning(f"获取持仓失败: {e}")
        positions = []

    # 获取余额
    try:
        balance = client.get_balance()
        available_usdt = balance.get('free', {}).get('USDT', 0)
        total_usdt = balance.get('total', {}).get('USDT', available_usdt)
    except Exception as e:
        logger.warning(f"获取余额失败: {e}")
        balance = {}
        available_usdt = 0
        total_usdt = 0

    # 获取数据服务
    data = get_data_service()
    summary = data.get_trade_summary()

    # 获取策略状态
    strategy_manager = get_strategy_manager()
    strategies = strategy_manager.list_strategies()

    # 获取最近日志
    logs = data.get_logs(limit=20)

    return jsonify({
        'success': True,
        'timestamp': datetime.now().isoformat(),
        'tickers': tickers,
        'positions': positions,
        'balance': {
            'available': available_usdt,
            'total': total_usdt,
        },
        'summary': summary,
        'strategies': strategies,
        'logs': logs[-5:] if logs else [],
    })


@dashboard_bp.route('/api/market/<symbol>')
def get_market(symbol):
    """获取单个交易对的市场数据"""
    from core.futures_service import get_futures_market_service

    market = get_futures_market_service()

    try:
        ticker = market.get_ticker(symbol)
        stats = market.get_price_stats(symbol, '1h', 24)
        order_book = market.get_order_book(symbol, 10)

        return jsonify({
            'success': True,
            'ticker': ticker,
            'stats': stats,
            'order_book': order_book,
        })
    except Exception as e:
        logger.error(f"获取市场数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@dashboard_bp.route('/api/kline/<symbol>')
def get_kline(symbol):
    """获取K线数据"""
    from core.futures_service import get_futures_market_service

    market = get_futures_market_service()

    timeframe = request.args.get('timeframe', '1h')
    limit = int(request.args.get('limit', 100))

    try:
        ohlcv = market.get_ohlcv(symbol, timeframe, limit)

        # 转换为前端需要的格式
        data = []
        for k in ohlcv:
            data.append({
                'time': k[0] // 1000,  # 转换为秒
                'open': k[1],
                'high': k[2],
                'low': k[3],
                'close': k[4],
                'volume': k[5],
            })

        return jsonify({
            'success': True,
            'symbol': symbol,
            'timeframe': timeframe,
            'data': data,
        })
    except Exception as e:
        logger.error(f"获取K线失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@dashboard_bp.route('/api/positions')
def get_positions():
    """获取所有持仓"""
    from core.futures_client import get_futures_client

    client = get_futures_client()

    try:
        positions = client.get_positions()
        return jsonify({
            'success': True,
            'positions': positions,
        })
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@dashboard_bp.route('/api/balance')
def get_balance():
    """获取账户余额"""
    from core.futures_client import get_futures_client

    client = get_futures_client()

    try:
        balance = client.get_balance()
        return jsonify({
            'success': True,
            'balance': balance,
        })
    except Exception as e:
        logger.error(f"获取余额失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@dashboard_bp.route('/api/trades')
def get_trades():
    """获取交易记录"""
    from core.data_service import get_data_service

    data = get_data_service()

    symbol = request.args.get('symbol')
    limit = int(request.args.get('limit', 50))

    trades = data.get_trades(symbol=symbol, limit=limit)

    return jsonify({
        'success': True,
        'trades': trades,
    })


@dashboard_bp.route('/api/logs')
def get_logs():
    """获取系统日志"""
    from core.data_service import get_data_service

    data = get_data_service()

    level = request.args.get('level')
    limit = int(request.args.get('limit', 100))

    logs = data.get_logs(level=level, limit=limit)

    return jsonify({
        'success': True,
        'logs': logs,
    })


@dashboard_bp.route('/api/funding-rates')
def get_funding_rates():
    """获取各平台资金费率"""
    import requests
    from config.settings import Config

    result = {
        'binance': [],
        'okx': [],
        'gate': []
    }

    proxies = {}
    if Config.HTTP_PROXY:
        proxies = {
            'http': Config.HTTP_PROXY,
            'https': Config.HTTP_PROXY,
        }

    # 币安期货资金费率
    try:
        response = requests.get(
            'https://fapi.binance.com/fapi/v1/premiumIndex',
            proxies=proxies,
            timeout=10
        )
        data = response.json()
        for item in data:
            result['binance'].append({
                'symbol': item.get('symbol', ''),
                'rate': float(item.get('lastFundingRate', 0))
            })
    except Exception as e:
        logger.error(f"获取币安资金费率失败: {e}")

    # OKX资金费率 - 先获取交易对列表，再获取资金费率
    try:
        # 先获取所有SWAP交易对
        response = requests.get(
            'https://www.okx.com/api/v5/market/tickers?instType=SWAP',
            proxies=proxies,
            timeout=15
        )
        data = response.json()
        if data.get('data'):
            # 获取前50个交易对的资金费率（避免请求太多）
            symbols = []
            for item in data['data'][:50]:
                inst_id = item.get('instId', '')
                if 'USDT' in inst_id:
                    symbols.append(inst_id)

            # 批量获取资金费率
            for symbol in symbols:
                try:
                    rate_response = requests.get(
                        f'https://www.okx.com/api/v5/public/funding-rate?instId={symbol}',
                        proxies=proxies,
                        timeout=5
                    )
                    rate_data = rate_response.json()
                    if rate_data.get('data'):
                        funding_rate = float(rate_data['data'][0].get('fundingRate', 0))
                        result['okx'].append({
                            'symbol': symbol.replace('-USDT-SWAP', ''),
                            'rate': funding_rate
                        })
                except:
                    pass
    except Exception as e:
        logger.error(f"获取OKX资金费率失败: {e}")

    # Gate.io资金费率
    try:
        response = requests.get(
            'https://api.gateio.ws/api/v4/futures/usdt/contracts',
            proxies=proxies,
            timeout=10
        )
        data = response.json()
        for item in data:
            result['gate'].append({
                'symbol': item.get('name', ''),
                'rate': float(item.get('funding_rate', 0))
            })
    except Exception as e:
        logger.error(f"获取Gate资金费率失败: {e}")

    return jsonify({
        'success': True,
        'binance': result['binance'],
        'okx': result['okx'],
        'gate': result['gate'],
    })
