import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import threading
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path to import python module
sys.path.insert(0, str(Path(__file__).parent.parent))

from python.rust_bridge import list_connectors, get_connector, compute_dex_cex_arbitrage

st.set_page_config(page_title="HFT Arbitrage Lab — Connectors (Live)", layout="wide")
st.title("Connectors & Live Market Data")

# Sidebar controls
with st.sidebar:
    st.header("Live configuration")
    
    # Default to finnhub if available
    connectors = list_connectors()
    default_idx = connectors.index("finnhub") if "finnhub" in connectors else 0
    connector_name = st.selectbox("Connector", connectors, index=default_idx)

    # Credentials are auto-loaded from api_keys.properties
    st.info("📝 Credentials are loaded from `api_keys.properties`. See QUICK_CONFIG.md for setup.")
    
    # Obtain connector instance - use cached version if collecting to preserve WebSocket connection
    if st.session_state.get("collecting", False) and st.session_state.get("connector_name") == connector_name:
        connector = st.session_state["connector"]
    else:
        connector = get_connector(connector_name)
        if not st.session_state.get("collecting", False):
            # Only update if not collecting (to preserve active WebSocket)
            st.session_state["connector_name"] = connector_name
    
    symbols = connector.list_symbols() if hasattr(connector, "list_symbols") else []
    symbol = st.selectbox("Symbol", symbols)

    st.write("---")
    st.markdown("**Data Collection Mode**")
    collection_mode = st.radio(
        "Mode",
        ["Manual", "Polling (REST)", "Streaming (WebSocket)"],
        index=0,
        help="Manual: Click button to fetch. Polling: Fetch every N ms. Streaming: Real-time WebSocket."
    )
    
    if collection_mode == "Polling (REST)":
        collect_interval = st.slider("Interval (ms)", 200, 5000, 500, step=100)
        auto_collect = True
        use_websocket = False
    elif collection_mode == "Streaming (WebSocket)":
        auto_collect = True
        use_websocket = True
        collect_interval = 200  # Update UI frequently from cached snapshot
        st.info("🔴 WebSocket streaming provides real-time updates")
    else:
        auto_collect = False
        use_websocket = False
        collect_interval = 500
    st.write("---")
    st.markdown("DEX ↔ CEX arbitrage")
    dex_fee = st.number_input("DEX fee (fraction)", min_value=0.0, max_value=0.1, value=0.003)
    cex_fee = st.number_input("CEX fee (fraction)", min_value=0.0, max_value=0.01, value=0.001)

# Session state for collected data
if "collected" not in st.session_state:
    st.session_state["collected"] = []  # list of dicts {ts, connector, symbol, bid, ask}

col1, col2 = st.columns([2, 1])

# Helper: convert orderbook to top-of-book
def top_of_book_from_ob(ob):
    # ob can be rust OrderBook pyclass or dict
    try:
        if isinstance(ob, dict):
            if not ob.get("bids") or not ob.get("asks"):
                return None, None
            bid = ob["bids"][0][0]
            ask = ob["asks"][0][0]
        else:
            # rust pyclass OrderBook
            if not ob.bids or not ob.asks:
                return None, None
            bid = ob.bids[0][0]
            ask = ob.asks[0][0]
        return float(bid), float(ask)
    except (IndexError, KeyError, AttributeError, TypeError) as e:
        return None, None

# Manual snapshot
if st.button("Fetch snapshot now"):
    with st.spinner("Fetching snapshot..."):
        try:
            ob = connector.fetch_orderbook_sync(symbol) if hasattr(connector, "fetch_orderbook_sync") else connector.fetch_orderbook(symbol)
            bid, ask = top_of_book_from_ob(ob)
            
            if bid is None or ask is None:
                st.error(f"❌ No data available for {symbol}. Check if the symbol is valid and the API is accessible.")
            else:
                ts = datetime.utcnow().isoformat()
                st.session_state["collected"].append({"ts": ts, "connector": connector_name, "symbol": symbol, "bid": bid, "ask": ask})
                st.success(f"✓ Fetched {symbol} — bid {bid:.2f} ask {ask:.2f}")
        except Exception as e:
            st.error(f"❌ Error fetching data: {str(e)}")

