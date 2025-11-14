# Quick Start Guide - New Features

## What's New

### 1. Authenticated Connectors
Python wrappers that add authentication to Rust connectors for live trading:

- **binance_auth** - Authenticated Binance API (place orders, check balances)
- **coinbase_auth** - Authenticated Coinbase Pro API

### 2. Finnhub Connector
Real-time market data from Finnhub (free tier available):
- WebSocket streaming for live quotes
- Supports stocks, crypto, and forex
- Get your free API key: https://finnhub.io/

### 3. Strategy Execution Framework
Run notebook strategies through a user-friendly interface:
- 7 strategies available: Triangular Arbitrage, Pairs Trading, Market Making, etc.
- Backtest with synthetic or historical data
- Visualize performance metrics (Sharpe, drawdown, equity curve)

### 4. Enhanced Streamlit UI
Two apps for different purposes:

**A. Market Data Collection** (`streamlit_app.py`)
```bash
streamlit run app/streamlit_app.py
```
- Connect to any exchange
- Collect live orderbook snapshots
- Visualize bid/ask spreads

**B. Strategy Execution** (`streamlit_strategies.py`)
```bash
streamlit run app/streamlit_strategies.py
```
- Select and configure strategies
- Run backtests with custom parameters
- View live performance (demo mode)

## Usage Examples

### Using Finnhub Connector

```python
from python.rust_bridge import get_connector

# Get your free API key from https://finnhub.io/
connector = get_connector("finnhub", api_key="YOUR_API_KEY")

# Fetch current orderbook (synthetic from quotes)
ob = connector.fetch_orderbook_sync("BINANCE:BTCUSDT")
print(f"Bid: {ob['bids'][0][0]}, Ask: {ob['asks'][0][0]}")

# Start real-time stream
def on_update(orderbook):
    bid, ask = orderbook['bids'][0][0], orderbook['asks'][0][0]
    print(f"Live update - Bid: {bid}, Ask: {ask}")

connector.start_stream("BINANCE:BTCUSDT", on_update)
```

### Running Strategies

```python
from python.strategies import StrategyExecutor, StrategyConfig
import pandas as pd
import numpy as np

# Generate synthetic market data
timestamps = pd.date_range(start='2024-01-01', periods=1000, freq='5min')
market_data = pd.DataFrame({
    'timestamp': timestamps,
    'BTC/USD_mid': 100 * (1 + np.random.randn(1000) * 0.02).cumprod(),
    'ETH/USD_mid': 50 * (1 + np.random.randn(1000) * 0.025).cumprod(),
})

# Configure and run strategy
config = StrategyConfig(
    strategy_name="pairs_trading",
    parameters={
        "symbol_a": "BTC/USD",
        "symbol_b": "ETH/USD",
        "lookback_periods": 60,
        "z_entry_threshold": 2.0,
        "z_exit_threshold": 0.5,
        "position_size": 1.0,
    },
    initial_capital=100000.0
)

executor = StrategyExecutor(config)
results = executor.run_pairs_trading(market_data)

print(f"Total Return: {results['total_return_pct']:.2f}%")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {results['max_drawdown_pct']:.2f}%")
```

### Using Authenticated Connectors

```python
# Binance authenticated
connector = get_connector(
    "binance_auth",
    api_key="your_key",
    api_secret="your_secret"
)

# Check account balance
account = connector.get_account_info()
print(account['balances'][:3])

# Place a limit order
order = connector.place_order(
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    quantity=0.001,
    price=50000.0
)
print(f"Order placed: {order['orderId']}")
```

## Available Strategies

1. **Triangular Arbitrage** - Exploit price discrepancies across 3 pairs
2. **Pairs Trading** - Statistical arbitrage on correlated pairs
3. **Market Making** - Provide liquidity with inventory management
4. **Market Making with Imbalance** - MM using order book flow prediction
5. **Statistical Arbitrage** - Mean reversion on multiple assets
6. **Hawkes Market Making** - MM with order flow intensity modeling
7. **Portfolio Hedging** - Dynamic delta hedging

## Installation

Update dependencies:
```bash
pip install -r docker/requirements.txt
```

Key packages added:
- `websocket-client>=1.6.0` - For Finnhub WebSocket streaming
- `streamlit` - Already included
- `plotly` - Already included

## Free API Keys

**Finnhub** (recommended for backtesting):
- Sign up: https://finnhub.io/
- Free tier: 60 calls/minute
- Supports: Stocks, Crypto, Forex

**Binance** (for live data):
- Create account: https://www.binance.com/
- Generate API key in account settings
- Enable spot trading permissions only (disable withdrawals for safety)

**Coinbase Pro** (alternative):
- Create account: https://pro.coinbase.com/
- Generate API key with view + trade permissions
- Requires API key, secret, AND passphrase

## Next Steps

1. Get a free Finnhub API key
2. Run the strategy UI: `streamlit run app/streamlit_strategies.py`
3. Select a strategy and configure parameters
4. Run backtest to see performance
5. Experiment with different parameters

## Safety Notes

⚠️ **Important**: 
- Start with paper trading / demo mode
- Never share your API keys
- For live trading, use API keys with limited permissions
- Test strategies thoroughly before using real funds
- The live trading feature is for demonstration only

## Troubleshooting

**ImportError: No module named 'websocket'**
```bash
pip install websocket-client
```

**Finnhub connection fails**
- Check your API key is valid
- Verify you haven't exceeded rate limits (60 calls/min on free tier)
- Try a different symbol

**Strategy backtest shows no trades**
- Increase the number of periods
- Adjust entry/exit thresholds
- Check market data has sufficient volatility

## Documentation

- Connectors guide: `python/connectors/README.md`
- Strategy definitions: `python/strategies/definitions.py`
- Notebook examples: `examples/notebooks/`
