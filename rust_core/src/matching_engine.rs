use crate::orderbook::{OrderBook, Price, Qty};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Side { Buy, Sell }

#[derive(Debug, Clone)]
pub struct Fill {
    pub price: Price,
    pub qty: Qty,
    pub cost: f64,
}

pub fn execute_market(book: &mut OrderBook, side: Side, mut qty: Qty) -> (Qty, f64, Vec<Fill>) {
    let mut filled=0.0; let mut cost=0.0; let mut fills=Vec::new();
    match side {
        Side::Buy => {
            let mut it: Vec<Price> = book.asks.price_iter().collect();
            for p in it {
                if qty<=0.0 { break; }
                let (f, c, parts) = book.asks.consume_at_price(p, qty);
                for (_id, q, pr) in parts { fills.push(Fill{price:pr, qty:q, cost:q*pr}); }
                filled += f; cost += c; qty -= f;
            }
        }
        Side::Sell => {
            let mut it: Vec<Price> = book.bids.price_iter().collect();
            for p in it {
                if qty<=0.0 { break; }
                let (f, c, parts) = book.bids.consume_at_price(p, qty);
                for (_id, q, pr) in parts { fills.push(Fill{price:pr, qty:q, cost:q*pr}); }
                filled += f; cost += c; qty -= f;
            }
        }
    }
    (filled, cost, fills)
}

pub fn place_limit(book: &mut OrderBook, side: Side, price: Price, qty: Qty, ts: i64) {
    match side {
        Side::Buy => book.bids.add_limit(0, price, qty, ts),
        Side::Sell => book.asks.add_limit(0, price, qty, ts),
    }
}
