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
