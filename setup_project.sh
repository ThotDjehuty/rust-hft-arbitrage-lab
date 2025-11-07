#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(pwd)/rust-hft-arbitrage-lab-mods"
echo "Création de l'arborescence dans ${ROOT_DIR}"
rm -rf "${ROOT_DIR}"
mkdir -p "${ROOT_DIR}"

# helper to write files
write() {
  local path="$1"; shift
  local content="$@"
  mkdir -p "$(dirname "${ROOT_DIR}/${path}")"
  cat > "${ROOT_DIR}/${path}" <<'EOF'
'"$content"'
EOF
}

# Because embedding large literals with single call is cumbersome, we will use a here-doc approach per file.
# Create directories and files (list abbreviated here; full content should be pasted per file)
mkdir -p "${ROOT_DIR}/rust_core/connectors/common/src"
cat > "${ROOT_DIR}/rust_core/connectors/common/Cargo.toml" <<'EOF'
[package]
name = "connectors_common"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
chrono = { version = "0.4", features = ["serde"] }
thiserror = "1.0"
EOF

cat > "${ROOT_DIR}/rust_core/connectors/common/src/lib.rs" <<'EOF'
pub mod types;
pub mod errors;
EOF

cat > "${ROOT_DIR}/rust_core/connectors/common/src/types.rs" <<'EOF'
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarketTick {
    pub exchange: String,
    pub pair: String,
    pub bid: f64,
    pub ask: f64,
    pub ts: u128,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBookLevel {
    pub price: f64,
    pub qty: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBookSnapshot {
    pub exchange: String,
    pub pair: String,
    pub bids: Vec<OrderBookLevel>,
    pub asks: Vec<OrderBookLevel>,
    pub ts: u128,
}
EOF

cat > "${ROOT_DIR}/rust_core/connectors/common/src/errors.rs" <<'EOF'
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ConnectorError {
    #[error("network error: {0}")]
    Network(String),

    #[error("parse error: {0}")]
    Parse(String),

    #[error("other: {0}")]
    Other(String),
}
EOF

# Create binance connector
mkdir -p "${ROOT_DIR}/rust_core/connectors/binance/src"
cat > "${ROOT_DIR}/rust_core/connectors/binance/Cargo.toml" <<'EOF'
[package]
name = "connector_binance"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1", features = ["full"] }
tokio-tungstenite = "0.20"
tungstenite = "0.20"
futures = "0.3"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
connectors_common = { path = "../common" }
log = "0.4"
env_logger = "0.10"
reqwest = { version = "0.11", features = ["json", "rustls-tls"] }
EOF

cat > "${ROOT_DIR}/rust_core/connectors/binance/src/lib.rs" <<'EOF'
pub mod ws;
pub mod rest;
EOF

cat > "${ROOT_DIR}/rust_core/connectors/binance/src/ws.rs" <<'EOF'
use connectors_common::types::MarketTick;
use futures::{SinkExt, StreamExt};
use tokio::sync::mpsc::Sender;
use tokio_tungstenite::connect_async;
use tungstenite::Message;
use serde_json::Value;
use log::{info, warn};

pub async fn run_binance_ws(mut tx: Sender<MarketTick>) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let url = "wss://stream.binance.com:9443/ws/!miniTicker@arr";
    info!("Connecting to {}", url);
    let (ws_stream, _) = connect_async(url).await?;
    let (_, mut read) = ws_stream.split();
    while let Some(msg) = read.next().await {
        match msg {
            Ok(Message::Text(txt)) => {
                if let Ok(v) = serde_json::from_str::<Value>(&txt) {
                    if let Some(arr) = v.as_array() {
                        for item in arr {
                            let s = item.get("s").and_then(|v| v.as_str()).unwrap_or_default().to_string();
                            let bid = item.get("b").and_then(|v| v.as_str()).and_then(|s| s.parse::<f64>().ok()).unwrap_or(0.0);
                            let ask = item.get("a").and_then(|v| v.as_str()).and_then(|s| s.parse::<f64>().ok()).unwrap_or(0.0);
                            let tick = MarketTick {
                                exchange: "binance".to_string(),
                                pair: s,
                                bid,
                                ask,
                                ts: chrono::Utc::now().timestamp_millis() as u128,
                            };
                            let _ = tx.send(tick).await;
                        }
                    } else {
                        if let (Some(symbol), Some(b), Some(a)) = (
                            v.get("s").and_then(|v| v.as_str()),
                            v.get("b").and_then(|v| v.as_str()),
                            v.get("a").and_then(|v| v.as_str()),
                        ) {
                            if let (Ok(bf), Ok(af)) = (b.parse::<f64>(), a.parse::<f64>()) {
                                let tick = MarketTick {
                                    exchange: "binance".to_string(),
                                    pair: symbol.to_string(),
                                    bid: bf,
                                    ask: af,
                                    ts: chrono::Utc::now().timestamp_millis() as u128,
                                };
                                let _ = tx.send(tick).await;
                            }
                        }
                    }
                } else {
                    warn!("failed to parse binance ws message");
                }
            }
            Ok(_) => {}
            Err(e) => {
                warn!("ws error: {:?}", e);
            }
        }
    }
    Ok(())
}
EOF

cat > "${ROOT_DIR}/rust_core/connectors/binance/src/rest.rs" <<'EOF'
use connectors_common::types::{OrderBookSnapshot, OrderBookLevel};
use reqwest::Client;
use std::time::Duration;

pub async fn fetch_orderbook(pair: &str) -> Result<OrderBookSnapshot, Box<dyn std::error::Error + Send + Sync>> {
    let url = format!("https://api.binance.com/api/v3/depth?symbol={}&limit=5", pair);
    let client = Client::new();
    let resp = client.get(&url).timeout(Duration::from_secs(5)).send().await?.text().await?;
    let v: serde_json::Value = serde_json::from_str(&resp)?;
    let mut bids = vec![];
    let mut asks = vec![];
    if let Some(b) = v.get("bids").and_then(|v| v.as_array()) {
        for it in b.iter().take(5) {
            if let (Some(p), Some(q)) = (it.get(0).and_then(|s| s.as_str()), it.get(1).and_then(|s| s.as_str())) {
                bids.push(OrderBookLevel { price: p.parse().unwrap_or(0.0), qty: q.parse().unwrap_or(0.0) });
            }
        }
    }
    if let Some(a) = v.get("asks").and_then(|v| v.as_array()) {
        for it in a.iter().take(5) {
            if let (Some(p), Some(q)) = (it.get(0).and_then(|s| s.as_str()), it.get(1).and_then(|s| s.as_str())) {
                asks.push(OrderBookLevel { price: p.parse().unwrap_or(0.0), qty: q.parse().unwrap_or(0.0) });
            }
        }
    }
    Ok(OrderBookSnapshot {
        exchange: "binance".to_string(),
        pair: pair.to_string(),
        bids,
        asks,
        ts: chrono::Utc::now().timestamp_millis() as u128,
    })
}
EOF

# Create kraken connector
mkdir -p "${ROOT_DIR}/rust_core/connectors/kraken/src"
cat > "${ROOT_DIR}/rust_core/connectors/kraken/Cargo.toml" <<'EOF'
[package]
name = "connector_kraken"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1", features = ["full"] }
tokio-tungstenite = "0.20"
tungstenite = "0.20"
futures = "0.3"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
reqwest = { version = "0.11", features = ["json", "rustls-tls"] }
connectors_common = { path = "../common" }
log = "0.4"
env_logger = "0.10"
EOF

cat > "${ROOT_DIR}/rust_core/connectors/kraken/src/lib.rs" <<'EOF'
pub mod ws;
pub mod rest;
EOF

cat > "${ROOT_DIR}/rust_core/connectors/kraken/src/ws.rs" <<'EOF'
use connectors_common::types::MarketTick;
use futures::{SinkExt, StreamExt};
use tokio::sync::mpsc::Sender;
use tokio_tungstenite::connect_async;
use tungstenite::Message;
use serde_json::Value;
use log::{info, warn};

pub async fn run_kraken_ws(mut tx: Sender<MarketTick>) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let url = "wss://ws.kraken.com";
    info!("Connecting to {}", url);
    let (ws_stream, _) = connect_async(url).await?;
    let (mut write, mut read) = ws_stream.split();

    let subscribe = serde_json::json!({
        "event": "subscribe",
        "subscription": { "name": "ticker" },
        "pair": ["XBT/USD","ETH/USD"]
    });
    let _ = write.send(Message::Text(subscribe.to_string())).await;

    while let Some(msg) = read.next().await {
        match msg {
            Ok(Message::Text(txt)) => {
                if let Ok(v) = serde_json::from_str::<Value>(&txt) {
                    if v.is_array() {
                        if let Some(arr) = v.as_array() {
                            if arr.len() >= 3 {
                                let pair = arr[2].as_str().unwrap_or_default().to_string();
                                let data = &arr[1];
                                if let (Some(bid), Some(ask)) = (
                                    data.get("b").and_then(|v| v.as_array()).and_then(|a| a.get(0)).and_then(|s| s.as_str()).and_then(|s| s.parse::<f64>().ok()),
                                    data.get("a").and_then(|v| v.as_array()).and_then(|a| a.get(0)).and_then(|s| s.as_str()).and_then(|s| s.parse::<f64>().ok())
                                ) {
                                    let tick = MarketTick {
                                        exchange: "kraken".to_string(),
                                        pair,
                                        bid,
                                        ask,
                                        ts: chrono::Utc::now().timestamp_millis() as u128,
                                    };
                                    let _ = tx.send(tick).await;
                                }
                            }
                        }
                    } else {
                    }
                } else {
                    warn!("failed to parse kraken ws msg");
                }
            }
            Ok(_) => {}
            Err(e) => warn!("kraken ws error: {:?}", e),
        }
    }
    Ok(())
}
EOF

