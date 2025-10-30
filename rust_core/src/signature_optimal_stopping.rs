/// Simplified signature-like features for a 1D price path:
/// compute iterated integrals via polynomial basis over a window
/// and trigger a stopping rule when score exceeds a threshold.
pub fn stopping_index(path: &[f64], win: usize, th: f64) -> usize {
    if path.is_empty() { return 0; }
    let n = path.len();
    let mut best = n-1;
    for t in win..n {
        let w = &path[t-win..t];
        let x0 = w[0];
        let dx: Vec<f64> = w.iter().map(|v| v - x0).collect();
        // polynomial 'signature' up to degree 3
        let m1: f64 = dx.iter().sum::<f64>() / (win as f64);
        let m2: f64 = dx.iter().map(|d| d*d).sum::<f64>() / (win as f64);
        let m3: f64 = dx.iter().map(|d| d*d*d).sum::<f64>() / (win as f64);
        let score = m1 + 0.5*m2.signum()*m2.sqrt() + 0.1*m3;
        if score > th { return t; }
    }
    best
}
