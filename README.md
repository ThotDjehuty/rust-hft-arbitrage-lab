```markdown
# rust-hft-arbitrage-lab

A modular, Docker-ready research lab for high-frequency trading (HFT) and arbitrage research.
This project combines Rust (for low-latency connectors and numeric kernels) and Python (for research, backtesting and visualization) to provide an end-to-end environment:

- Rust <-> Python bridge (PyO3 / maturin)
- Research notebooks (Triangular Arbitrage, Market Making, Pair Trading)
- Reusable Python backtester (PnL, Sharpe, drawdown)
- Streamlit UI for interactive backtesting, simulation and connector-driven live/paper runs
- Docker recipes to build & run everything reproducibly

Quick summary
- Ready-to-run notebooks with fallback Python implementations (so you can run them even without the Rust extension).
- Rust connector skeleton (WebSocket example + orderbook parsing + compute primitives).
- Streamlit app for visually running and inspecting strategies.
- Dockerfile that builds Rust and Python inside a container for consistent builds across hosts.

Table of contents
1. Features
2. Architecture overview
3. Quickstart (Docker — recommended)
4. Local dev (non-Docker)
5. Build & install Rust connector (maturin)
6. Using notebooks
7. Streamlit app (UI & examples)
8. Docker tips & troubleshooting
9. Development & testing
10. Contributing & license
11. References

---

## 1. Features

- Rust connector exported as a Python extension using PyO3 (fast orderbook parsing, example triangular compute).
- Python bridge (`python/rust_bridge.py`) that exposes the Rust functions to notebooks / Streamlit.
- Backtesting core (`python/backtest/core.py`) with:
  - Trade execution simulation
  - Mark-to-market equity curve recording
  - Metrics: returns, Sharpe (annualized), max drawdown
  - Plotly visualizations
- Notebooks:
  - `notebooks/Triangular.ipynb`
  - `notebooks/MarketMaking.ipynb`
  - `notebooks/PairTrading.ipynb`
  Each notebook contains equations, inline commentary, fallback implementations and visualization cells.
- Streamlit app (`app/streamlit_app.py`) that:
  - Runs backtests (synthetic or CSV)
  - Simulates live feed (synthetic orderbook)
  - Attempts to start the Rust WebSocket connector if built
  - Displays equity, trades, orderbook snapshots and metrics
- Docker-based reproducible build (Rust + Python built inside container using maturin).

---

## 2. Architecture overview

- rust_connector/ (Rust crate)
  - PyO3 module exposing:
    - OrderBook type
    - parse_orderbook(json)
    - compute_triangular_opportunity(...)
    - blocking_start_ws(url) — example to start WS in background
- python/
  - rust_bridge.py — thin shim to call the Rust module from Python
  - backtest/core.py — Backtest class + metrics
- app/
  - streamlit_app.py — interactive UI for backtesting and live simulation
  - joke_app.py — small demo (random joke generator)
- notebooks/ — example strategy notebooks (self-contained)
- Dockerfile, docker-compose.yml — build and run everything inside a container

Design notes:
- The Rust crate is built and installed into the Python environment using maturin. Rust crates (like pyo3) must be declared in Cargo.toml and NOT in pip requirements.
- The Streamlit app uses the Python bridge to call Rust when available, otherwise uses Python fallbacks included in the notebooks and app.

---

## 3. Quickstart (Docker — recommended)

Why Docker? It isolates host differences (macOS Python linking, architecture mismatches) and builds the Rust extension in a Linux environment where maturin + Python dev libs are available.

1) Build & run (from repository root)
```bash
# optionally improve performance on some setups
export COMPOSE_BAKE=true

# build and start (this will build Rust, install Python deps and start Streamlit)
docker-compose up --build
```

2) Open the UI:
- Streamlit interface: http://localhost:8501

3) Stop
```bash
docker-compose down
```

Notes:
- The image builds the Rust toolchain and runs `python -m maturin develop --manifest-path rust_connector/Cargo.toml --release` inside the container. That installs the compiled Python extension into the container's Python environment.
- If the build fails in Docker, copy the first ~100 error lines and check the Troubleshooting section below.

---

## 4. Local development (without Docker)

Prerequisites:
- Rust toolchain (rustup)
- Python 3.11+ (same interpreter you will use to run Streamlit)
- pip and virtualenv

Steps:
```bash
# create & activate venv
python -m venv .venv
source .venv/bin/activate

# install maturin and dependencies
pip install --upgrade pip setuptools wheel maturin
pip install -r docker/requirements.txt    # note: docker/requirements.txt does NOT include Rust crates

# build & install the rust extension into the current Python env
python -m maturin develop --manifest-path rust_connector/Cargo.toml --release

# run streamlit
streamlit run app/streamlit_app.py
```

Important: run `maturin` using the same Python interpreter you will use to import the extension (the same venv).

---

## 5. Build & install Rust connector (maturin)

The Rust crate is at `rust_connector/`. Example Cargo.toml includes PyO3 and tokio-tungstenite.

Build & install (dev workflow):
```bash
# from repo root (ensure your venv/py env is active)
python -m pip install --upgrade maturin
python -m maturin develop --manifest-path rust_connector/Cargo.toml --release
```

Alternative: build a wheel and install it and/or publish it:
```bash
python -m maturin build --manifest-path rust_connector/Cargo.toml --release
pip install target/wheels/rust_connector-*.whl
```

Notes:
- Do NOT put `pyo3` in Python requirements.txt — `pyo3` is a Rust dependency (Cargo.toml).
- If you encounter macOS linker errors (missing _Py symbols), ensure the Python architecture matches the Rust build or use Docker to build in Linux.

Example Python usage (after building):
```python
from python.rust_bridge import parse_orderbook, compute_triangular_opportunity, start_ws

