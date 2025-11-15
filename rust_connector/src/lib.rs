//! Async Rust connectors: Binance, Coinbase, Uniswap (reserves reader).
//! Exposes PyO3 classes & helpers to Python.
//!
//! Key exports:
//! - OrderBook (pyclass)
//! - ExchangeConnector (pyclass) — used as generic connector; get_connector(name) returns an instance.
//!    - list_symbols()
//!    - fetch_orderbook_sync(symbol)
//!    - start_stream(py, symbol, callback)
//!    - latest_snapshot()
//! - uniswap_get_reserves(rpc_url, pair_address)
//! - compute_dex_cex_arbitrage(ob_cex, ob_dex, fee_cex, fee_dex)

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::{Arc, Mutex};
use futures_util::{StreamExt, SinkExt};
use tokio_tungstenite::connect_async;
use tokio_tungstenite::tungstenite::Message;
use env_logger;
use log::{info, warn};
use fastrand;

/// OrderBook struct sent to Python
#[pyclass]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OrderBook {
    #[pyo3(get)]
    pub bids: Vec<(f64, f64)>,
    #[pyo3(get)]
    pub asks: Vec<(f64, f64)>,
}

#[pymethods]
impl OrderBook {
    #[new]
    fn new(bids: Vec<(f64, f64)>, asks: Vec<(f64, f64)>) -> Self {
        OrderBook { bids, asks }
    }

    fn top(&self) -> PyResult<(f64, f64)> {
        Ok((
            self.bids.get(0).map(|(p, _)| *p).unwrap_or(0.0),
            self.asks.get(0).map(|(p, _)| *p).unwrap_or(0.0),
        ))
    }
}

type Snapshot = Arc<Mutex<Option<OrderBook>>>;

/// Generic connector. Concrete behavior chosen by name.
#[pyclass]
pub struct ExchangeConnector {
    name: String,
    snapshot: Snapshot,
}

#[pymethods]
impl ExchangeConnector {
    #[new]
    fn new(name: String) -> Self {
        let _ = env_logger::try_init();
        ExchangeConnector {
            name,
            snapshot: Arc::new(Mutex::new(None)),
        }
    }

    fn list_symbols(&self) -> PyResult<Vec<String>> {
        let lower = self.name.to_lowercase();
        if lower.contains("binance") {
            Ok(vec!["BTCUSDT".to_string(), "ETHUSDT".to_string(), "BNBUSDT".to_string()])
        } else if lower.contains("coinbase") {
            Ok(vec!["BTC-USD".to_string(), "ETH-USD".to_string()])
        } else if lower.contains("kraken") {
            Ok(vec!["XBTUSDT".to_string(), "ETHUSDT".to_string(), "XXBTZUSD".to_string()])
        } else if lower.contains("uniswap") {
            Ok(vec!["UNI/ETH".to_string(), "USDC/ETH".to_string()])
        } else {
            Ok(vec!["BTC-USD".to_string(), "ETH-USD".to_string()])
        }
    }

