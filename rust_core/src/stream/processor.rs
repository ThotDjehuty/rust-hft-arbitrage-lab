use tokio::sync::mpsc::{Sender, Receiver, channel};
use crate::orderbook::OrderBook;
use serde_json::Value;
pub type Event = Value;
pub fn spawn_processor() -> (Sender<Event>, Receiver<OrderBook>) {
    let (in_tx, mut in_rx) = channel::<Event>(1024);
    let (out_tx, out_rx) = channel::<OrderBook>(64);
    tokio::spawn(async move {
        let mut state = OrderBook::new();
        while let Some(ev) = in_rx.recv().await {
            if ev.get("type") == Some(&Value::String("snapshot".into())) {
                state = state.with_snapshot(vec![], vec![], ev["ts"].as_i64().unwrap_or(0));
            } else {
                state = state.apply_delta(&[], &[], ev["ts"].as_i64().unwrap_or(0));
            }
            let _ = out_tx.send(state.clone()).await;
        }
    });
    (in_tx, out_rx)
}
