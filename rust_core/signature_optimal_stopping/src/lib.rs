//! signature_optimal_stopping
//!
//! Self-contained implementation (truncated signature up to level 3 + simple ridge regression)
//! to approximate a continuation function and produce an optimal stopping rule based on signatures.
//!
//! This implementation follows the algorithmic idea of using truncated signatures as features and
//! fitting a regression to estimate continuation values. It is intentionally compact and suitable
//! for testing and integration. For production, replace signature computation with a specialized
//! optimized library.

use ndarray::{Array1, Array2, Axis};
use ndarray_linalg::solve::Inverse;
use serde::{Deserialize, Serialize};
use std::error::Error;
use std::fmt;
use chrono::Utc;
use log::info;

/// Parameters and types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SigParams {
    pub truncation: usize, // truncation level (1..3 supported)
    pub ridge: f64,        // ridge regularization
}

impl Default for SigParams {
    fn default() -> Self {
        SigParams {
            truncation: 3,
            ridge: 1e-3,
        }
    }
}

#[derive(Debug)]
pub enum SigError {
    BadInput(String),
    LinAlg(String),
}

impl fmt::Display for SigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SigError::BadInput(s) => write!(f, "Bad input: {}", s),
            SigError::LinAlg(s) => write!(f, "Linear algebra error: {}", s),
        }
    }
}

impl Error for SigError {}

/// A trajectory: a vector of d-dimensional observations (time-ordered)
pub type Trajectory = Vec<Vec<f64>>;

/// Compute truncated signature up to level 3 on a discrete trajectory using simple iterated sums.
/// Supports multidimensional trajectories.
/// Returns a flat feature vector [level1..., level2..., level3...].
pub fn compute_truncated_signature(traj: &Trajectory, trunc: usize) -> Result<Vec<f64>, SigError> {
    if trunc < 1 || trunc > 3 {
        return Err(SigError::BadInput("trunc must be 1..3".to_string()));
    }
    if traj.is_empty() {
        return Err(SigError::BadInput("empty trajectory".to_string()));
    }
    let d = traj[0].len();
    // level 1: increments sum
    let mut feat: Vec<f64> = Vec::new();

    // compute increments
    let mut increments: Vec<Vec<f64>> = Vec::new();
    for i in 1..traj.len() {
        let mut inc = vec![0.0; d];
        for k in 0..d {
            inc[k] = traj[i][k] - traj[i - 1][k];
        }
        increments.push(inc);
    }

    // level 1: sums of increments per dimension
    if trunc >= 1 {
        for k in 0..d {
            let mut s = 0.0;
            for inc in &increments {
                s += inc[k];
            }
            feat.push(s);
        }
    }

    // level 2: pairwise iterated integrals approx: sum_{a<b} inc_a \otimes inc_b
    if trunc >= 2 {
        for i in 0..d {
            for j in 0..d {
                let mut s = 0.0;
                for a in 0..increments.len() {
                    for b in (a + 1)..increments.len() {
                        s += increments[a][i] * increments[b][j];
                    }
                }
                feat.push(s);
            }
        }
    }

    // level 3: triple iterated integrals approx: sum_{a<b<c} inc_a[i] * inc_b[j] * inc_c[k]
    if trunc >= 3 {
        for i in 0..d {
            for j in 0..d {
                for k in 0..d {
                    let mut s = 0.0;
                    for a in 0..increments.len() {
                        for b in (a + 1)..increments.len() {
                            for c in (b + 1)..increments.len() {
                                s += increments[a][i] * increments[b][j] * increments[c][k];
                            }
                        }
                    }
                    feat.push(s);
                }
            }
        }
    }

    Ok(feat)
}

/// Fit a ridge regression: solves (X^T X + lambda I) w = X^T y.
/// X: (n_samples x n_features), y: (n_samples)
pub fn fit_ridge(X: &Array2<f64>, y: &Array1<f64>, lambda: f64) -> Result<Array1<f64>, SigError> {
    let (n, p) = (X.nrows(), X.ncols());
    if y.len() != n {
        return Err(SigError::BadInput("X/y size mismatch".to_string()));
    }
    // compute XtX
    let xt = X.t();
    let xtx = xt.dot(X);
    // add ridge
    let mut ridge_mat = xtx.clone();
    for i in 0..p {
        ridge_mat[[i, i]] += lambda;
    }
    // compute rhs = X^T y
    let rhs = xt.dot(y);
    // solve via inverse (for simplicity)
    match ridge_mat.inv() {
        Ok(inv) => {
            let w = inv.dot(&rhs);
            Ok(w)
        }
        Err(e) => Err(SigError::LinAlg(format!("inv failed: {:?}", e))),
    }
}

