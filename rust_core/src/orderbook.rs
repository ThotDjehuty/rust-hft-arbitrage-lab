use serde::{Serialize,Deserialize};
pub type Level = (f64,f64);
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBook { pub bids: Vec<Level>, pub asks: Vec<Level>, pub ts: i64 }
impl OrderBook {
    pub fn new() -> Self { OrderBook { bids: vec![], asks: vec![], ts: 0 } }
    pub fn mid(&self) -> Option<f64> {
        if !self.bids.is_empty() && !self.asks.is_empty() { Some((self.bids[0].0 + self.asks[0].0)/2.0) } else { None }
    }
    pub fn with_snapshot(&self, bids: Vec<Level>, asks: Vec<Level>, ts: i64) -> Self { OrderBook { bids, asks, ts } }
    pub fn apply_delta(&self, bids_delta: &[(f64,f64)], asks_delta: &[(f64,f64)], ts: i64) -> Self {
        use std::collections::BTreeMap;
        let mut bids_map: BTreeMap<f64,f64> = self.bids.iter().map(|(p,s)| (*p,*s)).collect();
        let mut asks_map: BTreeMap<f64,f64> = self.asks.iter().map(|(p,s)| (*p,*s)).collect();
        for (p,s) in bids_delta { if *s <= 0.0 { bids_map.remove(p); } else { bids_map.insert(*p,*s); } }
        for (p,s) in asks_delta { if *s <= 0.0 { asks_map.remove(p); } else { asks_map.insert(*p,*s); } }
        let mut bids: Vec<Level> = bids_map.into_iter().collect(); bids.sort_by(|a,b| b.0.partial_cmp(&a.0).unwrap());
        let mut asks: Vec<Level> = asks_map.into_iter().collect(); asks.sort_by(|a,b| a.0.partial_cmp(&b.0).unwrap());
        OrderBook { bids, asks, ts }
    }
}
