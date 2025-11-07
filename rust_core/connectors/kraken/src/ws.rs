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
