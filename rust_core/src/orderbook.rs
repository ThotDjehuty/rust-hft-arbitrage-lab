use serde::{Serialize, Deserialize};
use std::collections::{BTreeMap, VecDeque};

pub type Price = f64;
pub type Qty = f64;
pub type Ts = i64;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Order {
    pub id: u64,
    pub price: Price,
    pub qty: Qty,
    pub ts: Ts,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBookSide {
    // price -> FIFO queue of (order-id, qty, ts)
    pub levels: BTreeMap<Price, VecDeque<Order>>,
    pub is_bid: bool,
}

impl OrderBookSide {
    pub fn new(is_bid: bool) -> Self {
        Self { levels: BTreeMap::new(), is_bid }
    }
    pub fn best_price(&self) -> Option<Price> {
        if self.is_bid {
            self.levels.keys().rev().next().copied()
        } else {
            self.levels.keys().next().copied()
        }
    }
    pub fn total_qty(&self) -> Qty {
        self.levels.values().map(|q| q.iter().map(|o| o.qty).sum::<Qty>()).sum()
    }
    pub fn add_limit(&mut self, id: u64, price: Price, qty: Qty, ts: Ts) {
        let q = self.levels.entry(price).or_insert_with(VecDeque::new);
        q.push_back(Order { id, price, qty, ts });
    }
    pub fn consume_at_price(&mut self, price: Price, mut qty: Qty) -> (Qty, f64, Vec<(u64, Qty, Price)>) {
        // returns (filled_qty, cost, fills)
        let mut filled = 0.0;
        let mut cost = 0.0;
        let mut fills = Vec::new();
        if let Some(queue) = self.levels.get_mut(&price) {
            while qty > 0.0 {
                if let Some(mut o) = queue.front().cloned() {
                    let take = Qty::min(o.qty, qty);
                    filled += take;
                    cost += take * price;
                    fills.push((o.id, take, price));
                    // mutate front
                    let front = queue.front_mut().unwrap();
                    front.qty -= take;
                    qty -= take;
                    if front.qty <= 1e-12 {
                        queue.pop_front();
                    }
                } else { break; }
            }
            if queue.is_empty() { self.levels.remove(&price); }
        }
        (filled, cost, fills)
    }
    pub fn price_iter<'a>(&'a self) -> Box<dyn Iterator<Item=Price> + 'a> {
        if self.is_bid {
            Box::new(self.levels.keys().rev().copied())
        } else {
            Box::new(self.levels.keys().copied())
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBook {
    pub bids: OrderBookSide,
    pub asks: OrderBookSide,
    pub ts: Ts,
    seq: u64,
}

impl OrderBook {
    pub fn new() -> Self {
        Self { bids: OrderBookSide::new(true), asks: OrderBookSide::new(false), ts: 0, seq: 1 }
    }
    pub fn best_bid(&self) -> Option<Price> { self.bids.best_price() }
    pub fn best_ask(&self) -> Option<Price> { self.asks.best_price() }
    pub fn mid(&self) -> Option<Price> {
        match (self.best_bid(), self.best_ask()) {
            (Some(b), Some(a)) => Some((a+b)/2.0),
            _ => None
        }
    }
    pub fn spread(&self) -> Option<f64> {
        match (self.best_bid(), self.best_ask()) {
            (Some(b), Some(a)) => Some(a-b),
            _ => None
        }
    }
    pub fn apply_snapshot(&mut self, bids: &[(Price, Qty)], asks: &[(Price, Qty)], ts: Ts) {
        self.bids.levels.clear(); self.asks.levels.clear();
        for (p,q) in bids { if *q>0.0 { self.bids.add_limit(self.next_id(), *p, *q, ts); } }
        for (p,q) in asks { if *q>0.0 { self.asks.add_limit(self.next_id(), *p, *q, ts); } }
        self.ts = ts;
    }
    pub fn apply_delta(&mut self, bid_d: &[(Price, Qty)], ask_d: &[(Price, Qty)], ts: Ts) {
        for (p, q) in bid_d {
            if *q <= 0.0 { self.bids.levels.remove(p); }
            else { self.bids.add_limit(self.next_id(), *p, *q, ts); }
        }
        for (p, q) in ask_d {
            if *q <= 0.0 { self.asks.levels.remove(p); }
            else { self.asks.add_limit(self.next_id(), *p, *q, ts); }
        }
        self.ts = ts;
    }
    fn next_id(&mut self) -> u64 { let id=self.seq; self.seq+=1; id }
}