cat > "${ROOT_DIR}/rust_core/connectors/kraken/src/rest.rs" <<'EOF'
use connectors_common::types::{OrderBookSnapshot, OrderBookLevel};
use reqwest::Client;
use std::time::Duration;

pub async fn fetch_orderbook(pair: &str) -> Result<OrderBookSnapshot, Box<dyn std::error::Error + Send + Sync>> {
    let url = format!("https://api.kraken.com/0/public/Depth?pair={}&count=5", pair);
    let client = Client::new();
    let resp = client.get(&url).timeout(Duration::from_secs(5)).send().await?.text().await?;
    let v: serde_json::Value = serde_json::from_str(&resp)?;
    let mut bids = vec![];
    let mut asks = vec![];
    if let Some(result) = v.get("result") {
        if let Some((_, book)) = result.as_object().and_then(|m| m.iter().next()) {
            if let Some(b) = book.get("bids").and_then(|v| v.as_array()) {
                for it in b.iter().take(5) {
                    if let (Some(p), Some(q)) = (it.get(0).and_then(|s| s.as_str()), it.get(1).and_then(|s| s.as_str())) {
                        bids.push(OrderBookLevel { price: p.parse().unwrap_or(0.0), qty: q.parse().unwrap_or(0.0) });
                    }
                }
            }
            if let Some(a) = book.get("asks").and_then(|v| v.as_array()) {
                for it in a.iter().take(5) {
                    if let (Some(p), Some(q)) = (it.get(0).and_then(|s| s.as_str()), it.get(1).and_then(|s| s.as_str())) {
                        asks.push(OrderBookLevel { price: p.parse().unwrap_or(0.0), qty: q.parse().unwrap_or(0.0) });
                    }
                }
            }
        }
    }
    Ok(OrderBookSnapshot {
        exchange: "kraken".to_string(),
        pair: pair.to_string(),
        bids,
        asks,
        ts: chrono::Utc::now().timestamp_millis() as u128,
    })
}
EOF

