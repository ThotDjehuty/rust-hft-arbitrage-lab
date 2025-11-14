# Connectors Guide

## Overview

This project supports multiple exchange connectors with authentication:

### Available Connectors

1. **binance** - Binance public data (via Rust)
2. **binance_auth** - Binance with authentication (Python wrapper)
3. **coinbase** - Coinbase public data (via Rust)
4. **coinbase_auth** - Coinbase Pro with authentication (Python wrapper)
5. **finnhub** - Finnhub real-time market data (Python)
6. **uniswap** - Uniswap DEX data (via Rust)
7. **mock** - Mock connector for testing

## Authentication

### Binance Authenticated

```python
from python.rust_bridge import get_connector

connector = get_connector(
    "binance_auth",
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# Get account info
account = connector.get_account_info()

# Place order
order = connector.place_order(
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    quantity=0.001,
    price=50000.0
)
```

### Coinbase Authenticated

```python
connector = get_connector(
    "coinbase_auth",
    api_key="your_api_key",
    api_secret="your_api_secret",
    passphrase="your_passphrase"
)

# Get accounts
accounts = connector.get_accounts()

# Place order
order = connector.place_order(
    product_id="BTC-USD",
    side="buy",
    order_type="limit",
    size=0.001,
    price=50000.0
)
```

### Finnhub

Get a free API key from https://finnhub.io/

```python
connector = get_connector(
    "finnhub",
    api_key="your_finnhub_api_key"
)

# List available symbols
symbols = connector.list_symbols()

# Fetch orderbook (synthetic from quote data)
ob = connector.fetch_orderbook_sync("BINANCE:BTCUSDT")

# Start real-time stream
def on_update(orderbook):
    print(f"Bid: {orderbook['bids'][0][0]}, Ask: {orderbook['asks'][0][0]}")

connector.start_stream("BINANCE:BTCUSDT", on_update)
```

## Using in Streamlit

The Streamlit UI automatically detects which connectors require authentication:

1. Select connector from dropdown
2. Enter API credentials when prompted
3. The app will instantiate the correct connector type

## Strategy Execution

Run strategies from notebooks in the Streamlit UI:

```bash
streamlit run app/streamlit_strategies.py
```

Available strategies:
- Triangular Arbitrage
- Pairs Trading
- Market Making
- Market Making with Order Book Imbalance
- Statistical Arbitrage
- Hawkes Process Market Making
- Portfolio Hedging

Each strategy has configurable parameters and supports backtesting with synthetic or historical data.
