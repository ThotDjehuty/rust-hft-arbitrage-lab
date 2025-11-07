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
