use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde::{Deserialize, Serialize};
use signature_optimal_stopping::{compute_feature_dim, SigParams, SignatureStopper, TrainingSample, Trajectory};
use std::sync::Mutex;
use std::sync::Arc;
use thiserror::Error;

/// Error wrapper for Python
#[derive(Error, Debug)]
enum PySigError {
    #[error("invalid input: {0}")]
    InvalidInput(String),
    #[error("internal: {0}")]
    Internal(String),
}

impl From<PySigError> for PyErr {
    fn from(e: PySigError) -> PyErr {
        PyValueError::new_err(e.to_string())
    }
}

/// Minimal serde-friendly structs for JSON interop
#[derive(Serialize, Deserialize)]
struct PyTrainingSample {
    traj: Vec<Vec<f64>>,
    reward: f64,
}

#[pyclass]
struct PySignatureStopper {
    inner: Arc<Mutex<SignatureStopper>>,
    params: SigParams,
}

#[pymethods]
impl PySignatureStopper {
    /// new(truncation: int = 2, ridge: float = 1e-3, dim_hint: Optional[int] = None)
    /// Create a new Python wrapper. If dim_hint is None, the wrapper will infer feature dimension from first sample at train time.
    #[new]
    fn new(truncation: Option<usize>, ridge: Option<f64>, dim_hint: Option<usize>) -> Self {
        env_logger::init();
        let trunc = truncation.unwrap_or(2);
        let ridge = ridge.unwrap_or(1e-3);
        let params = SigParams { truncation: trunc, ridge };
        let feature_dim = dim_hint.unwrap_or(0);
        let stopper = SignatureStopper::new(params.clone(), feature_dim);
        PySignatureStopper {
            inner: Arc::new(Mutex::new(stopper)),
            params,
        }
    }

    /// train_from_json(json_str: str) -> dict
    /// Expects JSON with structure: { "params": {"truncation": <int>, "ridge": <float>}, "samples": [{"traj": [[...],[...]], "reward": <float>}, ...] }
    /// Returns a dict { "weights": [...], "params": {...} }
    fn train_from_json(&self, json_str: &str) -> PyResult<PyObject> {
        let py = unsafe { Python::assume_gil_acquired() };
        // parse JSON
        let v: serde_json::Value = serde_json::from_str(json_str).map_err(|e| PySigError::InvalidInput(format!("invalid json: {}", e)))?;
        let params = v.get("params").cloned().unwrap_or(serde_json::json!({}));
        let trunc = params.get("truncation").and_then(|t| t.as_u64()).map(|u| u as usize).unwrap_or(self.params.truncation);
        let ridge = params.get("ridge").and_then(|r| r.as_f64()).unwrap_or(self.params.ridge);
        let samples_v = v.get("samples").and_then(|s| s.as_array()).ok_or_else(|| PySigError::InvalidInput("samples must be an array".to_string()))?;

        let mut samples: Vec<TrainingSample> = Vec::with_capacity(samples_v.len());
        for s in samples_v.iter() {
            let traj_v = s.get("traj").and_then(|t| t.as_array()).ok_or_else(|| PySigError::InvalidInput("each sample.traj must be an array".to_string()))?;
            let mut traj: Trajectory = Vec::with_capacity(traj_v.len());
            for point in traj_v.iter() {
                let pt = point.as_array().ok_or_else(|| PySigError::InvalidInput("trajectory points must be arrays of numbers".to_string()))?;
                let mut row: Vec<f64> = Vec::with_capacity(pt.len());
                for val in pt.iter() {
                    let num = val.as_f64().ok_or_else(|| PySigError::InvalidInput("trajectory point contains non-number".to_string()))?;
                    row.push(num);
                }
                traj.push(row);
            }
            let reward = s.get("reward").and_then(|r| r.as_f64()).ok_or_else(|| PySigError::InvalidInput("sample.reward must be a number".to_string()))?;
            samples.push(TrainingSample { traj, reward });
        }

        // infer feature dim if needed
        let d = samples.get(0).and_then(|s| s.traj.get(0)).map(|r| r.len()).ok_or_else(|| PySigError::InvalidInput("no sample/traj provided to infer feature dimension".to_string()))?;
        let feature_dim = compute_feature_dim(d, trunc);

        // create a local stopper and train (or replace inner)
        let mut stopper = SignatureStopper::new(SigParams { truncation: trunc, ridge }, feature_dim);
        stopper.train(&samples).map_err(|e| PySigError::Internal(format!("training failed: {}", e)))?;

        // store weights into inner
        let mut guard = self.inner.lock().map_err(|_| PySigError::Internal("mutex poisoned".to_string()))?;
        *guard = stopper;

        // prepare return dict
        let weights = guard.weights.as_ref().ok_or_else(|| PySigError::Internal("weights missing after training".to_string()))?;
        let py_weights = PyList::new(py, weights.iter().cloned());
        let out = PyDict::new(py);
        out.set_item("weights", py_weights)?;
        out.set_item("params", serde_json::json!({"truncation": trunc, "ridge": ridge}).to_string())?;
        Ok(out.to_object(py))
    }