# Create coinbase connector
mkdir -p "${ROOT_DIR}/rust_core/connectors/coinbase/src"
cat > "${ROOT_DIR}/rust_core/connectors/coinbase/Cargo.toml" <<'EOF'
[package]
name = "connector_coinbase"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1", features = ["full"] }
tokio-tungstenite = "0.20"
tungstenite = "0.20"
futures = "0.3"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
reqwest = { version = "0.11", features = ["json", "rustls-tls"] }
connectors_common = { path = "../common" }
log = "0.4"
env_logger = "0.10"
EOF

cat > "${ROOT_DIR}/rust_core/connectors/coinbase/src/lib.rs" <<'EOF'
pub mod ws;
pub mod rest;
EOF

cat > "${ROOT_DIR}/rust_core/connectors/coinbase/src/ws.rs" <<'EOF'
use connectors_common::types::MarketTick;
use futures::{SinkExt, StreamExt};
use tokio::sync::mpsc::Sender;
use tokio_tungstenite::connect_async;
use tungstenite::Message;
use serde_json::Value;
use log::{info, warn};

pub async fn run_coinbase_ws(mut tx: Sender<MarketTick>) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let url = "wss://ws-feed.pro.coinbase.com";
    info!("Connecting to {}", url);
    let (ws_stream, _) = connect_async(url).await?;
    let (mut write, mut read) = ws_stream.split();

    let subscribe = serde_json::json!({
        "type": "subscribe",
        "product_ids": ["BTC-USD", "ETH-USD"],
        "channels": ["ticker"]
    });
    let _ = write.send(Message::Text(subscribe.to_string())).await;

    while let Some(msg) = read.next().await {
        match msg {
            Ok(Message::Text(txt)) => {
                if let Ok(v) = serde_json::from_str::<Value>(&txt) {
                    if v.get("type").and_then(|t| t.as_str()) == Some("ticker") {
                        let pair = v.get("product_id").and_then(|s| s.as_str()).unwrap_or_default().to_string();
                        let bid = v.get("best_bid").and_then(|s| s.as_str()).and_then(|s| s.parse::<f64>().ok()).unwrap_or(0.0);
                        let ask = v.get("best_ask").and_then(|s| s.as_str()).and_then(|s| s.parse::<f64>().ok()).unwrap_or(0.0);
                        let tick = MarketTick {
                            exchange: "coinbase".to_string(),
                            pair,
                            bid,
                            ask,
                            ts: chrono::Utc::now().timestamp_millis() as u128,
                        };
                        let _ = tx.send(tick).await;
                    }
                } else {
                    warn!("failed to parse coinbase ws message");
                }
            }
            Ok(_) => {}
            Err(e) => warn!("coinbase ws error: {:?}", e),
        }
    }
    Ok(())
}
EOF

