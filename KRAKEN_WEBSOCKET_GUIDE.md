# Kraken Support & WebSocket Streaming - Implementation Guide

## Changes Made

### 1. Added Kraken to Rust Connector

**File: `rust_connector/src/lib.rs`**

#### Added Kraken to connector list:
```rust
fn list_connectors() -> Vec<String> {
    vec![
        "binance".to_string(), 
        "coinbase".to_string(), 
        "kraken".to_string(),  // NEW
        "uniswap".to_string(), 
        "mock".to_string()
    ]
}
```

#### Added Kraken symbols:
```rust
} else if lower.contains("kraken") {
    Ok(vec!["XBTUSDT".to_string(), "ETHUSDT".to_string(), "XXBTZUSD".to_string()])
```

#### Added Kraken REST API support in `fetch_orderbook_sync()`:
- URL: `https://api.kraken.com/0/public/Depth?pair={symbol}&count=5`
- Added `parse_kraken_rest()` function to parse Kraken's unique response format
- Kraken format: `{"result": {"XBTUSDT": {"bids": [...], "asks": [...]}}}`

#### Added Kraken WebSocket support in `start_stream()`:
- URL: `wss://ws.kraken.com`
- Subscribe message: `{"event": "subscribe", "pair": [symbol], "subscription": {"name": "book", "depth": 10}}`
- Added `parse_kraken_ws_text()` function to parse WebSocket messages
- Kraken WS format: Arrays with book data `[channelID, {"as": [[price, vol, ts]], "bs": [[price, vol, ts]]}, ...]`

### 2. Added Kraken Authentication Support

**File: `python/connectors/authenticated.py`**

Created `AuthenticatedKraken` class:
- Auto-loads credentials from `api_keys.properties`
- Implements Kraken's unique signature scheme (HMAC-SHA512 with base64)
- Methods:
  - `get_account_balance()` - Fetch account balances
  - `place_order()` - Place orders with authentication
  - `fetch_orderbook_sync()` - Public orderbook (delegates to Rust)
  - `start_stream()` - WebSocket streaming (delegates to Rust)

**File: `python/api_keys.py`**

Added convenience function:
```python
def get_kraken_credentials() -> tuple[Optional[str], Optional[str]]:
    return (get_api_key('KRAKEN_API_KEY'), get_api_key('KRAKEN_API_SECRET'))
```

**File: `python/rust_bridge.py`**

- Added `"kraken_auth"` to connector list
- Added handler for `kraken_auth` in `get_connector()`

### 3. WebSocket Streaming Support

The Rust connector already has WebSocket streaming via `start_stream()` method. However, Streamlit doesn't expose this directly in the UI.

**How WebSocket streaming works:**
1. Call `connector.start_stream(symbol, callback)` 
2. Rust spawns a background tokio task
3. Callback receives `OrderBook` objects in real-time
4. Use `connector.latest_snapshot()` to get most recent data

**Current Streamlit implementation:**
- Uses polling with `fetch_orderbook_sync()` every N milliseconds
- Does NOT use WebSocket streaming

## Rebuild Instructions

After making Rust changes, rebuild the connector:

```bash
cd /Users/melvinalvarez/Documents/Workspace/rust-hft-arbitrage-lab
maturin develop --manifest-path rust_connector/Cargo.toml
```

Then restart Streamlit:
```bash
streamlit run app/streamlit_app.py
```

## Testing Kraken

### 1. Setup API Keys

Edit `api_keys.properties`:
```properties
KRAKEN_API_KEY=your_kraken_key_here
KRAKEN_API_SECRET=your_kraken_secret_here
```

### 2. Test in Streamlit

1. Open Connectors & Live Market Data
2. Select "kraken" from dropdown (for public data)
3. Select "kraken_auth" from dropdown (for authenticated endpoints)
4. Choose symbol: XBTUSDT, ETHUSDT, or XXBTZUSD
5. Click "Fetch snapshot now" to test REST API
6. Enable "Collect market snapshots continuously" for polling

### 3. Test WebSocket Streaming (Python Console)

```python
from python.rust_bridge import get_connector

def on_orderbook(ob):
    print(f"Received orderbook: bid={ob.bids[0][0]}, ask={ob.asks[0][0]}")

connector = get_connector("kraken")
connector.start_stream("XBTUSDT", on_orderbook)

# Stream runs in background
# Check latest snapshot
snapshot = connector.latest_snapshot()
print(snapshot)
```

## Kraken-Specific Notes

### Symbol Format
Kraken uses unique symbol names:
- `XBTUSDT` - Bitcoin/Tether
- `ETHUSDT` - Ethereum/Tether  
- `XXBTZUSD` - Bitcoin/USD
- Check Kraken API docs for full list

### API Authentication
Kraken uses:
- Header: `API-Key: <your_key>`
- Header: `API-Sign: <signature>`
- Signature = Base64(HMAC-SHA512(urlpath + SHA256(nonce + postdata), base64_decode(api_secret)))

### Rate Limits
- Public API: 1 request/second (may vary)
- Private API: Check your tier limits
- WebSocket: Generally more generous

## Next Steps

To fully enable WebSocket streaming in Streamlit:

1. **Add streaming toggle** - Add checkbox "Use WebSocket streaming" 
2. **Start stream on enable** - Call `connector.start_stream(symbol, callback)`
3. **Display streaming data** - Use `connector.latest_snapshot()` instead of `fetch_orderbook_sync()`
4. **Add streaming indicator** - Show "🔴 LIVE" badge when streaming
5. **Handle reconnection** - Restart stream if connection drops

Would you like me to implement the WebSocket streaming UI in Streamlit?