# Continuous collection thread
collect_thread = None
stop_event = threading.Event()

def collect_loop(connector, symbol, interval_ms, stop_event, use_websocket=False):
    """Collect orderbook data either by polling or from WebSocket cache."""
    consecutive_failures = 0
    max_failures = 10
    
    while not stop_event.is_set():
        try:
            if use_websocket and hasattr(connector, "latest_snapshot"):
                # Get cached data from WebSocket stream
                ob = connector.latest_snapshot()
                if ob is None:
                    # No data yet, wait a bit and retry
                    consecutive_failures += 1
                    if consecutive_failures > max_failures:
                        # WebSocket might not be working, log to session state
                        if "ws_error" not in st.session_state:
                            st.session_state["ws_error"] = "WebSocket not receiving data, check connection"
                    stop_event.wait(interval_ms / 1000.0)
                    continue
                else:
                    consecutive_failures = 0  # Reset on success
                    if "ws_error" in st.session_state:
                        del st.session_state["ws_error"]
            else:
                # Polling mode - fetch fresh data
                ob = connector.fetch_orderbook_sync(symbol) if hasattr(connector, "fetch_orderbook_sync") else connector.fetch_orderbook(symbol)
            
            bid, ask = top_of_book_from_ob(ob)
            
            # Only append if we got valid data
            if bid is not None and ask is not None:
                ts = datetime.utcnow().isoformat()
                st.session_state["collected"].append({
                    "ts": ts, 
                    "connector": connector.name if hasattr(connector,'name') else connector.__class__.__name__, 
                    "symbol": symbol, 
                    "bid": bid, 
                    "ask": ask
                })
        except Exception as e:
            # Log error to session state for debugging
            st.session_state["collect_error"] = str(e)
        
        stop_event.wait(interval_ms / 1000.0)

# Start/Stop collect controls
if auto_collect and ("collecting" not in st.session_state or not st.session_state["collecting"]):
    # Store connector in session state so it persists
    st.session_state["connector"] = connector
    st.session_state["symbol"] = symbol
    
    # Start WebSocket stream if using streaming mode
    if use_websocket and hasattr(connector, "start_stream"):
        try:
            # Define callback for WebSocket - this receives updates in real-time
            def ws_callback(ob):
                # Callback is called from Rust thread, just log that we got data
                # The actual data is stored in connector.latest_snapshot()
                pass
            
            # Give Python GIL to the callback
            import sys
            connector.start_stream(symbol, ws_callback)
            st.success("🔴 Started WebSocket stream - waiting for data...")
            
            # Give WebSocket time to connect and receive first data
            import time
            time.sleep(1)
            
            # Check if we got data
            test_snapshot = connector.latest_snapshot()
            if test_snapshot is None:
                st.warning("⚠️ WebSocket connected but no data received yet. Will keep trying...")
            else:
                st.success("✓ WebSocket receiving data!")
                
        except Exception as e:
            st.error(f"❌ WebSocket failed: {str(e)}")
            st.info("Falling back to polling mode...")
            use_websocket = False
    
    # Start collection thread
    stop_event.clear()
    t = threading.Thread(target=collect_loop, args=(connector, symbol, collect_interval, stop_event, use_websocket), daemon=True)
    t.start()
    st.session_state["collecting"] = True
    st.session_state["collect_thread"] = t
    st.session_state["use_websocket"] = use_websocket
    
    if not use_websocket:
        st.success("✓ Started polling")
elif (not auto_collect) and st.session_state.get("collecting", False):
    # stop
    stop_event.set()
    st.session_state["collecting"] = False
    if "connector" in st.session_state:
        del st.session_state["connector"]
    if "symbol" in st.session_state:
        del st.session_state["symbol"]
    st.success("Stopped collection")

# Auto-refresh while collecting
if st.session_state.get("collecting", False):
    # Force Streamlit to rerun every second to show new data
    time.sleep(1.0)
    st.rerun()

