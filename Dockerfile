# Unified Dockerfile for HFT Arbitrage Lab
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    RUSTUP_HOME=/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git ca-certificates pkg-config \
    libssl-dev clang cmake python3-dev \
    libopenblas-dev liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY docker/requirements.txt /app/docker/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r docker/requirements.txt

# Install Rust toolchain
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y && \
    rustup default stable

# Copy project files
COPY . /app

# Build Rust extensions
RUN maturin build --release --manifest-path rust_connector/Cargo.toml && \
    pip install --no-cache-dir target/wheels/rust_connector-*.whl

EXPOSE 8501 8888

# Default: Streamlit
CMD ["streamlit", "run", "app/streamlit_strategies.py", "--server.address=0.0.0.0"]
