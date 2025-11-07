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
