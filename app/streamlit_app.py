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
    connector_name = st.selectbox("Connector", list_connectors())

    # Conditionally ask for API credentials for connectors that commonly require them
    lower_name = connector_name.lower() if isinstance(connector_name, str) else ""
    needs_auth = any(k in lower_name for k in ("binance", "coinbase"))
    if needs_auth:
        st.markdown("**Credentials**")
        api_key = st.text_input("API Key", type="password", key=f"{connector_name}_api_key")
        api_secret = st.text_input("API Secret", type="password", key=f"{connector_name}_api_secret")
    else:
        api_key = None
        api_secret = None

    # Obtain connector instance, passing credentials when available. The bridge will try to
    # set credentials on returned connector objects when possible.
    connector = get_connector(connector_name, api_key=api_key, api_secret=api_secret)
    symbols = connector.list_symbols() if hasattr(connector, "list_symbols") else []
    symbol = st.selectbox("Symbol", symbols)

    st.write("---")
    st.markdown("Automated collection")
    auto_collect = st.checkbox("Collect market snapshots continuously", value=False)
    collect_interval = st.slider("Interval (ms)", 200, 5000, 500, step=100)
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
            bid = ob["bids"][0][0]
            ask = ob["asks"][0][0]
        else:
            # rust pyclass OrderBook
            bid = ob.bids[0][0]
            ask = ob.asks[0][0]
        return float(bid), float(ask)
    except Exception:
        return 0.0, 0.0

# Manual snapshot
if st.button("Fetch snapshot now"):
    with st.spinner("Fetching snapshot..."):
        ob = connector.fetch_orderbook_sync(symbol) if hasattr(connector, "fetch_orderbook_sync") else connector.fetch_orderbook(symbol)
        bid, ask = top_of_book_from_ob(ob)
        ts = datetime.utcnow().isoformat()
        st.session_state["collected"].append({"ts": ts, "connector": connector_name, "symbol": symbol, "bid": bid, "ask": ask})
        st.success(f"Fetched {symbol} — bid {bid} ask {ask}")

# Continuous collection thread
collect_thread = None
stop_event = threading.Event()

def collect_loop(connector, symbol, interval_ms, stop_event):
    while not stop_event.is_set():
        try:
            ob = connector.fetch_orderbook_sync(symbol) if hasattr(connector, "fetch_orderbook_sync") else connector.fetch_orderbook(symbol)
            bid, ask = top_of_book_from_ob(ob)
            ts = datetime.utcnow().isoformat()
            st.session_state["collected"].append({"ts": ts, "connector": connector.name if hasattr(connector,'name') else connector.__class__.__name__, "symbol": symbol, "bid": bid, "ask": ask})
        except Exception as e:
            st.warning(f"collect error: {e}")
        stop_event.wait(interval_ms / 1000.0)

# Start/Stop collect controls
if auto_collect and ("collecting" not in st.session_state or not st.session_state["collecting"]):
    # start thread
    stop_event.clear()
    t = threading.Thread(target=collect_loop, args=(connector, symbol, collect_interval, stop_event), daemon=True)
    t.start()
    st.session_state["collecting"] = True
    st.session_state["collect_thread"] = t
    st.success("Started collection")
elif (not auto_collect) and st.session_state.get("collecting", False):
    # stop
    stop_event.set()
    st.session_state["collecting"] = False
    st.success("Stopped collection")

# Show collected table and visualizations
df = pd.DataFrame(st.session_state["collected"])
if not df.empty:
    df["ts"] = pd.to_datetime(df["ts"])
    col1.subheader("Collected snapshots")
    col1.dataframe(df.tail(200))
    col2.subheader("Top-of-book timeseries")
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