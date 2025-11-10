use pyo3::prelude::*;
use serde::{Serialize, Deserialize};
use tokio::runtime::Runtime;
use std::thread;

use futures_util::StreamExt;
use tokio_tungstenite::connect_async;
use tokio_tungstenite::tungstenite::Message;

#[pyclass]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OrderBook {
    pub bids: Vec<(f64, f64)>,
    pub asks: Vec<(f64, f64)>,
}

#[pyfunction]
fn parse_orderbook(json: &str) -> PyResult<OrderBook> {
    let ob: OrderBook = serde_json::from_str(json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{}", e)))?;
    Ok(ob)
}

#[pyfunction]
fn compute_triangular_opportunity(_ob1: &OrderBook, _ob2: &OrderBook, _ob3: &OrderBook) -> PyResult<(f64, Vec<String>)> {
    // Simplified placeholder: compute a dummy expected profit and route
    let profit = 0.001; // 0.1%
    let route = vec!["A->B".to_string(), "B->C".to_string(), "C->A".to_string()];
    Ok((profit, route))
}

#[pyfunction]
fn blocking_start_ws(url: &str) -> PyResult<()> {
    // Spawn a thread with a tokio runtime that runs an async WS client.
    // For production use, consider pyo3-asyncio to push events back into Python asyncio.
    let url = url.to_string();
    thread::spawn(move || {
        let rt = Runtime::new().expect("Failed to create tokio runtime");
        rt.block_on(async move {
            if let Err(e) = start_ws_client(&url).await {
                eprintln!("ws error: {}", e);
            }
        });
    });
    Ok(())
}

async fn start_ws_client(url: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let (ws_stream, _resp) = connect_async(url).await?;
    // keep only the read half (we don't write in this example)
    let (_write_unused, mut read) = ws_stream.split();

    // simple read loop that logs incoming messages
    while let Some(msg_res) = read.next().await {
        match msg_res {
            Ok(msg) => match msg {
                Message::Text(t) => println!("WS text: {}", t),
                Message::Binary(b) => println!("WS binary (len={}): {:02x?}", b.len(), &b[..std::cmp::min(b.len(), 64)]),
                Message::Ping(_) | Message::Pong(_) | Message::Close(_) => println!("WS control frame: {:?}", msg),
                _ => println!("WS other message: {:?}", msg),
            },
            Err(e) => {
                eprintln!("WS read error: {}", e);
                break;
            }
        }
    }

    Ok(())
}

#[pymodule]
fn rust_connector(_py: Python, m: &PyModule) -> PyResult<()> {
    env_logger::init();
    m.add_class::<OrderBook>()?;
    m.add_function(wrap_pyfunction!(parse_orderbook, m)?)?;
    m.add_function(wrap_pyfunction!(compute_triangular_opportunity, m)?)?;
    m.add_function(wrap_pyfunction!(blocking_start_ws, m)?)?;
    Ok(())
}