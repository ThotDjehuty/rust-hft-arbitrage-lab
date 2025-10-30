use futures_util::{SinkExt, StreamExt};
use tokio::time::{sleep, Duration};
use tokio_tungstenite::{connect_async, tungstenite::Message};

pub async fn run_ws(url: &str) -> anyhow::Result<()> {
    let mut backoff = 1u64;
    loop {
        match connect_async(url).await {
            Ok((mut ws, _resp)) => {
                backoff = 1;
                // Optionally send a subscribe message here
                while let Some(msg) = ws.next().await {
                    match msg {
                        Ok(Message::Text(txt)) => {
                            // handle text JSON
                            // eprintln!("MSG: {}", txt);
                            let _ = txt;
                        },
                        Ok(Message::Binary(_b)) => {},
                        Ok(Message::Ping(p)) => ws.send(Message::Pong(p)).await?,
                        Ok(Message::Close(_)) => break,
                        Err(e) => { eprintln!("ws err: {}", e); break; }
                    }
                }
            }
            Err(e) => {
                eprintln!("connect error: {}", e);
            }
        }
        sleep(Duration::from_secs(backoff.min(30))).await;
        backoff *= 2;
    }
}
