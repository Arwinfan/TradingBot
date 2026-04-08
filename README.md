# TradingBot

基于 Flask 的量化交易机器人，提供实时行情监控、策略交易和风险管理功能。

## 功能特性

- **实时行情监控**: 支持多个交易对的实时价格、K线图、订单簿
- **多种交易策略**:
  - 网格策略: 在震荡行情中低买高卖
  - 定投策略: 定期定额买入，平均成本
  - 趋势策略: 跟随MACD/RSI信号顺势交易
- **交易功能**: 市价单、限价单、止损止盈
- **风险管理**: 单笔金额限制、持仓限制、余额检查
- **Web界面**: 仪表盘、交易面板、策略管理、设置页面
- **数据存储**: SQLite数据库存储交易记录和策略状态

## 技术栈

- **后端**: Python 3.8+, Flask, CCXT
- **数据库**: SQLite
- **前端**: Bootstrap 5, Chart.js
- **实时通信**: Flask-SocketIO

## 安装

### 1. 克隆项目

```bash
git clone <repository-url>
cd binance_trading_system
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量 (可选)

```bash
# Linux/Mac
export BINANCE_API_KEY="your_api_key"
export BINANCE_API_SECRET="your_api_secret"

# Windows (PowerShell)
$env:BINANCE_API_KEY="your_api_key"
$env:BINANCE_API_SECRET="your_api_secret"
```

或者直接在 `config/settings.py` 中修改配置。

### 5. 运行

```bash
python run.py
```

访问 http://localhost:5000

## 配置说明

### API配置

在 `config/settings.py` 中配置:

```python
# API密钥
BINANCE_API_KEY = 'your_api_key'
BINANCE_API_SECRET = 'your_api_secret'

# 是否使用测试网 (强烈建议测试时开启)
USE_TESTNET = True
```

### 交易配置

```python
# 支持的交易对
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']

# 风险管理
MAX_TRADE_AMOUNT = 1000         # 单笔最大金额 (USDT)
MAX_POSITION_PER_SYMBOL = 5000  # 单币种最大持仓 (USDT)
```

### 策略参数

各策略的默认参数在 `config/strategies.py` 中定义。

## 使用指南

### 1. 仪表盘

主页显示:
- 各交易对的实时行情
- 账户余额
- 当前持仓和盈亏
- K线走势图
- 策略运行状态

### 2. 交易

**手动交易**:
1. 选择交易对
2. 选择订单类型 (市价/限价)
3. 输入数量或金额
4. 点击买入/卖出

**策略交易**:
1. 启动策略
2. 策略将自动分析市场并执行交易
3. 可手动运行策略查看信号

### 3. 策略说明

#### 网格策略
- 设置价格区间和网格数量
- 价格下跌到网格线时买入，上涨时卖出
- 适合震荡行情

#### 定投策略
- 设置定投金额和间隔时间
- 定期自动买入
- 适合长期投资

#### 趋势策略
- 基于MACD金叉死叉和RSI超买超卖
- 趋势确认后顺势交易
- 带有止损和追踪止损

### 4. 设置

- **API配置**: 设置币安API密钥
- **交易配置**: 调整风险参数
- **数据管理**: 清理旧日志

## 注意事项

1. **安全提示**:
   - 请勿将API密钥提交到公共仓库
   - 建议仅使用只读权限的API密钥
   - 启用IP白名单限制

2. **风险提示**:
   - 量化交易存在风险，请谨慎操作
   - 建议先在测试网/模拟盘验证策略
   - 合理设置止损和仓位限制

3. **测试网**:
   - 测试时可开启 `USE_TESTNET = True`
   - 测试网API: https://testnet.binance.vision

## 目录结构

```
binance_trading_system/
├── config/           # 配置
│   ├── settings.py   # 主配置
│   └── strategies.py # 策略配置
├── core/             # 核心服务
│   ├── api_client.py
│   ├── market_service.py
│   ├── trade_service.py
│   └── data_service.py
├── strategies/       # 交易策略
│   ├── base_strategy.py
│   ├── grid_strategy.py
│   ├── dca_strategy.py
│   └── trend_strategy.py
├── web/              # Web应用
│   ├── app.py
│   ├── routes/
│   └── templates/
├── utils/            # 工具函数
│   ├── logger.py
│   ├── indicators.py
│   └── validators.py
├── data/             # 数据存储
├── logs/             # 日志
├── run.py            # 启动文件
└── requirements.txt
```

## License

MIT License
