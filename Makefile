.PHONY: build test package clean

build:
    cargo build -p rust_python_bindings --release
    cargo build -p aggregator --release
    cargo build -p connector_binance --release || true
    cargo build -p connector_kraken --release || true
    cargo build -p connector_coinbase --release || true
    cargo build -p connector_coingecko --release || true

test:
    cargo test --all

package: build test
    @rm -f rust-hft-arbitrage-lab-mods.zip
    zip -r rust-hft-arbitrage-lab-mods.zip . -x "target/*" -x ".git/*" -x "venv/*" -x "__pycache__/*"
    @echo "Created rust-hft-arbitrage-lab-mods.zip in repo root"

clean:
    cargo clean
    @rm -f rust-hft-arbitrage-lab-mods.zip