    /// Blocking snapshot via REST for simplicity
    fn fetch_orderbook_sync(&self, symbol: String) -> PyResult<OrderBook> {
        let lower = self.name.to_lowercase();
        if lower.contains("binance") {
            let url = format!(
                "https://api.binance.com/api/v3/depth?symbol={}&limit=5",
                symbol.to_uppercase()
            );
            match reqwest::blocking::get(&url) {
                Ok(resp) => match resp.json::<Value>() {
                    Ok(v) => {
                        let bids = parse_binance_rest(&v, "b");
                        let asks = parse_binance_rest(&v, "a");
                        return Ok(OrderBook::new(bids, asks));
                    }
                    Err(e) => return Err(pyo3::exceptions::PyRuntimeError::new_err(format!("json parse: {:?}", e))),
                },
                Err(e) => return Err(pyo3::exceptions::PyRuntimeError::new_err(format!("request: {:?}", e))),
            }
        } else if lower.contains("coinbase") {
            let url = format!("https://api.exchange.coinbase.com/products/{}/book?level=2", symbol);
            match reqwest::blocking::get(&url) {
                Ok(resp) => match resp.json::<Value>() {
                    Ok(v) => {
                        let bids = parse_coinbase_rest(&v, "bids");
                        let asks = parse_coinbase_rest(&v, "asks");
                        return Ok(OrderBook::new(bids, asks));
                    }
                    Err(e) => return Err(pyo3::exceptions::PyRuntimeError::new_err(format!("json parse: {:?}", e))),
                },
                Err(e) => return Err(pyo3::exceptions::PyRuntimeError::new_err(format!("request: {:?}", e))),
            }
        } else if lower.contains("kraken") {
            let url = format!("https://api.kraken.com/0/public/Depth?pair={}&count=5", symbol);
            match reqwest::blocking::get(&url) {
                Ok(resp) => match resp.json::<Value>() {
                    Ok(v) => {
                        let bids = parse_kraken_rest(&v, "bids");
                        let asks = parse_kraken_rest(&v, "asks");
                        return Ok(OrderBook::new(bids, asks));
                    }
                    Err(e) => return Err(pyo3::exceptions::PyRuntimeError::new_err(format!("json parse: {:?}", e))),
                },
                Err(e) => return Err(pyo3::exceptions::PyRuntimeError::new_err(format!("request: {:?}", e))),
            }
        } else {
            // synthetic fallback
            let mid = 100.0;
            let spread = 0.001;
            let bid = mid * (1.0 - spread / 2.0);
            let ask = mid * (1.0 + spread / 2.0);
            let bids = vec![(bid, 1.0), (bid * 0.999, 2.0)];
            let asks = vec![(ask, 1.0), (ask * 1.001, 2.0)];
            Ok(OrderBook::new(bids, asks))
        }
    }

    /// Start streaming; callback is a Python callable that receives an OrderBook pyobject.
    /// Spawns a tokio task for async WebSocket handling.
    fn start_stream(&mut self, _py: Python<'_>, symbol: String, py_callback: PyObject) -> PyResult<()> {
        let snapshot = self.snapshot.clone();
        let name = self.name.clone();
        let cb = py_callback.clone();

        // Spawn in a new thread with its own tokio runtime
        std::thread::spawn(move || {
            let rt = tokio::runtime::Runtime::new().expect("Failed to create tokio runtime");
            rt.block_on(async move {
            let lower = name.to_lowercase();
            if lower.contains("binance") {
                let url = format!("wss://stream.binance.com:9443/ws/{}@depth5@100ms", symbol.to_lowercase());
                match connect_async(&url).await {
                    Ok((ws_stream, _)) => {
                        info!("Connected to Binance {}", url);
                        let (_write, mut read) = ws_stream.split();
                        while let Some(msg) = read.next().await {
                            match msg {
                                Ok(Message::Text(txt)) => {
                                    if let Ok(ob) = parse_binance_depth_text(&txt) {
                                        if let Ok(mut s) = snapshot.lock() { *s = Some(ob.clone()); }
                                        Python::with_gil(|py| {
                                            let cb_ref = cb.bind(py);
                                            if let Ok(py_ob) = Py::new(py, ob.clone()) {
                                                let _ = cb_ref.call1((py_ob,));
                                            }
                                        });
                                    }
                                }
                                Ok(Message::Ping(_)) | Ok(Message::Pong(_)) => {}
                                Ok(Message::Close(_)) => break,
                                Err(e) => { warn!("binance ws error: {:?}", e); break; }
                                _ => {}
                            }
                        }
                    }
                    Err(e) => warn!("binance connect error: {:?}", e),
                }
            } else if lower.contains("coinbase") {
                let url = "wss://ws-feed.exchange.coinbase.com";
                match connect_async(url).await {
                    Ok((ws_stream, _)) => {
                        info!("Connected to Coinbase WS");
                        let (mut write, mut read) = ws_stream.split();
                        let subscribe = serde_json::json!({
                            "type":"subscribe",
                            "channels":[{"name":"level2","product_ids":[symbol]}]
                        });
                        let _ = write.send(Message::Text(subscribe.to_string())).await;
                        while let Some(msg) = read.next().await {
                            match msg {
                                Ok(Message::Text(txt)) => {
                                    if let Ok(ob) = parse_coinbase_l2_text(&txt) {
                                        if let Ok(mut s) = snapshot.lock() { *s = Some(ob.clone()); }
                                        Python::with_gil(|py| {
                                            let cb_ref = cb.bind(py);
                                            if let Ok(py_ob) = Py::new(py, ob.clone()) {
                                                let _ = cb_ref.call1((py_ob,));
                                            }
                                        });
                                    }
                                }
                                _ => {}
                            }
                        }
                    }
                    Err(e) => warn!("coinbase connect error: {:?}", e),
                }
            } else if lower.contains("kraken") {
                let url = "wss://ws.kraken.com";
                match connect_async(url).await {
                    Ok((ws_stream, _)) => {
                        info!("Connected to Kraken WS");
                        let (mut write, mut read) = ws_stream.split();
                        let subscribe = serde_json::json!({
                            "event": "subscribe",
                            "pair": [symbol.clone()],
                            "subscription": {"name": "book", "depth": 10}
                        });
                        let _ = write.send(Message::Text(subscribe.to_string())).await;
                        while let Some(msg) = read.next().await {
                            match msg {
                                Ok(Message::Text(txt)) => {
                                    if let Ok(ob) = parse_kraken_ws_text(&txt) {
                                        if let Ok(mut s) = snapshot.lock() { *s = Some(ob.clone()); }
                                        Python::with_gil(|py| {
                                            let cb_ref = cb.bind(py);
                                            if let Ok(py_ob) = Py::new(py, ob.clone()) {
                                                let _ = cb_ref.call1((py_ob,));
                                            }
                                        });
                                    }
                                }
                                _ => {}
                            }
                        }
                    }
                    Err(e) => warn!("kraken connect error: {:?}", e),
                }
            } else {
                // fallback: synthetic stream
                loop {
                    let mid = 100.0 + (fastrand::f64() - 0.5) * 0.5;
                    let spread = 0.001;
                    let bid = (mid * (1.0 - spread / 2.0) * 1e8f64).round() / 1e8f64;
                    let ask = (mid * (1.0 + spread / 2.0) * 1e8f64).round() / 1e8f64;
                    let bids = vec![(bid, 1.0), (bid * 0.999, 2.0)];
                    let asks = vec![(ask, 1.0), (ask * 1.001, 2.0)];
                    let ob = OrderBook::new(bids, asks);
                    if let Ok(mut s) = snapshot.lock() { *s = Some(ob.clone()); }
                    Python::with_gil(|py| {
                        let cb_ref = cb.bind(py);
                        if let Ok(py_ob) = Py::new(py, ob.clone()) {
                            let _ = cb_ref.call1((py_ob,));
                        }
                    });
                    tokio::time::sleep(std::time::Duration::from_millis(500)).await;
                }
            }
            }); // end of rt.block_on
        }); // end of std::thread::spawn

        Ok(())
    }

