# Wrapper Python simple qui importe le module Rust (après build via maturin or maturin develop)
# Usage: from rust_bridge import parse_orderbook, compute_triangular_opportunity, start_ws
try:
    import rust_connector  # built from the rust module
except Exception as e:
    rust_connector = None
    _err = e

def parse_orderbook(json_str):
    if rust_connector is None:
        raise RuntimeError(f"rust_connector not available: {_err}")
    return rust_connector.parse_orderbook(json_str)

def compute_triangular_opportunity(ob1, ob2, ob3):
    if rust_connector is None:
        raise RuntimeError(f"rust_connector not available: {_err}")
    return rust_connector.compute_triangular_opportunity(ob1, ob2, ob3)

def start_ws(url):
    if rust_connector is None:
        raise RuntimeError(f"rust_connector not available: {_err}")
    return rust_connector.blocking_start_ws(url)