cat > "${ROOT_DIR}/rust_core/connectors/coinbase/src/rest.rs" <<'EOF'
use connectors_common::types::{OrderBookSnapshot, OrderBookLevel};
use reqwest::Client;
use std::time::Duration;

pub async fn fetch_orderbook(pair: &str) -> Result<OrderBookSnapshot, Box<dyn std::error::Error + Send + Sync>> {
    let url = format!("https://api.pro.coinbase.com/products/{}/book?level=1", pair);
    let client = Client::new();
    let resp = client.get(&url).timeout(Duration::from_secs(5)).send().await?.text().await?;
    let v: serde_json::Value = serde_json::from_str(&resp)?;
    let mut bids = vec![];
    let mut asks = vec![];
    if let Some(b) = v.get("bids").and_then(|v| v.as_array()) {
        for it in b.iter().take(5) {
            if let (Some(p), Some(q)) = (it.get(0).and_then(|s| s.as_str()), it.get(1).and_then(|s| s.as_str())) {
                bids.push(OrderBookLevel { price: p.parse().unwrap_or(0.0), qty: q.parse().unwrap_or(0.0) });
            }
        }
    }
    if let Some(a) = v.get("asks").and_then(|v| v.as_array()) {
        for it in a.iter().take(5) {
            if let (Some(p), Some(q)) = (it.get(0).and_then(|s| s.as_str()), it.get(1).and_then(|s| s.as_str())) {
                asks.push(OrderBookLevel { price: p.parse().unwrap_or(0.0), qty: q.parse().unwrap_or(0.0) });
            }
        }
    }
    Ok(OrderBookSnapshot {
        exchange: "coinbase".to_string(),
        pair: pair.to_string(),
        bids,
        asks,
        ts: chrono::Utc::now().timestamp_millis() as u128,
    })
}
EOF