    fn latest_snapshot(&self) -> PyResult<Option<OrderBook>> {
        if let Ok(s) = self.snapshot.lock() { Ok(s.clone()) } else { Ok(None) }
    }
}

/// Helpers: parse REST & WS payloads

fn parse_binance_rest(v: &Value, key: &str) -> Vec<(f64, f64)> {
    v.get(key)
        .and_then(|x| x.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|it| {
                    let p = it.get(0)?.as_str()?.parse::<f64>().ok()?;
                    let q = it.get(1)?.as_str()?.parse::<f64>().ok()?;
                    Some((p, q))
                })
                .take(5)
                .collect()
        })
        .unwrap_or_default()
}

fn parse_coinbase_rest(v: &Value, key: &str) -> Vec<(f64, f64)> {
    v.get(key)
        .and_then(|x| x.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|it| {
                    let p = it.get(0)?.as_str()?.parse::<f64>().ok()?;
                    let q = it.get(1)?.as_str()?.parse::<f64>().ok()?;
                    Some((p, q))
                })
                .take(5)
                .collect()
        })
        .unwrap_or_default()
}

fn parse_kraken_rest(v: &Value, key: &str) -> Vec<(f64, f64)> {
    // Kraken response format: {"result": {"XBTUSDT": {"bids": [...], "asks": [...]}}}
    v.get("result")
        .and_then(|result| result.as_object())
        .and_then(|obj| obj.values().next()) // Get first pair's data
        .and_then(|pair_data| pair_data.get(key))
        .and_then(|x| x.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|it| {
                    let p = it.get(0)?.as_str()?.parse::<f64>().ok()?;
                    let q = it.get(1)?.as_str()?.parse::<f64>().ok()?;
                    Some((p, q))
                })
                .take(5)
                .collect()
        })
        .unwrap_or_default()
}

