# rust-hft-arbitrage-lab

A modular, Docker-ready, **Rust + Python** high-frequency trading & arbitrage research lab, with:
- 🦀 **Rust core** (order book, matching engine, stream processing, strategies, signature optimal stopping)
- 🐍 **Python bindings** (PyO3 / maturin) for notebooks & analysis
- 🧪 **Mock exchanges** (FastAPI REST + WebSocket) for deterministic end-to-end tests
- 📓 **Notebooks** (market making w/ imbalance, stat-arb pairs, triangular arb, Hawkes modeling, portfolio hedging, price discovery, signature optimal stopping)
- ⚙️ **GitHub Actions** CI (build/test/package) + Release (wheel + zip)
- 🐳 **Docker Compose** to run everything locally without installing toolchains

![Build](https://github.com/<your-user>/rust-hft-arbitrage-lab/actions/workflows/build_and_package.yml/badge.svg)

---

## Table of contents

- [Quickstart](#quickstart)
- [Project goals](#project-goals)
- [Architecture](#architecture)
- [Mock exchanges (FastAPI)](#mock-exchanges-fastapi)
- [Rust core](#rust-core)
- [Python bindings](#python-bindings)
- [Backtesting & execution](#backtesting--execution)
- [Notebooks (examples)](#notebooks-examples)
- [Docker & Compose](#docker--compose)
- [GitHub Actions (CI & Release)](#github-actions-ci--release)
- [Data & reproducibility](#data--reproducibility)
- [Roadmap](#roadmap)
- [References](#references)
- [Contributing](#contributing)
- [License](#license)

---

## Quickstart

**Run everything with Docker:**
```bash
docker compose up --build
# Jupyter: http://localhost:8888
# Mock API: http://localhost:8000/health
```

**Local dev (optional):**
```bash
# Build Python bindings (needs Rust toolchain + maturin)
pip install maturin
cd rust_python_bindings
maturin develop --release
```

---

## Project goals

- Provide a **research-grade** playground for HFT & arbitrage:
  - Order book simulation & **depth-aware execution** (matching engine, fills)
  - **Market making** with inventory/imbalance control
  - **Statistical arbitrage** (pairs, triangular)
  - **Price discovery** (multi-venue correlation / lead–lag)
  - **Portfolio hedging** (factor/PCA demos)
  - **Hawkes processes** for event-time modeling (via `tick`)
  - **Signature Optimal Stopping** implemented in Rust, callable from Python
- Fully **containerized** & **CI-driven** for reproducibility

---

## Architecture

```
rust-hft-arbitrage-lab/
├─ .github/workflows/
│  ├─ build_and_package.yml       # CI: build/test/package (artifact zip)
│  └─ release.yml                 # Release on tag: wheel + repo zip
├─ docker/
│  └─ requirements.txt            # Python deps for notebooks & mocks
├─ scripts/
│  └─ start_jupyter.sh
├─ mock_apis/                     # FastAPI mock exchanges (REST + WS)
│  ├─ Dockerfile
│  ├─ app.py
│  └─ data/
│     ├─ binance.json
│     ├─ kraken.json
│     └─ coinmarketcap.json
├─ rust_core/                     # Rust core library (no Py deps)
│  ├─ Cargo.toml
│  └─ src/
│     ├─ lib.rs
│     ├─ orderbook.rs
│     ├─ matching_engine.rs
│     ├─ signature_optimal_stopping.rs
│     ├─ stream/
│     │  ├─ mod.rs
│     │  ├─ ws_client.rs
│     │  └─ processor.rs
│     └─ strategies/
│        ├─ mod.rs
│        ├─ mm.rs
│        └─ pairs.rs
├─ rust_python_bindings/          # PyO3 module (maturin)
│  ├─ Cargo.toml
│  └─ src/lib.rs                  # exports hft_py.{hello,simulate_market_order_py,...}
├─ python_client/                 # Lightweight Python client side
│  ├─ backtest.py
│  ├─ execution.py
│  └─ strategies/
│     ├─ __init__.py
│     └─ mm_imbalance.py
├─ examples/notebooks/            # Analysis & demos
│  ├─ market_making_imbalance.ipynb
│  ├─ stat_arb_pairs.ipynb
│  ├─ triangular_arbitrage.ipynb
│  ├─ hawkes_modeling.ipynb
│  ├─ ws_orderbook_client_demo.ipynb
│  ├─ portfolio_hedging.ipynb
│  ├─ price_discovery.ipynb
│  └─ signature_optimal_stopping.ipynb
├─ data/
│  ├─ eth_ohlcv.csv
│  └─ sample_market.csv
├─ tests/
│  ├─ test_bindings.py
│  └─ test_backtest.py
├─ docker-compose.yml
├─ Dockerfile
├─ README.md
└─ LICENSE
```

---

## Mock exchanges (FastAPI)

**Endpoints (REST):**
- `/api/{exchange}/ticker` → synthetic spot prices
- `/api/{exchange}/orderbook/{symbol}?depth=20&latency_ms=...` → L2 snapshot with configurable depth/latency
- `/api/{exchange}/mock_trades/{symbol}?n=...` → synthetic trade prints

**WebSocket:**
- `/ws/orderbook/{exchange}/{symbol}?depth=...&interval_ms=...` → periodic L2 updates for **real-time** tests

**Exchanges covered (mocked):**
- `binance`, `kraken`, `coinmarketcap` (add more JSONs to `mock_apis/data/` to extend)

This enables **end-to-end tests** without hitting real APIs; you can control **depth** and **latencies** to stress strategies.

---

## Rust core

- `orderbook.rs` — L2 model with deltas & mid calculation
- `matching_engine.rs` — depth-aware market order fills (volume-by-price)
- `stream/ws_client.rs` — robust WS client (auto-reconnect w/ backoff)
- `stream/processor.rs` — async pipeline using `tokio::mpsc` (event → book state)
- `strategies/mm.rs` — imbalance-aware quoting (`MMQuote`)
- `strategies/pairs.rs` — simple z-score calculation for spreads
- `signature_optimal_stopping.rs` — minimal signature-style features & quantile-based optimal stop placeholder

> The **Signature Optimal Stopping** module is a **Rust implementation callable from Python** (see notebook). It demonstrates the pipeline; you can enrich the features/signature levels/decision rules or plug a learned policy.

---

## Python bindings

The PyO3 module `hft_py` exposes:
- `hello() -> str` — smoke test
- `simulate_market_order_py(levels: List[Tuple[price,size]], qty: float)` → `(filled, cost, fills)`
- `signature_opt_stop_py(path: List[Tuple[t,x]], quantile: float)` → `Optional[(t,x)]`

Build locally with:
```bash
pip install maturin
cd rust_python_bindings
maturin develop --release
python -c "import hft_py; print(hft_py.hello())"
```

---

## Backtesting & execution

- `python_client/execution.py`:
  - `SimulatedAdapter` hits the **mock orderbook** and simulates market order fills against the L2.
- `python_client/backtest.py`:
  - Minimal event-driven loop to demonstrate integration (extend with slippage/latency/fees).

Example strategy skeleton (market making w/ imbalance) is in `python_client/strategies/mm_imbalance.py`.

---

## Notebooks (examples)

All notebooks live in `examples/notebooks/` and are ready to run when the stack is up:

1. **Market Making (Imbalance)** — compute L2 imbalance, derive skewed quotes, visualize mid & imbalance.
2. **Stat Arb Pairs** — fit linear relation, compute residuals/spreads, z-score, entry/exit template.
3. **Triangular Arbitrage** — toy loop over BTC/ETH/USDT implied rates to detect >1 cycles.
4. **Hawkes Modeling** — fit Hawkes exponential kernel (via `tick`) on synthetic trade timestamps (falls back to interarrival histogram if `tick` not available).
5. **WS Orderbook Client Demo** — connect to mock WS and reconstruct/update L2 in real time.
6. **Portfolio Hedging** — quick PCA on synthetic multi-asset series for factor hedging intuition.
7. **Price Discovery** — lead–lag / correlation sketch between two venues (mocked).
8. **Signature Optimal Stopping** — generate a path, call **Rust** stopping rule, and plot stop point (seaborn visualization).

> For real datasets, drop your CSVs into `data/` and adapt the notebook loaders.

---

## Docker & Compose

**Images:**
- `mock_apis` — FastAPI server (REST+WS), with synthetic data in `/data`.
- `lab` — Jupyter environment with all Python libs from `docker/requirements.txt`.

**Run:**
```bash
docker compose up --build
# Jupyter → http://localhost:8888
# Mock API health → http://localhost:8000/health
```

---

## GitHub Actions (CI & Release)

### CI on push / PR
Workflow: `.github/workflows/build_and_package.yml`
- Sets up **Python 3.11** and **Rust** (stable)
- Installs **maturin** and builds the PyO3 module (`maturin develop --release`)
- Installs Python deps from `docker/requirements.txt`
- Runs tests in `tests/`
- Uploads an artifact zip **rust-hft-arbitrage-lab.zip**

### Release on tag `vX.Y.Z`
Workflow: `.github/workflows/release.yml`
- Builds a **wheel**: `rust_python_bindings/dist/*.whl`
- Packages the repo as `rust-hft-arbitrage-lab-<tag>.zip`
- Creates a **GitHub Release** and attaches wheel + zip

**Tag & push to release:**
```bash
git tag -a v0.1.0 -m "Initial release"
git push origin v0.1.0
```

*(Optional PyPI publishing can be added by wiring `MATURIN_PYPI_TOKEN` / `PYPI_API_TOKEN` secrets.)*

---

## Data & reproducibility

- **Mocked** venues remove external variability (network, rate limits).
- You can configure **latency** (`latency_ms`) and **depth** on the endpoints to simulate adverse conditions.
- For **determinism**, feed fixed seeds where appropriate in notebooks / mock generators.

---

## Roadmap

- Depth-aware **execution simulator** with queue position model
- More robust **WS connectors** & replay of recorded L2 diffs
- Full **LQG / Riccati** execution policy (Rust solver, Python interface)
- **MLE calibration** for OU/Hawkes on real tick data
- Portfolio construction & **multi-asset hedging** templates
- CI matrix: Linux/macOS/Windows + publish wheel on Release

---

## References

- Bergault, Drissi & Guéant. *Multi-Asset Optimal Execution and Statistical Arbitrage under OU Dynamics*. SSRN 4319255.
- **Hawkes** processes: [`tick` documentation](https://x-datainitiative.github.io/tick/)
- nkaz001/**hftbacktest** tutorials (market making & grid, order book imbalance)
- Gatheral, Jaisson, Rosenbaum — *Volatility is rough* (for stylized facts)
- Bouchaud, Farmer, Lillo — *Market Impact* literature

---

## Contributing

Contributions are welcome!  
Please open issues for bugs/ideas and PRs with focused changes.  
Before submitting:
- Make sure **tests pass** (`pytest -q`)
- Run notebooks you touched (keep outputs small / or clear them)
- Document new endpoints/params in this README

---

## License

**Apache 2.0** — see [LICENSE](./LICENSE).