# Create coingecko connector
mkdir -p "${ROOT_DIR}/rust_core/connectors/coingecko/src"
cat > "${ROOT_DIR}/rust_core/connectors/coingecko/Cargo.toml" <<'EOF'
[package]
name = "connector_coingecko"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1", features = ["full"] }
reqwest = { version = "0.11", features = ["json", "rustls-tls"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
connectors_common = { path = "../common" }
log = "0.4"
env_logger = "0.10"
EOF

cat > "${ROOT_DIR}/rust_core/connectors/coingecko/src/lib.rs" <<'EOF'
pub mod rest;
EOF

cat > "${ROOT_DIR}/rust_core/connectors/coingecko/src/rest.rs" <<'EOF'
use connectors_common::types::MarketTick;
use reqwest::Client;
use std::time::Duration;
use tokio::time::{sleep, Duration as TokioDuration};
use log::info;

pub async fn run_coingecko_poll(mut tx: tokio::sync::mpsc::Sender<MarketTick>, pairs: Vec<String>, interval_ms: u64) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let client = Client::new();
    let interval = TokioDuration::from_millis(interval_ms);
    loop {
        for pair in pairs.iter() {
            let parts: Vec<&str> = pair.split('/').collect();
            let (id, vs) = if parts.len() == 2 { (parts[0], parts[1]) } else { (pair.as_str(), "usd") };
            let url = format!("https://api.coingecko.com/api/v3/simple/price?ids={}&vs_currencies={}", id, vs);
            match client.get(&url).timeout(Duration::from_secs(5)).send().await {
                Ok(resp) => {
                    if let Ok(text) = resp.text().await {
                        if let Ok(v) = serde_json::from_str::<serde_json::Value>(&text) {
                            if let Some(price) = v.get(id).and_then(|o| o.get(vs)).and_then(|p| p.as_f64()) {
                                let tick = MarketTick {
                                    exchange: "coingecko".to_string(),
                                    pair: pair.clone(),
                                    bid: price,
                                    ask: price,
                                    ts: chrono::Utc::now().timestamp_millis() as u128,
                                };
                                let _ = tx.send(tick).await;
                            }
                        }
                    }
                }
                Err(e) => {
                    info!("coingecko poll error for {}: {:?}", pair, e);
                }
            }
        }
        sleep(interval).await;
    }
}
EOF

# Create aggregator crate
mkdir -p "${ROOT_DIR}/rust_core/aggregator/src"
cat > "${ROOT_DIR}/rust_core/aggregator/Cargo.toml" <<'EOF'
[package]
name = "aggregator"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1", features = ["full"] }
connectors_common = { path = "../connectors/common" }
log = "0.4"
env_logger = "0.10"
serde = { version = "1.0", features = ["derive"] }
EOF

cat > "${ROOT_DIR}/rust_core/aggregator/src/lib.rs" <<'EOF'
use connectors_common::types::MarketTick;
use tokio::sync::{mpsc, broadcast};
use log::info;

pub struct Aggregator {
    tx: broadcast::Sender<MarketTick>,
}

impl Aggregator {
    pub fn new(buffer: usize) -> Self {
        let (tx, _) = broadcast::channel(buffer);
        Aggregator { tx }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<MarketTick> {
        self.tx.subscribe()
    }

    pub fn sender(&self) -> broadcast::Sender<MarketTick> {
        self.tx.clone()
    }

    pub fn create_input_channel(&self, buffer: usize) -> mpsc::Sender<MarketTick> {
        let (tx, mut rx) = mpsc::channel(buffer);
        let tx_b = self.tx.clone();
        tokio::spawn(async move {
            while let Some(tick) = rx.recv().await {
                let _ = tx_b.send(tick);
            }
            info!("aggregator input channel closed");
        });
        tx
    }
}
EOF

# Create rust_python_bindings crate
mkdir -p "${ROOT_DIR}/rust_python_bindings/src"
cat > "${ROOT_DIR}/rust_python_bindings/Cargo.toml" <<'EOF'
[package]
name = "rust_python_bindings"
version = "0.1.0"
edition = "2021"

[lib]
name = "hft_py"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.18", features = ["extension-module", "auto-initialize"] }
pyo3-asyncio = { version = "0.18", features = ["tokio-runtime"] }
tokio = { version = "1", features = ["rt-multi-thread", "macros", "time"] }
connectors_common = { path = "../rust_core/connectors/common" }
aggregator = { path = "../rust_core/aggregator" }
connector_binance = { path = "../rust_core/connectors/binance" }
connector_kraken = { path = "../rust_core/connectors/kraken" }
connector_coinbase = { path = "../rust_core/connectors/coinbase" }
connector_coingecko = { path = "../rust_core/connectors/coingecko" }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
EOF

cat > "${ROOT_DIR}/rust_python_bindings/src/lib.rs" <<'EOF'
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_asyncio::tokio::future_into_py;
use connectors_common::types::MarketTick;
use aggregator::Aggregator;
use tokio::sync::{mpsc, broadcast, oneshot};
use std::sync::{Arc, Mutex};
use std::collections::HashMap;
use log::info;

type HandleId = u64;

struct ConnectorHandle {
    stop_tx: oneshot::Sender<()>,
}

#[pyclass]
struct PyAggregator {
    inner: Arc<Aggregator>,
    handles: Arc<Mutex<HashMap<HandleId, ConnectorHandle>>>,
    next_handle: Arc<Mutex<HandleId>>,
}

#[pymethods]
impl PyAggregator {
    #[new]
    fn new() -> Self {
        let agg = Aggregator::new(1024);
        PyAggregator {
            inner: Arc::new(agg),
            handles: Arc::new(Mutex::new(HashMap::new())),
            next_handle: Arc::new(Mutex::new(1)),
        }
    }

    fn subscribe<'py>(&self, py: Python<'py>, callback: PyObject) -> PyResult<&'py PyAny> {
        let mut rx = self.inner.subscribe();
        let cb = callback.clone();
        future_into_py(py, async move {
            loop {
                match rx.recv().await {
                    Ok(tick) => {
                        Python::with_gil(|py| {
                            let dict = PyDict::new(py);
                            dict.set_item("exchange", tick.exchange.clone()).ok();
                            dict.set_item("pair", tick.pair.clone()).ok();
                            dict.set_item("bid", tick.bid).ok();
                            dict.set_item("ask", tick.ask).ok();
                            dict.set_item("ts", tick.ts).ok();
                            let _ = cb.call1(py, (dict,));
                        });
                    }
                    Err(broadcast::error::RecvError::Closed) => break,
                    Err(broadcast::error::RecvError::Lagged(_)) => continue,
                }
            }
            Ok(())
        })
    }

    fn create_input_channel_py(&self, buffer: usize) -> PyResult<usize> {
        let tx = self.inner.create_input_channel(buffer);
        let boxed = Box::new(tx);
        let ptr = Box::into_raw(boxed) as usize;
        Ok(ptr)
    }

    unsafe fn drop_input_channel_py(&self, ptr: usize) -> PyResult<()> {
        if ptr == 0 { return Ok(()) }
        let _boxed: Box<mpsc::Sender<MarketTick>> = Box::from_raw(ptr as *mut _);
        Ok(())
    }

    fn start_binance_ws(&self, _pairs: Option<Vec<String>>) -> PyResult<u64> {
        let tx = self.inner.create_input_channel(1024);
        let (stop_tx, _stop_rx) = oneshot::channel();
        tokio::spawn(async move {
            let _ = connector_binance::ws::run_binance_ws(tx).await;
        });
        let mut nh = self.next_handle.lock().unwrap();
        let id = *nh;
        *nh += 1;
        self.handles.lock().unwrap().insert(id, ConnectorHandle { stop_tx });
        Ok(id)
    }

    fn start_kraken_ws(&self, _pairs: Option<Vec<String>>) -> PyResult<u64> {
        let tx = self.inner.create_input_channel(1024);
        let (stop_tx, _stop_rx) = oneshot::channel();
        tokio::spawn(async move {
            let _ = connector_kraken::ws::run_kraken_ws(tx).await;
        });
        let mut nh = self.next_handle.lock().unwrap();
        let id = *nh;
        *nh += 1;
        self.handles.lock().unwrap().insert(id, ConnectorHandle { stop_tx });
        Ok(id)
    }

    fn start_coinbase_ws(&self, _pairs: Option<Vec<String>>) -> PyResult<u64> {
        let tx = self.inner.create_input_channel(1024);
        let (stop_tx, _stop_rx) = oneshot::channel();
        tokio::spawn(async move {
            let _ = connector_coinbase::ws::run_coinbase_ws(tx).await;
        });
        let mut nh = self.next_handle.lock().unwrap();
        let id = *nh;
        *nh += 1;
        self.handles.lock().unwrap().insert(id, ConnectorHandle { stop_tx });
        Ok(id)
    }

    fn start_coingecko_poll(&self, pairs: Vec<String>, interval_ms: Option<u64>) -> PyResult<u64> {
        let tx = self.inner.create_input_channel(1024);
        let (stop_tx, _stop_rx) = oneshot::channel();
        let int_ms = interval_ms.unwrap_or(5000);
        tokio::spawn(async move {
            let _ = connector_coingecko::rest::run_coingecko_poll(tx, pairs, int_ms).await;
        });
        let mut nh = self.next_handle.lock().unwrap();
        let id = *nh;
        *nh += 1;
        self.handles.lock().unwrap().insert(id, ConnectorHandle { stop_tx });
        Ok(id)
    }

    fn stop_connector(&self, handle: u64) -> PyResult<bool> {
        if let Some(h) = self.handles.lock().unwrap().remove(&handle) {
            let _ = h.stop_tx.send(());
            Ok(true)
        } else {
            Ok(false)
        }
    }
}