/// Score a feature vector with weights
pub fn score_feature_vec(w: &Array1<f64>, x: &Array1<f64>) -> f64 {
    w.dot(x)
}

/// Dataset type for training: each sample is (trajectory, label)
#[derive(Clone, Serialize, Deserialize)]
pub struct TrainingSample {
    pub traj: Trajectory,
    pub reward: f64, // observed reward if stopped at that time (target)
}

/// Trainer object: holds params and trained weights
pub struct SignatureStopper {
    pub params: SigParams,
    pub weights: Option<Array1<f64>>,
    pub feature_dim: usize,
}

impl SignatureStopper {
    pub fn new(params: SigParams, feature_dim: usize) -> Self {
        SignatureStopper {
            params,
            weights: None,
            feature_dim,
        }
    }

    /// Build design matrix from training samples.
    pub fn build_design_matrix(&self, samples: &[TrainingSample]) -> Result<(Array2<f64>, Array1<f64>), SigError> {
        let n = samples.len();
        if n == 0 {
            return Err(SigError::BadInput("no training samples".to_string()));
        }
        let p = self.feature_dim;
        let mut x = Array2::<f64>::zeros((n, p));
        let mut y = Array1::<f64>::zeros(n);
        for (i, s) in samples.iter().enumerate() {
            let feat = compute_truncated_signature(&s.traj, self.params.truncation)?;
            if feat.len() != p {
                return Err(SigError::BadInput(format!("feature dim mismatch: got {}, expected {}", feat.len(), p)));
            }
            for j in 0..p {
                x[[i, j]] = feat[j];
            }
            y[i] = s.reward;
        }
        Ok((x, y))
    }

    /// Train using ridge regression on samples.
    pub fn train(&mut self, samples: &[TrainingSample]) -> Result<(), SigError> {
        let (x, y) = self.build_design_matrix(samples)?;
        let w = fit_ridge(&x, &y, self.params.ridge)?;
        self.weights = Some(w);
        info!("Trained weights (len={}): trained at {}", self.weights.as_ref().unwrap().len(), Utc::now());
        Ok(())
    }

    /// Given a trajectory, compute score (continuation value). If weights not present, return error.
    pub fn score(&self, traj: &Trajectory) -> Result<f64, SigError> {
        let feat = compute_truncated_signature(traj, self.params.truncation)?;
        let p = feat.len();
        if Some(p) != self.weights.as_ref().map(|w| w.len()) {
            return Err(SigError::BadInput("model not trained or feature dim mismatch".to_string()));
        }
        let x = Array1::from(feat);
        let w = self.weights.as_ref().ok_or_else(|| SigError::BadInput("weights missing".to_string()))?;
        Ok(score_feature_vec(w, &x))
    }

    /// Decision rule: stop if immediate reward >= continuation_score (or thresholded)
    pub fn should_stop(&self, traj: &Trajectory, immediate_reward: f64, threshold: f64) -> Result<bool, SigError> {
        let cont = self.score(traj)?;
        Ok(immediate_reward >= cont - threshold)
    }
}

// Convenience: compute feature dimension given d and truncation
pub fn compute_feature_dim(d: usize, trunc: usize) -> usize {
    let mut dim = 0;
    if trunc >= 1 {
        dim += d;
    }
    if trunc >= 2 {
        dim += d * d;
    }
    if trunc >= 3 {
        dim += d * d * d;
    }
    dim
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_trunc_signature_dim() {
        let d = 2;
        let trunc = 3;
        let dim = compute_feature_dim(d, trunc);
        assert_eq!(dim, 2 + 4 + 8);
    }

    #[test]
    fn test_feature_and_train() {
        // synthetic dataset: 1D deterministic increasing sequences with reward equal to last value
        let params = SigParams { truncation: 2, ridge: 1e-3 };
        let feature_dim = compute_feature_dim(1, params.truncation);
        let mut stopper = SignatureStopper::new(params, feature_dim);

        let mut samples: Vec<TrainingSample> = Vec::new();
        for _ in 0..50 {
            let mut traj: Trajectory = Vec::new();
            let mut x = 0.0;
            traj.push(vec![x]);
            for _ in 0..5 {
                x += 1.0; // deterministic increasing
                traj.push(vec![x]);
            }
            samples.push(TrainingSample { traj, reward: x });
        }

        let res = stopper.train(&samples);
        assert!(res.is_ok());
        let test_traj = samples[0].traj.clone();
        let s = stopper.score(&test_traj).unwrap();
        assert!(s.is_finite());
    }
}
