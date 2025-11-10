import streamlit as st
import pandas as pd
import numpy as np
import time
import threading
import queue
import json
import math
import plotly.graph_objects as go
from datetime import datetime

# Try to import rust_bridge and backtest core; fallbacks provided if not present
RUST_AVAILABLE = False
try:
    from python.rust_bridge import parse_orderbook as rust_parse_orderbook, compute_triangular_opportunity as rust_tri, start_ws as rust_start_ws
    RUST_AVAILABLE = True
except Exception:
    RUST_AVAILABLE = False

BACKTEST_AVAILABLE = False
try:
    from python.backtest.core import Backtest, sharpe_ratio, max_drawdown
    BACKTEST_AVAILABLE = True
except Exception:
    # Minimal fallback backtester
    BACKTEST_AVAILABLE = True
    class Backtest:
        def __init__(self, initial_cash=100000.0):
            self.cash = initial_cash
            self.positions = {}
            self.trades = []
            self.history = []

        def execute_trade(self, timestamp, symbol, qty, price, side):
            cost = qty * price
            if side.lower() == 'buy':
                self.cash -= cost
                prev = self.positions.get(symbol, (0.0, 0.0))
                new_qty = prev[0] + qty
                new_avg = (prev[0]*prev[1] + qty*price) / (new_qty if new_qty != 0 else 1)
                self.positions[symbol] = (new_qty, new_avg)
            else:
                self.cash += cost
                prev = self.positions.get(symbol, (0.0, 0.0))
                new_qty = prev[0] - qty
                if new_qty <= 0:
                    self.positions.pop(symbol, None)
                else:
                    self.positions[symbol] = (new_qty, prev[1])
            self.trades.append({"ts": timestamp, "symbol": symbol, "qty": qty, "price": price, "side": side})
            self.mark_to_market(timestamp, {})

        def mark_to_market(self, timestamp, market_prices: dict):
            equity = self.cash
            for s, (qty, avg) in self.positions.items():
                price = market_prices.get(s, avg)
                equity += qty * price
            self.history.append((timestamp, equity))
            return equity

        def results_df(self):
            df = pd.DataFrame(self.history, columns=["ts", "equity"]).set_index("ts")
            df["returns"] = df["equity"].pct_change().fillna(0.0)
            df["cum_return"] = (1 + df["returns"]).cumprod() - 1
            return df

    def sharpe_ratio(returns, freq=252):
        if len(returns) < 2:
            return 0.0
        mu = returns.mean() * freq
        sigma = returns.std() * math.sqrt(freq)
        return mu / sigma if sigma != 0 else 0.0

    def max_drawdown(equity_curve):
        roll_max = equity_curve.cummax()
        drawdown = (equity_curve - roll_max) / roll_max
        return drawdown.min()

