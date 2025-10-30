use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

#[pyfunction]
fn hello() -> PyResult<String> { Ok("hft_py ready".to_string()) }

#[pyfunction]
fn simulate_market_order_py(snapshot: Vec<(f64,f64)>, qty: f64) -> PyResult<(f64,f64, Vec<(f64,f64)>)> {
    let (filled, cost, fills) = rust_core::matching_engine::simulate_market_order(&snapshot, qty);
    Ok((filled, cost, fills))
}

#[pyfunction]
fn signature_opt_stop_py(xs: Vec<(f64,f64)>, quantile: f64) -> PyResult<Option<(f64,f64)>> {
    let path: Vec<rust_core::signature_optimal_stopping::PathPoint> = xs.into_iter()
        .map(|(t,x)| rust_core::signature_optimal_stopping::PathPoint{t,x}).collect();
    let res = rust_core::signature_optimal_stopping::signature_optimal_stop(&path, quantile);
    Ok(res.map(|p| (p.t, p.x)))
}

#[pymodule]
fn hft_py(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hello, m)?)?;
    m.add_function(wrap_pyfunction!(simulate_market_order_py, m)?)?;
    m.add_function(wrap_pyfunction!(signature_opt_stop_py, m)?)?;
    Ok(())
}
