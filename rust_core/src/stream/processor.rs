/// Triangular arbitrage helper:
/// Given BTC/USDT = P1, ETH/USDT = P2, BTC/ETH = P3, fee rate f per trade,
/// cycle factor = P1 / (P2 * P3)
/// net edge = cycle * (1-f)^3 - 1
pub fn tri_edge(p_btc_usdt: f64, p_eth_usdt: f64, p_btc_eth: f64, fee: f64) -> f64 {
    let cycle = p_btc_usdt / (p_eth_usdt * p_btc_eth + 1e-12);
    cycle * (1.0 - fee).powi(3) - 1.0
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_edge() {
        let e = tri_edge(68000.0, 3700.0, 68000.0/3700.0, 0.0004);
        assert!(e.abs() < 1e-6);
    }
}
