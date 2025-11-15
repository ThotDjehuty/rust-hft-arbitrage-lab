# Using Finnhub with HFT Arbitrage Lab

## Quick Start

### 1. Get Your Free API Key

Visit https://finnhub.io/register and sign up for a free account. You'll receive an API key with:
- ✅ 60 API calls per minute
- ✅ Real-time quotes for stocks, crypto, and forex
- ✅ WebSocket support for streaming data

### 2. Set Up Your Environment

**Option A: Environment Variable (Recommended)**
```bash
export FINNHUB_API_KEY=your_key_here
```

Add to your shell profile (`~/.zshrc` or `~/.bash_profile`):
```bash
echo 'export FINNHUB_API_KEY=your_key_here' >> ~/.zshrc
source ~/.zshrc
```

**Option B: Enter When Prompted**

Notebooks and apps will prompt for the API key if not found in environment.

### 3. Run Examples

#### Jupyter Notebooks

```bash
# Start Jupyter
jupyter notebook

# Or use the project script
./scripts/start_jupyter.sh

# Open any notebook in examples/notebooks/
# They will automatically use Finnhub if configured
```

#### Streamlit Apps

**Market Data Explorer:**
```bash
streamlit run app/streamlit_app.py
```
1. Select "finnhub" connector (default)
2. Enter API key in sidebar
3. Choose a symbol (e.g., BINANCE:BTCUSDT)
4. Click "Fetch snapshot now"

**Strategy Backtesting:**
```bash
streamlit run app/streamlit_strategies.py
```
1. Go to "⚡ Strategy Execution" tab
2. Choose a strategy (e.g., Pairs Trading)
3. Select "Finnhub (Real)" as data source
4. Enter API key
5. Click "🚀 Run Backtest"

## Supported Symbols

### Crypto (most common)
```python
'BINANCE:BTCUSDT'   # Bitcoin
'BINANCE:ETHUSDT'   # Ethereum
'BINANCE:BNBUSDT'   # Binance Coin
'BINANCE:ADAUSDT'   # Cardano
'BINANCE:SOLUSDT'   # Solana
'COINBASE:BTC-USD'  # Bitcoin on Coinbase
'COINBASE:ETH-USD'  # Ethereum on Coinbase
```

### Stocks
```python
'AAPL'   # Apple
'GOOGL'  # Google
'MSFT'   # Microsoft
'TSLA'   # Tesla
'AMZN'   # Amazon
```

### Forex
```python
'OANDA:EUR_USD'
'OANDA:GBP_USD'
'OANDA:USD_JPY'
```

## Python API Usage

### Fetch Real-Time Quotes

```python
from python.finnhub_helper import fetch_realtime_quotes, get_finnhub_api_key

api_key = get_finnhub_api_key()
symbols = ['BINANCE:BTCUSDT', 'BINANCE:ETHUSDT']

# Fetch current quotes
df = fetch_realtime_quotes(symbols, api_key=api_key, duration_seconds=30)

print(df.head())
# Output:
#   timestamp              symbol          bid      ask      mid
# 0 2024-01-15 10:00:00   BINANCE:BTCUSDT  50000.0  50001.0  50000.5
# 1 2024-01-15 10:00:01   BINANCE:ETHUSDT  3000.0   3001.0   3000.5
```

### Generate Historical Simulation

```python
from python.finnhub_helper import fetch_historical_simulation

# Generates synthetic historical data based on current prices
df = fetch_historical_simulation(
    symbols=['BINANCE:BTCUSDT', 'BINANCE:ETHUSDT'],
    periods=1000,
    api_key=api_key
)

print(df.columns)
# Output: ['timestamp', 'BINANCE:BTCUSDT_mid', 'BINANCE:ETHUSDT_mid']

# Use for backtesting
prices_btc = df['BINANCE:BTCUSDT_mid'].values
prices_eth = df['BINANCE:ETHUSDT_mid'].values
```

### Create Orderbook from Quote

```python
from python.finnhub_helper import create_orderbook_from_quote

# Convert bid/ask to orderbook format
ob = create_orderbook_from_quote(bid=50000.0, ask=50001.0, size=1.0)

print(ob)
# Output: {'bids': [[50000.0, 1.0]], 'asks': [[50001.0, 1.0]]}
```

## Troubleshooting

### No API Key Error

**Error:** `No Finnhub API key provided. Using demo mode with synthetic data.`

**Solutions:**
1. Set environment variable: `export FINNHUB_API_KEY=your_key`
2. Pass API key directly: `api_key="your_key"`
3. Enter when prompted in notebook

### Rate Limit Exceeded

**Error:** API returns 429 status code

