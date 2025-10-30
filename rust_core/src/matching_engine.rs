pub type Level = (f64,f64);
pub fn simulate_market_order(snapshot: &[(f64,f64)], mut qty: f64) -> (f64, f64, Vec<(f64,f64)>) {
    let mut filled = 0.0; let mut cost = 0.0; let mut fills = Vec::new();
    for (price, size) in snapshot.iter() {
        if qty <= 0.0 { break; }
        let take = if *size >= qty { qty } else { *size };
        filled += take; cost += take * price; fills.push((*price, take)); qty -= take;
    }
    (filled, cost, fills)
}