fn parse_binance_depth_text(txt: &str) -> Result<OrderBook, serde_json::Error> {
    let v: Value = serde_json::from_str(txt)?;
    let root = if v.get("e").is_some() || v.get("b").is_some() || v.get("a").is_some() {
        v
    } else if let Some(data) = v.get("data") { data.clone() } else { v };
    let bids = root
        .get("b")
        .and_then(|x| x.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|it| {
                    let p = it.get(0)?.as_str()?.parse::<f64>().ok()?;
                    let q = it.get(1)?.as_str()?.parse::<f64>().ok()?;
                    Some((p, q))
                })
                .take(5)
                .collect()
        })
        .unwrap_or_default();
    let asks = root
        .get("a")
        .and_then(|x| x.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|it| {
                    let p = it.get(0)?.as_str()?.parse::<f64>().ok()?;
                    let q = it.get(1)?.as_str()?.parse::<f64>().ok()?;
                    Some((p, q))
                })
                .take(5)
                .collect()
        })
        .unwrap_or_default();
    Ok(OrderBook::new(bids, asks))
}

fn parse_coinbase_l2_text(txt: &str) -> Result<OrderBook, serde_json::Error> {
    let v: Value = serde_json::from_str(txt)?;
    if let Some(t) = v.get("type").and_then(|x| x.as_str()) {
        if t == "snapshot" {
            let bids = parse_coinbase_rest(&v, "bids");
            let asks = parse_coinbase_rest(&v, "asks");
            return Ok(OrderBook::new(bids, asks));
        } else if t == "l2update" {
            // For simplicity, produce a tiny update (production: apply deltas to maintained book)
            let bids = vec![(100.0, 1.0)];
            let asks = vec![(100.2, 1.0)];
            return Ok(OrderBook::new(bids, asks));
        }
    }
    Ok(OrderBook::new(vec![(100.0, 1.0)], vec![(100.2, 1.0)]))
}

fn parse_kraken_ws_text(txt: &str) -> Result<OrderBook, serde_json::Error> {
    let v: Value = serde_json::from_str(txt)?;
    
    // Kraken WS messages are arrays: [channelID, data, channelName, pair]
    if let Some(arr) = v.as_array() {
        if arr.len() >= 2 {
            // Check if it's a book update
            if let Some(data) = arr.get(1).and_then(|d| d.as_object()) {
                // Snapshot format: {"as": [[price, vol, timestamp]], "bs": [[price, vol, timestamp]]}
                if data.contains_key("as") && data.contains_key("bs") {
                    let bids = data.get("bs")
                        .and_then(|x| x.as_array())
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|it| {
                                    let p = it.get(0)?.as_str()?.parse::<f64>().ok()?;
                                    let q = it.get(1)?.as_str()?.parse::<f64>().ok()?;
                                    Some((p, q))
                                })
                                .take(5)
                                .collect()
                        })
                        .unwrap_or_default();
                    
                    let asks = data.get("as")
                        .and_then(|x| x.as_array())
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|it| {
                                    let p = it.get(0)?.as_str()?.parse::<f64>().ok()?;
                                    let q = it.get(1)?.as_str()?.parse::<f64>().ok()?;
                                    Some((p, q))
                                })
                                .take(5)
                                .collect()
                        })
                        .unwrap_or_default();
                    
                    return Ok(OrderBook::new(bids, asks));
                }
            }
        }
    }
    
    // Return empty orderbook if parsing fails (not a book update message)
    Ok(OrderBook::new(vec![], vec![]))
}

