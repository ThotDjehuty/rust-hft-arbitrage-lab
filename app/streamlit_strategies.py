import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import time
import threading
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path to import python module
sys.path.insert(0, str(Path(__file__).parent.parent))

from python.rust_bridge import list_connectors, get_connector
from python.strategies import StrategyExecutor, StrategyConfig, AVAILABLE_STRATEGIES

st.set_page_config(page_title="HFT Arbitrage Lab — Strategies", layout="wide", initial_sidebar_state="expanded")

# Sidebar navigation
st.sidebar.title("🚀 HFT Arbitrage Lab")
page = st.sidebar.radio("Navigation", ["📊 Market Data", "⚡ Strategy Execution", "📈 Live Trading"])

if page == "📊 Market Data":
    st.title("Connectors & Live Market Data")
    
    # Connector configuration
    with st.sidebar:
        st.header("Live configuration")
        connector_name = st.selectbox("Connector", list_connectors())
        
        # Conditionally ask for API credentials
        lower_name = connector_name.lower() if isinstance(connector_name, str) else ""
        needs_auth = any(k in lower_name for k in ("binance_auth", "coinbase_auth", "finnhub"))
        
        if needs_auth:
            st.markdown("**Credentials**")
            api_key = st.text_input("API Key", type="password", key=f"{connector_name}_api_key")
            api_secret = st.text_input("API Secret", type="password", key=f"{connector_name}_api_secret")
            
            if "coinbase_auth" in lower_name:
                passphrase = st.text_input("Passphrase", type="password", key=f"{connector_name}_passphrase")
            else:
                passphrase = None
        else:
            api_key = None
            api_secret = None
            passphrase = None
        
        # Get connector
        try:
            connector = get_connector(connector_name, api_key=api_key, api_secret=api_secret, passphrase=passphrase)
            symbols = connector.list_symbols() if hasattr(connector, "list_symbols") else []
            symbol = st.selectbox("Symbol", symbols)
        except Exception as e:
            st.error(f"Failed to initialize connector: {e}")
            st.stop()
        
        st.write("---")
        st.markdown("Automated collection")
        auto_collect = st.checkbox("Collect market snapshots continuously", value=False)
        collect_interval = st.slider("Interval (ms)", 200, 5000, 500, step=100)
    
    # Session state for collected data
    if "collected" not in st.session_state:
        st.session_state["collected"] = []
    
    col1, col2 = st.columns([2, 1])
    
    # Helper: convert orderbook to top-of-book
    def top_of_book_from_ob(ob):
        try:
            if isinstance(ob, dict):
                bid = ob["bids"][0][0]
                ask = ob["asks"][0][0]
            else:
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
    
    # Show collected data
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
    else:
        st.info("No market snapshots collected yet. Use 'Fetch snapshot now' or enable Auto-collect.")

