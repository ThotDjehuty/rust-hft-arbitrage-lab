pub fn zscore_series(x: &[f64], window: usize) -> Vec<f64> {
    if x.len() < window { return Vec::new(); }
    let mut out = Vec::new();
    for i in 0..=x.len()-window {
        let w = &x[i..i+window];
        let mean = w.iter().sum::<f64>() / (window as f64);
        let var = w.iter().map(|v| (v-mean)*(v-mean)).sum::<f64>()/(window as f64);
        let std = var.sqrt().max(1e-9);
        out.push((x[i+window-1] - mean)/std);
    }
    out
}
