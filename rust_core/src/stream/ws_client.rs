use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use tokio::time::{sleep, Duration};
use futures_util::{StreamExt, SinkExt};
use url::Url;
use anyhow::Result;
pub async fn run_ws(url: &str, mut on_msg: impl FnMut(String) + Send + 'static) -> Result<()> {
    let mut backoff = 1;
    loop {
        let u = Url::parse(url)?;
        match connect_async(u).await {
            Ok((ws, _)) => {
                let (mut write, mut read) = ws.split();
                while let Some(msg) = read.next().await {
                    match msg {
                        Ok(Message::Text(s)) => on_msg(s),
                        Ok(Message::Ping(_)) => { write.send(Message::Pong(vec![])).await.ok(); }
                        Ok(Message::Close(_)) => { break; }
                        _ => {}
                    }
                }
            }
            Err(_) => {}
        }
        let wait = backoff.min(60);
        sleep(Duration::from_secs(wait)).await;
        backoff *= 2;
    }
}