elif page == "⚡ Strategy Execution":
    st.title("Strategy Backtesting & Execution")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Strategy Selection")
        
        strategy_name = st.selectbox(
            "Choose Strategy",
            options=list(AVAILABLE_STRATEGIES.keys()),
            format_func=lambda x: AVAILABLE_STRATEGIES[x].display_name
        )
        
        strategy_def = AVAILABLE_STRATEGIES[strategy_name]
        
        st.markdown(f"**Description:** {strategy_def.description}")
        st.write("---")
        
        st.subheader("Parameters")
        params = {}
        for param_name, default_value in strategy_def.parameters.items():
            param_desc = strategy_def.param_descriptions.get(param_name, param_name)
            
            if isinstance(default_value, (int, float)):
                params[param_name] = st.number_input(
                    param_desc,
                    value=float(default_value),
                    key=f"param_{param_name}"
                )
            elif isinstance(default_value, str):
                params[param_name] = st.text_input(
                    param_desc,
                    value=default_value,
                    key=f"param_{param_name}"
                )
            elif isinstance(default_value, list):
                params[param_name] = st.text_input(
                    param_desc,
                    value=", ".join(map(str, default_value)),
                    key=f"param_{param_name}"
                ).split(", ")
        
        st.write("---")
        st.subheader("Backtest Configuration")
        initial_capital = st.number_input("Initial Capital ($)", value=100000.0, min_value=1000.0)
        
        # Generate synthetic market data
        generate_data = st.checkbox("Generate synthetic data", value=True)
        if generate_data:
            num_periods = st.slider("Number of periods", 100, 5000, 1000)
        
        run_backtest = st.button("🚀 Run Backtest", type="primary")
    
    with col2:
        st.subheader("Backtest Results")
        
        if run_backtest:
            with st.spinner("Running backtest..."):
                # Generate synthetic market data
                timestamps = pd.date_range(start=datetime.now() - timedelta(days=num_periods//100), periods=num_periods, freq='5min')
                
                market_data = pd.DataFrame({"timestamp": timestamps})
                
                # Generate price data for each symbol
                if strategy_def.requires_multiple_symbols:
                    symbols = [params.get("symbol_a", "BTC/USD"), params.get("symbol_b", "ETH/USD")]
                    if "symbol_c" in params:
                        symbols.append(params.get("symbol_c", "ETH/BTC"))
                else:
                    symbols = [params.get("symbol", "BTC/USD")]
                
                for sym in symbols:
                    # Generate random walk prices
                    returns = np.random.randn(num_periods) * 0.02
                    prices = 100 * (1 + returns).cumprod()
                    market_data[f"{sym}_mid"] = prices
                
                # Create and run strategy
                config = StrategyConfig(
                    strategy_name=strategy_name,
                    parameters=params,
                    mode="backtest",
                    initial_capital=initial_capital
                )
                
                executor = StrategyExecutor(config)
                
                # Execute strategy based on type
                if strategy_name == "triangular_arbitrage":
                    results = executor.run_triangular_arbitrage(market_data)
                elif strategy_name == "pairs_trading":
                    results = executor.run_pairs_trading(market_data)
                elif strategy_name in ["market_making", "market_making_imbalance"]:
                    results = executor.run_market_making(market_data)
                else:
                    st.warning(f"Strategy {strategy_name} execution not yet implemented")
                    results = executor.get_results()
                
                # Display results
                st.success("Backtest completed!")
                
                metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
                
                with metrics_col1:
                    st.metric("Total Return", f"{results['total_return_pct']:.2f}%")
                
                with metrics_col2:
                    st.metric("Sharpe Ratio", f"{results['sharpe_ratio']:.2f}")
                
                with metrics_col3:
                    st.metric("Max Drawdown", f"{results['max_drawdown_pct']:.2f}%")
                
                with metrics_col4:
                    st.metric("Total Trades", results['total_trades'])
                
                # Equity curve
                if not results['equity_curve'].empty:
                    st.subheader("Equity Curve")
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=results['equity_curve']['timestamp'],
                        y=results['equity_curve']['equity'],
                        mode='lines',
                        name='Equity',
                        line=dict(color='#00ff00', width=2)
                    ))
                    fig.update_layout(
                        template="plotly_dark",
                        xaxis_title="Time",
                        yaxis_title="Equity ($)",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Trade history
                if not results['trades'].empty:
                    st.subheader("Trade History")
                    st.dataframe(results['trades'].tail(100))

elif page == "📈 Live Trading":
    st.title("Live Strategy Execution")
    
    st.warning("⚠️ Live trading is for demonstration only. Do not use with real funds without proper risk management!")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Configuration")
        
        strategy_name = st.selectbox(
            "Strategy",
            options=list(AVAILABLE_STRATEGIES.keys()),
            format_func=lambda x: AVAILABLE_STRATEGIES[x].display_name,
            key="live_strategy"
        )
        
        connector_name = st.selectbox("Connector", list_connectors(), key="live_connector")
        
        # API credentials
        st.markdown("**API Credentials**")
        api_key = st.text_input("API Key", type="password", key="live_api_key")
        api_secret = st.text_input("API Secret", type="password", key="live_api_secret")
        
        initial_capital = st.number_input("Virtual Capital ($)", value=10000.0, min_value=100.0)
        
        start_live = st.button("▶️ Start Live Execution", type="primary")
        stop_live = st.button("⏹️ Stop", type="secondary")
    
    with col2:
        st.subheader("Live Performance")
        
        if start_live:
            st.info("Live execution started (demo mode)")
            
            # Create placeholder for live updates
            metrics_placeholder = st.empty()
            chart_placeholder = st.empty()
            
            # Simulate live updates
            for i in range(10):
                with metrics_placeholder.container():
                    m1, m2, m3 = st.columns(3)
                    m1.metric("PnL", f"${np.random.randn()*100:.2f}")
                    m2.metric("Open Positions", np.random.randint(0, 5))
                    m3.metric("Trades Today", np.random.randint(0, 20))
                
                time.sleep(1)
                
                if stop_live:
                    st.success("Live execution stopped")
                    break

st.markdown("---")
st.caption("HFT Arbitrage Lab — High-frequency trading strategies powered by Rust + Python")