    /// train(samples_json: str) -> None
    /// Alias to train_from_json but returns None (keeps weights inside object)
    fn train(&self, samples_json: &str) -> PyResult<()> {
        let _ = self.train_from_json(samples_json)?;
        Ok(())
    }

    /// score(traj_json: str) -> float
    /// traj_json: JSON array of arrays representing the trajectory [[x1,...],[x2,...],...]
    fn score(&self, traj_json: &str) -> PyResult<f64> {
        let v: serde_json::Value = serde_json::from_str(traj_json).map_err(|e| PySigError::InvalidInput(format!("invalid traj json: {}", e)))?;
        let traj_v = v.as_array().ok_or_else(|| PySigError::InvalidInput("trajectory must be a JSON array".to_string()))?;
        let mut traj: Trajectory = Vec::with_capacity(traj_v.len());
        for point in traj_v.iter() {
            let pt = point.as_array().ok_or_else(|| PySigError::InvalidInput("trajectory point must be array".to_string()))?;
            let mut row: Vec<f64> = Vec::with_capacity(pt.len());
            for val in pt.iter() {
                let num = val.as_f64().ok_or_else(|| PySigError::InvalidInput("trajectory point contains non-number".to_string()))?;
                row.push(num);
            }
            traj.push(row);
        }
        let guard = self.inner.lock().map_err(|_| PySigError::Internal("mutex poisoned".to_string()))?;
        let sc = guard.score(&traj).map_err(|e| PySigError::Internal(format!("score error: {}", e)))?;
        Ok(sc)
    }

    /// should_stop(traj_json: str, immediate_reward: float, threshold: float = 0.0) -> bool
    fn should_stop(&self, traj_json: &str, immediate_reward: f64, threshold: Option<f64>) -> PyResult<bool> {
        let thr = threshold.unwrap_or(0.0);
        let v: serde_json::Value = serde_json::from_str(traj_json).map_err(|e| PySigError::InvalidInput(format!("invalid traj json: {}", e)))?;
        let traj_v = v.as_array().ok_or_else(|| PySigError::InvalidInput("trajectory must be a JSON array".to_string()))?;
        let mut traj: Trajectory = Vec::with_capacity(traj_v.len());
        for point in traj_v.iter() {
            let pt = point.as_array().ok_or_else(|| PySigError::InvalidInput("trajectory point must be array".to_string()))?;
            let mut row: Vec<f64> = Vec::with_capacity(pt.len());
            for val in pt.iter() {
                let num = val.as_f64().ok_or_else(|| PySigError::InvalidInput("trajectory point contains non-number".to_string()))?;
                row.push(num);
            }
            traj.push(row);
        }
        let guard = self.inner.lock().map_err(|_| PySigError::Internal("mutex poisoned".to_string()))?;
        let res = guard.should_stop(&traj, immediate_reward, thr).map_err(|e| PySigError::Internal(format!("should_stop error: {}", e)))?;
        Ok(res)
    }

    /// get_weights() -> list[float] or None
    fn get_weights(&self) -> PyResult<Option<PyObject>> {
        let py = unsafe { Python::assume_gil_acquired() };
        let guard = self.inner.lock().map_err(|_| PySigError::Internal("mutex poisoned".to_string()))?;
        if let Some(w) = &guard.weights {
            let list = PyList::new(py, w.iter().cloned());
            Ok(Some(list.to_object(py)))
        } else {
            Ok(None)
        }
    }

    /// compute_feature_dim(d: int, trunc: int) -> int (staticmethod)
    #[staticmethod]
    fn compute_feature_dim_py(d: usize, trunc: usize) -> PyResult<usize> {
        Ok(compute_feature_dim(d, trunc))
    }
}

/// Python module
#[pymodule]
fn signature_optimal_stopping_py(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PySignatureStopper>()?;
    Ok(())
}