# Helper: apply light styling to the app
st.set_page_config(page_title="HFT Arbitrage Lab", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(90deg,#0f172a 0%, #071029 100%); color: #e6eef8; }
    .big-title {font-size:28px; font-weight:700; color:#ffd966}
    .muted { color:#9fb0d6 }
    .metric { background: rgba(255,255,255,0.03); padding: 8px; border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("<div class='big-title'>HFT Arbitrage Lab — Visual Strategies</div>", unsafe_allow_html=True)
st.markdown("<div class='muted'>Use Backtest for offline analysis or Live to simulate feeds / try connectors</div>", unsafe_allow_html=True)
st.write("")

# Sidebar controls
with st.sidebar:
    st.header("Run configuration")
    mode = st.selectbox("Mode", ["Backtest", "Live (simulate)", "Live (connector)"])
    strategy = st.selectbox("Strategy", ["Triangular", "Market Making", "Pair Trading"])
    data_source = st.selectbox("Data source", ["Synthetic", "Upload CSV"])
    api_key = st.text_input("API Key (optional)", type="password")
    api_secret = st.text_input("API Secret (optional)", type="password")
    run = st.button("Run")
    st.markdown("---")
    st.markdown("Rust connector available: " + ("✅" if RUST_AVAILABLE else "❌"))

# Shared UI placeholders
col1, col2 = st.columns([2, 1])

# Data loaders
def generate_synthetic_orderbook(mid=100.0, spread=0.002, size=10):
    bid = round(mid * (1 - spread/2), 8)
    ask = round(mid * (1 + spread/2), 8)
    bids = [[bid * (1 - i*0.0005), size*(1+i)] for i in range(5)]
    asks = [[ask * (1 + i*0.0005), size*(1+i)] for i in range(5)]
    return {"bids": bids, "asks": asks}

def generate_synthetic_price_series(length=500, base=100.0, vol=0.001):
    rng = np.random.default_rng(42)
    returns = rng.normal(0, vol, length)
    prices = base * np.exp(np.cumsum(returns))
    df = pd.DataFrame({"ts": np.arange(length), "price": prices})
    return df.set_index("ts")

# Strategy implementations (simple, for visualization)
def triangular_detect(ob1, ob2, ob3):
    # Use top-of-book bids to detect a simple loop profit on synthetic orientation
    try:
        a_bid = ob1["bids"][0][0]
        b_bid = ob2["bids"][0][0]
        c_bid = ob3["bids"][0][0]
        after = 1.0 * a_bid * b_bid * c_bid
        profit = after - 1.0
        return profit
    except Exception:
        return 0.0

def run_triangular_backtest(df_snapshots, threshold=0.0008, trade_size=1.0):
    bt = Backtest(100000)
    ts = 0
    for ob1, ob2, ob3 in df_snapshots:
        profit = triangular_detect(ob1, ob2, ob3)
        mid_A = (ob1["bids"][0][0] + ob1["asks"][0][0]) / 2
        bt.mark_to_market(ts, {"A": mid_A})
        if profit > threshold:
            # simulate sell at bid and buy back at ask/effective price
            bt.execute_trade(ts, "A", trade_size, ob1["bids"][0][0], "sell")
            eff_price = ob1["asks"][0][0] / (1 + profit)
            bt.execute_trade(ts, "A", trade_size, eff_price, "buy")
        ts += 1
    return bt

def run_mm_backtest(price_series, spread=0.002, mm_size=1.0, skew=0.5):
    bt = Backtest(100000)
    ts = 0
    for t, row in price_series.iterrows():
        mid = row["price"]
        bid = mid * (1 - spread/2)
        ask = mid * (1 + spread/2)
        inv = bt.positions.get("SYM", (0.0, 0.0))[0] if "SYM" in bt.positions else 0.0
        if inv > 0:
            post_bid = mm_size * (1 - skew)
            post_ask = mm_size * (1 + skew)
        elif inv < 0:
            post_bid = mm_size * (1 + skew)
            post_ask = mm_size * (1 - skew)
        else:
            post_bid = post_ask = mm_size
        # probabilistic fills
        p_buy = max(0.01, 0.5 - abs(mid - bid) / mid * 100)
        p_sell = max(0.01, 0.5 - abs(ask - mid) / mid * 100)
        if np.random.rand() < p_buy:
            bt.execute_trade(ts, "SYM", post_bid, bid, "buy")
        if np.random.rand() < p_sell:
            bt.execute_trade(ts, "SYM", post_ask, ask, "sell")
        bt.mark_to_market(ts, {"SYM": mid})
        ts += 1
    return bt

def run_pair_backtest(df_prices, entry_z=2.0, exit_z=0.5, window=50, size=10.0):
    # df_prices must have 'P1' and 'P2'
    bt = Backtest(100000)
    T = len(df_prices)
    betas = []
    spread = []
    for i in range(window, T):
        y_slice = df_prices['P1'].iloc[i-window:i]
        x_slice = df_prices['P2'].iloc[i-window:i]
        beta = np.cov(x_slice, y_slice, ddof=0)[0,1] / np.var(x_slice)
        betas.append(beta)
        s = df_prices['P1'].iloc[i] - beta * df_prices['P2'].iloc[i]
        spread.append(s)
    betas = np.array(betas)
    spread = np.array(spread)
    mu = pd.Series(spread).rolling(20).mean()
    sigma = pd.Series(spread).rolling(20).std()
    z = (pd.Series(spread) - mu) / sigma
    z = z.fillna(0)
    position = 0
    ts = 0
    for i in range(len(z)):
        zi = z[i]
        idx = i + window
        p1 = df_prices['P1'].iloc[idx]
        p2 = df_prices['P2'].iloc[idx]
        if position == 0:
            if zi > entry_z:
                bt.execute_trade(ts, 'P1', size, p1, 'sell')
                bt.execute_trade(ts, 'P2', size*betas[i], p2, 'buy')
                position = -1
            elif zi < -entry_z:
                bt.execute_trade(ts, 'P1', size, p1, 'buy')
                bt.execute_trade(ts, 'P2', size*betas[i], p2, 'sell')
                position = 1
        elif position == 1:
            if abs(zi) < exit_z:
                bt.execute_trade(ts, 'P1', size, p1, 'sell')
                bt.execute_trade(ts, 'P2', size*betas[i], p2, 'buy')
                position = 0
        elif position == -1:
            if abs(zi) < exit_z:
                bt.execute_trade(ts, 'P1', size, p1, 'buy')
                bt.execute_trade(ts, 'P2', size*betas[i], p2, 'sell')
                position = 0
        bt.mark_to_market(ts, {'P1': p1, 'P2': p2})
        ts += 1
    return bt

# Live simulation infrastructure
live_q = queue.Queue()
live_running = threading.Event()

def live_simulator(q, interval=0.4):
    """Puts synthetic orderbook snapshots into queue periodically for UI display."""
    rng = np.random.default_rng(123)
    mid = 100.0
    while live_running.is_set():
        mid = mid * math.exp(rng.normal(0, 0.0005))
        ob = generate_synthetic_orderbook(mid=mid, spread=0.002)
        timestamp = datetime.utcnow().isoformat()
        q.put((timestamp, ob))
        time.sleep(interval)

# UI main
if run:
    if mode == "Backtest":
        st.success("Running backtest: %s" % strategy)
        if data_source == "Synthetic":
            if strategy == "Triangular":
                # create synthetic snapshots of triples
                snapshots = []
                base_mid = 1.0
                for i in range(300):
                    m_ab = base_mid * (1 + np.random.normal(0, 0.0006))
                    m_bc = 2.0 * (1 + np.random.normal(0, 0.0006))
                    # create m_ca to usually be consistent but occasionally produce arbitrage
                    if np.random.rand() < 0.07:
                        m_ca = 1.0 / (m_ab * m_bc) * 1.0025
                    else:
                        m_ca = 1.0 / (m_ab * m_bc) * (1 + np.random.normal(0, 0.0002))
                    snapshots.append((generate_synthetic_orderbook(m_ab), generate_synthetic_orderbook(m_bc), generate_synthetic_orderbook(m_ca)))
                bt = run_triangular_backtest(snapshots, threshold=st.sidebar.slider("Tri Threshold", 0.0001, 0.01, 0.0008, 0.0001), trade_size=st.sidebar.number_input("Trade size (A)", 0.1, 100.0, 1.0))
            elif strategy == "Market Making":
                series = generate_synthetic_price_series(800, base=100.0, vol=0.001)
                bt = run_mm_backtest(series, spread=st.sidebar.slider("MM spread", 0.0005, 0.01, 0.002, 0.0005), mm_size=st.sidebar.number_input("MM size", 0.1, 10.0, 1.0), skew=st.sidebar.slider("Skew", 0.0, 0.9, 0.5))
            elif strategy == "Pair Trading":
                # make synthetic cointegrated pair
                T = 700
                x = np.cumsum(np.random.normal(0, 0.5, T)) + 50
                beta_true = 1.8
                y = beta_true * x + np.random.normal(0, 0.2, T)
                dfp = pd.DataFrame({'P1': x, 'P2': y})
                bt = run_pair_backtest(dfp, entry_z=st.sidebar.slider("Entry z", 1.0, 3.5, 2.0), exit_z=st.sidebar.slider("Exit z", 0.1, 1.0, 0.5))
        else:
            uploaded = st.file_uploader("Upload CSV for backtest (price series or orderbooks)")
            if uploaded is not None:
                # simple CSV handling: if it contains columns P1,P2 use pair backtest, else treat as price series for MM
                df = pd.read_csv(uploaded)
                if {"P1", "P2"}.issubset(set(df.columns)) and strategy == "Pair Trading":
                    bt = run_pair_backtest(df, entry_z=st.sidebar.slider("Entry z", 1.0, 3.5, 2.0), exit_z=st.sidebar.slider("Exit z", 0.1, 1.0, 0.5))
                else:
                    if strategy == "Market Making":
                        bt = run_mm_backtest(df.rename(columns={df.columns[0]:'price'}), spread=st.sidebar.slider("MM spread", 0.0005, 0.01, 0.002, 0.0005))
                    else:
                        st.warning("CSV support for this strategy is limited; use synthetic for now.")
                        st.stop()
        # Render results
        df = bt.results_df()
        col1.subheader("Equity curve")
        if not df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df['equity'], mode='lines', name='Equity'))
            fig.update_layout(height=400, template="plotly_dark")
            col1.plotly_chart(fig, use_container_width=True)
            col2.subheader("Metrics")
            col2.metric("Final equity", f"{df['equity'].iloc[-1]:.2f}")
            col2.metric("Sharpe", f"{sharpe_ratio(df['returns']):.3f}")
            col2.metric("Max drawdown", f"{max_drawdown(df['equity']):.3f}")
            st.subheader("Trades")
            if len(bt.trades) > 0:
                trades_df = pd.DataFrame(bt.trades)
                st.dataframe(trades_df.tail(200))
            else:
                st.info("No trades in this backtest run.")
        else:
            st.info("No history produced by backtest.")
    elif mode == "Live (simulate)":
        st.info("Starting live simulator (synthetic orderbook feed).")
        live_running.set()
        t = threading.Thread(target=live_simulator, args=(live_q,), daemon=True)
        t.start()
        st.subheader("Live orderbook (synthetic)")
        ob_placeholder = st.empty()
        price_chart = st.empty()
        history_prices = []
        max_points = 200
        try:
            while True:
                try:
                    ts, ob = live_q.get(timeout=2.0)
                    # compute mid
                    mid = (ob["bids"][0][0] + ob["asks"][0][0]) / 2
                    history_prices.append({"ts": ts, "mid": mid})
                    if len(history_prices) > max_points:
                        history_prices.pop(0)
                    # orderbook depth chart
                    bids = ob["bids"]
                    asks = ob["asks"]
                    bid_prices = [p for p, s in bids]
                    bid_sizes = [s for p, s in bids]
                    ask_prices = [p for p, s in asks]
                    ask_sizes = [s for p, s in asks]
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=bid_prices, y=bid_sizes, name="bids", marker_color="green", orientation='v'))
                    fig.add_trace(go.Bar(x=ask_prices, y=ask_sizes, name="asks", marker_color="red", orientation='v'))
                    fig.update_layout(title=f"Orderbook snapshot @ {ts}", barmode='overlay', template="plotly_dark", height=350)
                    ob_placeholder.plotly_chart(fig, use_container_width=True)
                    # mid price timeseries
                    hist_df = pd.DataFrame(history_prices).set_index("ts")
                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(x=hist_df.index, y=hist_df['mid'], mode='lines+markers', name='mid'))
                    fig2.update_layout(title="Mid price (live)", template="plotly_dark", height=300)
                    price_chart.plotly_chart(fig2, use_container_width=True)
                    time.sleep(0.05)
                except queue.Empty:
                    # no data recently
                    st.warning("No live data received.")
                    break
        except KeyboardInterrupt:
            live_running.clear()
            st.info("Stopped live simulator.")
        finally:
            live_running.clear()
    elif mode == "Live (connector)":
        st.info("Attempting to start connector...")
        if RUST_AVAILABLE:
            try:
                # rust_start_ws should start the ws in background (per rust module design)
                rust_start_ws("wss://example.exchange/ws")
                st.success("Rust WS started (background). Check logs for events.")
            except Exception as e:
                st.error(f"Rust connector failed to start: {e}")
        else:
            st.error("Rust connector not available locally. Build it with maturin develop --manifest-path rust_connector/Cargo.toml")
            st.info("As fallback you can use Live (simulate) mode to visualise data.")
else:
    st.info("Choose options in the sidebar and click Run to execute a strategy or start live mode.")