**Solutions:**
1. Free tier: 60 calls/minute - wait 60 seconds
2. Reduce `periods` parameter in simulations
3. Use caching to avoid repeated calls
4. Upgrade to paid plan for higher limits

### Symbol Not Found

**Error:** `Failed to fetch {symbol}`

**Solutions:**
1. Check symbol format: Must include exchange prefix
   - ✅ Correct: `'BINANCE:BTCUSDT'`
   - ❌ Wrong: `'BTCUSDT'`
2. Verify symbol exists on Finnhub
3. Try alternative exchange: `'COINBASE:BTC-USD'`

### Import Error

**Error:** `Could not import Finnhub helper`

**Solutions:**
1. Check file exists: `python/finnhub_helper.py`
2. Add parent directory to path:
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).parent.parent))
   ```
3. Run from project root directory

### WebSocket Connection Issues

**Error:** `websocket-client` module not found

**Solution:**
```bash
pip install websocket-client>=1.6.0
```

## Best Practices

### 1. Cache API Responses

```python
import functools
import time

@functools.lru_cache(maxsize=100)
def cached_fetch(symbol, timestamp_minute):
    """Cache responses for 1 minute"""
    return fetch_realtime_quotes([symbol], api_key=api_key)

# Use with current minute as cache key
current_minute = int(time.time() / 60)
df = cached_fetch('BINANCE:BTCUSDT', current_minute)
```

### 2. Respect Rate Limits

```python
import time

symbols = ['BINANCE:BTCUSDT', 'BINANCE:ETHUSDT', 'BINANCE:BNBUSDT']

for symbol in symbols:
    df = fetch_realtime_quotes([symbol], api_key=api_key)
    time.sleep(1.1)  # 60 calls/min = 1 per second + margin
```

### 3. Handle Errors Gracefully

```python
try:
    df = fetch_historical_simulation(symbols, api_key=api_key)
except Exception as e:
    print(f"Finnhub fetch failed: {e}")
    # Fall back to synthetic data
    df = generate_synthetic_data(symbols)
```

### 4. Use Environment Variables

```python
import os

# Check if running in production
if os.getenv('PRODUCTION'):
    api_key = os.environ['FINNHUB_API_KEY']
else:
    api_key = get_finnhub_api_key()  # Prompt in dev
```

## Advanced Usage

### Custom Historical Data Generation

```python
from python.finnhub_helper import fetch_realtime_quotes
import pandas as pd
import numpy as np

# Fetch current price as starting point
current = fetch_realtime_quotes(['BINANCE:BTCUSDT'], api_key=api_key)
start_price = current['mid'].iloc[0]

# Generate custom historical series
timestamps = pd.date_range(end=pd.Timestamp.now(), periods=1000, freq='5min')
returns = np.random.randn(1000) * 0.01  # 1% volatility
prices = start_price * (1 + returns).cumprod()

df = pd.DataFrame({
    'timestamp': timestamps,
    'BINANCE:BTCUSDT_mid': prices
})
```

### Multiple Exchange Comparison

```python
symbols = ['BINANCE:BTCUSDT', 'COINBASE:BTC-USD']
df = fetch_realtime_quotes(symbols, api_key=api_key)

# Calculate arbitrage opportunity
binance_price = df[df['symbol'] == 'BINANCE:BTCUSDT']['mid'].iloc[0]
coinbase_price = df[df['symbol'] == 'COINBASE:BTC-USD']['mid'].iloc[0]

spread = abs(binance_price - coinbase_price)
spread_pct = spread / binance_price * 100

print(f"Spread: ${spread:.2f} ({spread_pct:.2f}%)")
```

### Real-Time Streaming (Advanced)

```python
from python.connectors.finnhub import FinnhubConnector

connector = FinnhubConnector(api_key)

# Start WebSocket stream
connector.start_stream(['BINANCE:BTCUSDT'])

# Poll for updates
while True:
    ob = connector.fetch_orderbook_sync('BINANCE:BTCUSDT')
    print(f"Bid: {ob['bids'][0][0]}, Ask: {ob['asks'][0][0]}")
    time.sleep(1)
```

## Resources

- **Finnhub API Docs**: https://finnhub.io/docs/api
- **Free API Key**: https://finnhub.io/register
- **Symbol Search**: https://finnhub.io/docs/api/symbol-search
- **Rate Limits**: https://finnhub.io/pricing
- **WebSocket API**: https://finnhub.io/docs/api/websocket-trades

## Support

For issues specific to this project:
- Check `FINNHUB_INTEGRATION.md` for implementation details
- See `python/finnhub_helper.py` for source code
- Review notebooks in `examples/notebooks/` for usage examples

For Finnhub API issues:
- Email: support@finnhub.io
- Discord: https://finnhub.io/discord
- GitHub: https://github.com/Finnhub-Stock-API
