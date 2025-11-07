#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
echo "Running from: $ROOT"

write_file() {
  local path="$1"; shift
  local content="$@"
  mkdir -p "$(dirname "$path")"
  if [ -f "$path" ]; then
    cp "$path" "${path}.bak"
    echo "Backed up existing $path -> ${path}.bak"
  fi
  cat > "$path" <<'EOF'
'"$content"'
EOF
  echo "Wrote $path"
}

# workspace root Cargo.toml
write_file "${ROOT}/Cargo.toml" '
[workspace]
members = [
  "rust_core/connectors/common",
  "rust_core/connectors/binance",
  "rust_core/connectors/kraken",
  "rust_core/connectors/coinbase",
  "rust_core/connectors/coingecko",
  "rust_core/aggregator",
  "rust_core/signature_optimal_stopping",
  "rust_core/signature_optimal_stopping_py",
  "rust_python_bindings"
]
'

# connectors/common
write_file "${ROOT}/rust_core/connectors/common/Cargo.toml" '
[package]
name = "connectors_common"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
chrono = { version = "0.4", features = ["serde"] }
thiserror = "1.0"
'

# connectors/binance
write_file "${ROOT}/rust_core/connectors/binance/Cargo.toml" '
[package]
name = "connector_binance"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.36", features = ["full"] }
tokio-tungstenite = "0.20"
tungstenite = "0.20"
futures = "0.3"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
reqwest = { version = "0.11", features = ["json", "rustls-tls"] }
connectors_common = { path = "../common" }
log = "0.4"
env_logger = "0.10"
chrono = { version = "0.4", features = ["serde"] }
'

# connectors/kraken
write_file "${ROOT}/rust_core/connectors/kraken/Cargo.toml" '
[package]
name = "connector_kraken"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.36", features = ["full"] }
tokio-tungstenite = "0.20"
tungstenite = "0.20"
futures = "0.3"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
reqwest = { version = "0.11", features = ["json", "rustls-tls"] }
connectors_common = { path = "../common" }
log = "0.4"
env_logger = "0.10"
chrono = { version = "0.4", features = ["serde"] }
'

# connectors/coinbase
write_file "${ROOT}/rust_core/connectors/coinbase/Cargo.toml" '
[package]
name = "connector_coinbase"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.36", features = ["full"] }
tokio-tungstenite = "0.20"
tungstenite = "0.20"
futures = "0.3"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
reqwest = { version = "0.11", features = ["json", "rustls-tls"] }
connectors_common = { path = "../common" }
log = "0.4"
env_logger = "0.10"
chrono = { version = "0.4", features = ["serde"] }
'

# connectors/coingecko
write_file "${ROOT}/rust_core/connectors/coingecko/Cargo.toml" '
[package]
name = "connector_coingecko"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.36", features = ["full"] }
reqwest = { version = "0.11", features = ["json", "rustls-tls"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
connectors_common = { path = "../common" }
log = "0.4"
env_logger = "0.10"
chrono = { version = "0.4", features = ["serde"] }
'

# aggregator
write_file "${ROOT}/rust_core/aggregator/Cargo.toml" '
[package]
name = "aggregator"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.36", features = ["full"] }
connectors_common = { path = "../connectors/common" }
log = "0.4"
env_logger = "0.10"
serde = { version = "1.0", features = ["derive"] }
'

# signature_optimal_stopping
write_file "${ROOT}/rust_core/signature_optimal_stopping/Cargo.toml" '
[package]
name = "signature_optimal_stopping"
version = "0.1.0"
edition = "2021"

[lib]
name = "signature_optimal_stopping"
path = "src/lib.rs"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
ndarray = "0.15"
# optional: remove ndarray-linalg if you do not want system BLAS; adjust if needed
ndarray-linalg = { version = "0.16", features = ["openblas-static"] }
chrono = { version = "0.4", features = ["serde"] }
log = "0.4"
'

# signature_optimal_stopping_py
write_file "${ROOT}/rust_core/signature_optimal_stopping_py/Cargo.toml" '
[package]
name = "signature_optimal_stopping_py"
version = "0.1.0"
edition = "2021"

[lib]
name = "signature_optimal_stopping_py"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.18", features = ["extension-module", "auto-initialize"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
thiserror = "1.0"
signature_optimal_stopping = { path = "../signature_optimal_stopping" }
log = "0.4"
env_logger = "0.10"
'

# rust_python_bindings
write_file "${ROOT}/rust_python_bindings/Cargo.toml" '
[package]
name = "rust_python_bindings"
version = "0.1.0"
edition = "2021"

[lib]
name = "hft_py"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.18", features = ["extension-module", "auto-initialize"] }
pyo3-asyncio = { version = "0.18", features = ["tokio-runtime"] }
tokio = { version = "1.36", features = ["rt-multi-thread", "macros", "time"] }
connectors_common = { path = "rust_core/connectors/common" }
aggregator = { path = "rust_core/aggregator" }
connector_binance = { path = "rust_core/connectors/binance" }
connector_kraken = { path = "rust_core/connectors/kraken" }
connector_coinbase = { path = "rust_core/connectors/coinbase" }
connector_coingecko = { path = "rust_core/connectors/coingecko" }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
log = "0.4"
env_logger = "0.10"
chrono = { version = "0.4", features = ["serde"] }
'

echo "All Cargo.toml files written. Run 'cargo update' then 'cargo build --workspace'."