# parsing
ob = parse_orderbook('{"bids":[[100.0,1]],"asks":[[100.1,1]]}')

# compute (placeholders exist in skeleton)
profit, route = compute_triangular_opportunity(ob, ob, ob)

# start background websocket client (example)
start_ws("wss://example.exchange/ws")
```

---

## 6. Using the notebooks

Notebooks are self-contained and have fallback implementations:
- Run them in Jupyter or VSCode notebooks.
- They attempt to import `python.rust_bridge` but fall back to pure-Python logic so results are reproducible if Rust extension is missing.
- Each notebook includes:
  - Strategy explanation & equations
  - Synthetic dataset generator
  - Strategy function (detect & signal generation)
  - Backtest run and visualizations (Plotly)
  - Notes on production improvements (fees, depth, slippage, order management)

Quick run:
```bash
pip install -r docker/requirements.txt
jupyter notebook notebooks/Triangular.ipynb
```

---

## 7. Streamlit app (UI & examples)

File: `app/streamlit_app.py`

Key features:
- Choose mode: Backtest | Live (simulate) | Live (connector)
- Choose strategy: Triangular | Market Making | Pair Trading
- Data source: Synthetic | Upload CSV
- For Backtest: sliders & params in sidebar, Equity chart, Metrics, Trades table
- For Live (simulate): synthetic orderbook feed with orderbook snapshot and mid-price chart
- For Live (connector): attempts to call `rust_connector` to start a WS client

Example commands:
```bash
# run locally
streamlit run app/streamlit_app.py

# in Docker the container's CMD runs streamlit automatically
```

Security note: never hardcode API keys. Use Streamlit secrets (`.streamlit/secrets.toml`) or environment variables when connecting to real exchanges.

---

## 8. Docker tips & troubleshooting

Common build problem you reported:
- Error: `Could not find a version that satisfies the requirement pyo3`
  - Root cause: `pyo3` is a Rust crate, not a Python package; pip cannot install it.
  - Fix: remove `pyo3` from any `requirements.txt` and let `maturin` build the Rust crate.

Build troubleshooting checklist:
1. If pip fails saying it can't find pyo3 -> remove it from requirements.
2. If macOS linker fails with missing `_Py*` symbols:
   - Likely Python <-> Rust arch mismatch. Ensure you run maturin with the Python interpreter you will use for import.
   - Use Docker to build on Linux if host linking is problematic.
3. If Docker build is slow:
   - Consider enabling delegated builds: `export COMPOSE_BAKE=true` (informational prompt from compose).
   - Use Docker build cache or multi-stage builds to reduce final image size.
4. Use `--manifest-path rust_connector/Cargo.toml` with maturin to avoid workspace detection issues.

Example Docker rebuild (after fixing requirements):
```bash
docker-compose down --remove-orphans
export COMPOSE_BAKE=true     # optional
docker-compose up --build
```

If you still hit errors, copy the first 80–120 lines of the failing build log and open an issue or paste here.

---

## 9. Development & testing

- Add unit tests for:
  - Rust functions (use maturin + pytest to import & test behavior)
  - Backtester invariants (PnL commutativity, monotonicity in some setups)
  - Strategy deterministic behavior on synthetic snapshots
- Suggested CI:
  - CI job that builds the Rust wheel using maturin and runs Python tests in a Linux runner
  - Use multi-stage builds: builder stage (has rust toolchain) produces wheel, runtime stage installs the wheel and python deps

Example test command:
```bash
python -m pytest tests/
```

---

## 10. Contributing & Code Style

- Please open issues for bugs / feature requests.
- PRs: fork -> branch -> PR; include tests where relevant.
- Rust style: `cargo fmt` and `cargo clippy`.
- Python style: follow Black (optional), include unit tests for new features.

Suggested files to add (if not present):
- LICENSE (MIT or Apache-2.0)
- CONTRIBUTING.md
- .github/workflows/ci.yml (build + test + lint)

---

## 11. References & useful links

- PyO3: https://pyo3.rs
- Maturin: https://github.com/PyO3/maturin
- tokio-tungstenite: async websocket client for tokio (used in examples)
- Streamlit: https://streamlit.io
- Plotly: https://plotly.com/python

---

## Minimal example snippets

Build rust and install into interpreter:
```bash
python -m pip install --upgrade maturin
python -m maturin develop --manifest-path rust_connector/Cargo.toml --release
```

Run Streamlit:
```bash
streamlit run app/streamlit_app.py
```

Python usage example:
```python
from python.rust_bridge import parse_orderbook, compute_triangular_opportunity

ob_json = '{"bids":[[100.0,1]],"asks":[[100.1,1]]}'
ob = parse_orderbook(ob_json)
profit, route = compute_triangular_opportunity(ob, ob, ob)
print("profit", profit, "route", route)
```

Docker build & run:
```bash
export COMPOSE_BAKE=true      # optional
docker-compose up --build
# open http://localhost:8501
```

---

If you want, I can:
- prepare a git patch that updates `docker/requirements.txt` (removes any `pyo3` listed) and the `Dockerfile` to use `--manifest-path` and `maturin` as described, or
- produce a lightweight multi-stage Dockerfile (builder → runtime) so the final image is smaller (no Rust toolchain included).

Thank you — copy this README into `README.md` at repository root to replace the current README or use it as a polished project landing doc.
```