/// Uniswap pair reserves reader using ethers subcrates.
/// Returns a Python dict {"reserve0": f64, "reserve1": f64}
/// Note: This function releases the GIL while performing the blocking HTTP request.
#[pyfunction]
fn uniswap_get_reserves(py: Python<'_>, rpc_url: String, pair_address: String) -> PyResult<PyObject> {
    use ethers_providers::{Provider, Http};
    use ethers_contract::Contract;
    use ethers_core::types::Address;
    use std::sync::Arc;
    
    // Release GIL for blocking operation
    py.allow_threads(|| {
        // Create tokio runtime for this blocking call
        let rt = tokio::runtime::Runtime::new()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("tokio runtime: {:?}", e)))?;
        
        rt.block_on(async {
            // Minimal ABI for getReserves
            let abi_json = r#"[{"constant":true,"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint112","name":"_reserve0","type":"uint112"},{"internalType":"uint112","name":"_reserve1","type":"uint112"},{"internalType":"uint32","name":"_blockTimestampLast","type":"uint32"}],"payable":false,"stateMutability":"view","type":"function"}]"#;
            let provider = Provider::<Http>::try_from(rpc_url.clone())
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("{:?}", e)))?;
            let addr: Address = pair_address.parse()
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{:?}", e)))?;
            let abi: ethers_core::abi::Abi = serde_json::from_str(abi_json)
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("{:?}", e)))?;
            let contract = Contract::new(addr, abi, Arc::new(provider));
            
            // call getReserves
            let (r0, r1, _ts): (ethers_core::types::U256, ethers_core::types::U256, u32) = contract
                .method("getReserves", ())
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("method error: {:?}", e)))?
                .call()
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("call error: {:?}", e)))?;
            
            let reserve0 = r0.as_u128() as f64;
            let reserve1 = r1.as_u128() as f64;
            
            Python::with_gil(|py| {
                let d = PyDict::new_bound(py);
                let _ = d.set_item("reserve0", reserve0);
                let _ = d.set_item("reserve1", reserve1);
                Ok(d.to_object(py))
            })
        })
    })
}

/// compute dex/cex arbitrage (top-of-book vs dex price)
#[pyfunction]
fn compute_dex_cex_arbitrage(ob_cex: &OrderBook, ob_dex: &OrderBook, fee_cex: f64, fee_dex: f64) -> PyResult<PyObject> {
    Python::with_gil(|py| {
        let cex_bid = ob_cex.bids.get(0).map(|(p, _)| *p).unwrap_or(0.0);
        let cex_ask = ob_cex.asks.get(0).map(|(p, _)| *p).unwrap_or(0.0);
        let dex_price = ob_dex.bids.get(0).map(|(p, _)| *p).unwrap_or(0.0);

        let gross = if dex_price > 0.0 { cex_bid / dex_price - 1.0 } else { 0.0 };
        let net = (1.0 - fee_dex) * (1.0 + gross) * (1.0 - fee_cex) - 1.0;

        let gross2 = if cex_ask > 0.0 { dex_price / cex_ask - 1.0 } else { 0.0 };
        let net2 = (1.0 - fee_cex) * (1.0 + gross2) * (1.0 - fee_dex) - 1.0;

        let root = PyDict::new_bound(py);
        let d1 = PyDict::new_bound(py);
        d1.set_item("gross", gross)?;
        d1.set_item("net", net)?;
        d1.set_item("dex_price", dex_price)?;
        d1.set_item("cex_bid", cex_bid)?;
        let d2 = PyDict::new_bound(py);
        d2.set_item("gross", gross2)?;
        d2.set_item("net", net2)?;
        d2.set_item("cex_ask", cex_ask)?;
        d2.set_item("dex_price", dex_price)?;
        root.set_item("buy_dex_sell_cex", d1)?;
        root.set_item("buy_cex_sell_dex", d2)?;
        Ok(root.to_object(py))
    })
}

/// Factory functions
#[pyfunction]
fn list_connectors() -> Vec<String> {
    vec![
        "binance".to_string(), 
        "coinbase".to_string(), 
        "kraken".to_string(),
        "uniswap".to_string(), 
        "mock".to_string()
    ]
}

#[pyfunction]
fn get_connector(name: &str) -> PyResult<ExchangeConnector> {
    Ok(ExchangeConnector::new(name.to_string()))
}

#[pymodule]
fn rust_connector(m: &Bound<'_, PyModule>) -> PyResult<()> {
    env_logger::init();
    m.add_class::<OrderBook>()?;
    m.add_class::<ExchangeConnector>()?;
    m.add_function(wrap_pyfunction!(uniswap_get_reserves, m)?)?;
    m.add_function(wrap_pyfunction!(compute_dex_cex_arbitrage, m)?)?;
    m.add_function(wrap_pyfunction!(list_connectors, m)?)?;
    m.add_function(wrap_pyfunction!(get_connector, m)?)?;
    Ok(())
}