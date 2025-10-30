pub struct MMQuote { pub bid_px: f64, pub ask_px: f64, pub bid_size: f64, pub ask_size: f64 }
pub fn imbalance_quote(bids: &[(f64,f64)], asks: &[(f64,f64)], spread: f64, skew_coeff: f64) -> MMQuote {
    let bid_vol: f64 = bids.iter().map(|(_,s)| *s).sum();
    let ask_vol: f64 = asks.iter().map(|(_,s)| *s).sum();
    let im = if (bid_vol + ask_vol) == 0.0 { 0.0 } else { (bid_vol - ask_vol)/(bid_vol + ask_vol) };
    let mid = if !bids.is_empty() && !asks.is_empty() { (bids[0].0 + asks[0].0)/2.0 } else { 0.0 };
    let half = spread/2.0; let bid_px = mid - half + im*skew_coeff; let ask_px = mid + half + im*skew_coeff;
    MMQuote { bid_px, ask_px, bid_size: 1.0, ask_size: 1.0 }
}