# Show streaming status and errors
if st.session_state.get("collecting", False):
    num_collected = len(st.session_state.get("collected", []))
    
    if st.session_state.get("use_websocket", False):
        col1.success(f"🔴 LIVE - WebSocket Streaming ({num_collected} snapshots)")
        # Show WebSocket error if any
        if "ws_error" in st.session_state:
            col1.warning(st.session_state["ws_error"])
    else:
        col1.info(f"📊 Polling - REST API ({num_collected} snapshots)")
    
    # Show collection errors if any
    if "collect_error" in st.session_state:
        col1.error(f"Collection error: {st.session_state['collect_error']}")
    
    # Show latest prices in real-time
    if st.session_state.get("collected") and len(st.session_state["collected"]) > 0:
        latest = st.session_state["collected"][-1]
        m1, m2, m3 = col2.columns(3)
        m1.metric("Latest Bid", f"{latest['bid']:.4f}" if latest['bid'] else "N/A")
        m2.metric("Latest Ask", f"{latest['ask']:.4f}" if latest['ask'] else "N/A")
        spread = (latest['ask'] - latest['bid']) if (latest['bid'] and latest['ask']) else 0
        m3.metric("Spread", f"{spread:.4f}" if spread else "N/A")

# Show collected table and visualizations
df = pd.DataFrame(st.session_state["collected"])
if not df.empty:
    df["ts"] = pd.to_datetime(df["ts"])
    col1.subheader("Collected snapshots")
    col1.dataframe(df.tail(200))
    col2.subheader("Top-of-book timeseries")
else:
    col1.info("📊 No data collected yet. Click 'Fetch snapshot now' or enable auto-collection to start.")
    col2.info("📈 Charts will appear here once data is collected.")
    
if not df.empty:
    fig = go.Figure()
    for cname, grp in df.groupby("connector"):
        grp_sorted = grp.sort_values("ts")
        fig.add_trace(go.Scatter(x=grp_sorted["ts"], y=grp_sorted["bid"], mode="lines+markers", name=f"{cname} bid"))
        fig.add_trace(go.Scatter(x=grp_sorted["ts"], y=grp_sorted["ask"], mode="lines", name=f"{cname} ask"))
    fig.update_layout(template="plotly_dark", height=420)
    col2.plotly_chart(fig, use_container_width=True)

    # DEX vs CEX arbitrage quick table (if uniswap and cex snapshots exist)
    col1.subheader("DEX ↔ CEX opportunities (top-of-book comparison)")
    # find latest per connector
    latest = df.groupby(["connector", "symbol"]).last().reset_index()
    # attempt to compare any cex vs any uniswap if present
    opportunities = []
    for idx_c, row_c in latest[latest["connector"].str.contains("cex|binance|coinbase", case=False, na=False)].iterrows():
        for idx_d, row_d in latest[latest["connector"].str.contains("uniswap|dex", case=False, na=False)].iterrows():
            # compute arbitrage using compute_dex_cex_arbitrage wrapper
            ob_cex = {"bids": [[row_c["bid"], 1.0]], "asks": [[row_c["ask"], 1.0]]}
            ob_dex = {"bids": [[row_d["bid"], 1.0]], "asks": [[row_d["ask"], 1.0]]}
            arb = compute_dex_cex_arbitrage(ob_cex, ob_dex, fee_cex=cex_fee, fee_dex=dex_fee)
            opp = {"cex": row_c["connector"], "dex": row_d["connector"], "cex_symbol": row_c["symbol"], "dex_symbol": row_d["symbol"], "arb": arb}
            opportunities.append(opp)
    if opportunities:
        st.write(opportunities)
    else:
        st.info("No CEX/DEX pairs collected yet to compare.")

else:
    st.info("No market snapshots collected yet. Use 'Fetch snapshot now' or enable Auto-collect.")

st.markdown("---")
st.caption("For production use, build the rust_connector with maturin and restart Streamlit. The Rust connector runs async background tasks via Tokio and calls Python callbacks for high-throughput streaming.")