#[pymodule]
fn hft_py(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyAggregator>()?;
    Ok(())
}
EOF

# Create Makefile and package.sh at root
cat > "${ROOT_DIR}/Makefile" <<'EOF'
.PHONY: build test package clean

build:
    cargo build -p rust_python_bindings --release
    cargo build -p aggregator --release
    cargo build -p connector_binance --release || true
    cargo build -p connector_kraken --release || true
    cargo build -p connector_coinbase --release || true
    cargo build -p connector_coingecko --release || true

test:
    cargo test --all

package: build test
    @rm -f rust-hft-arbitrage-lab-mods.zip
    zip -r rust-hft-arbitrage-lab-mods.zip . -x "target/*" -x ".git/*" -x "venv/*" -x "__pycache__/*"
    @echo "Created rust-hft-arbitrage-lab-mods.zip in repo root"

clean:
    cargo clean
    @rm -f rust-hft-arbitrage-lab-mods.zip
EOF

cat > "${ROOT_DIR}/package.sh" <<'EOF'
#!/usr/bin/env bash
set -e
make package
echo "Package ready: rust-hft-arbitrage-lab-mods.zip"
EOF
chmod +x "${ROOT_DIR}/package.sh"

echo "Fichiers créés sous ${ROOT_DIR}."
echo "Pour builder et zipper, cd ${ROOT_DIR} && ./package.sh"
echo "Une fois le zip créé, tu peux le téléverser vers Google Drive via l'interface web ou rclone."
