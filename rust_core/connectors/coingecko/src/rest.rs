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
