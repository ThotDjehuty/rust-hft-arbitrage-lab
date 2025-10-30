use serde::{Serialize,Deserialize};
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PathPoint { pub t: f64, pub x: f64 }
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignatureFeatures { pub t: f64, pub x: f64, pub x2: f64 }
pub fn lift_to_signature(path: &[PathPoint]) -> Vec<SignatureFeatures> {
    path.iter().map(|p| SignatureFeatures { t: p.t, x: p.x, x2: p.x * p.x }).collect()
}
pub fn signature_optimal_stop(path: &[PathPoint], quantile: f64) -> Option<PathPoint> {
    if path.is_empty() { return None; }
    let mut xs: Vec<f64> = path.iter().map(|p| p.x).collect();
    xs.sort_by(|a,b| a.partial_cmp(b).unwrap());
    let idx = ((xs.len() as f64)*quantile).floor() as usize;
    let idx = idx.min(xs.len()-1);
    let thr = xs[idx];
    for p in path { if p.x >= thr { return Some(p.clone()); } }
    None
}
