use connectors_common::types::MarketTick;
use tokio::sync::{mpsc, broadcast};
use log::info;

pub struct Aggregator {
    tx: broadcast::Sender<MarketTick>,
}

impl Aggregator {
    pub fn new(buffer: usize) -> Self {
        let (tx, _) = broadcast::channel(buffer);
        Aggregator { tx }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<MarketTick> {
        self.tx.subscribe()
    }

    pub fn sender(&self) -> broadcast::Sender<MarketTick> {
        self.tx.clone()
    }

    pub fn create_input_channel(&self, buffer: usize) -> mpsc::Sender<MarketTick> {
        let (tx, mut rx) = mpsc::channel(buffer);
        let tx_b = self.tx.clone();
        tokio::spawn(async move {
            while let Some(tick) = rx.recv().await {
                let _ = tx_b.send(tick);
            }
            info!("aggregator input channel closed");
        });
        tx
    }
}
