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
