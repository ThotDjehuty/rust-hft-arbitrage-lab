# Single-stage dev image that builds the rust extension in-container and runs Streamlit.
# For production, consider a multi-stage build that copies only the runtime artifacts.

FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV RUSTUP_HOME=/rustup CARGO_HOME=/usr/local/cargo PATH=/usr/local/cargo/bin:$PATH

# Install system build dependencies required for Rust crates and Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    ca-certificates \
    pkg-config \
    libssl-dev \
    clang \
    cmake \
    python3-dev \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the project into the container
COPY . /app

# Upgrade pip and install Python packages (maturin included)
# IMPORTANT: do not include Rust crates (pyo3) in python requirements -- maturin will build the Rust crate.
RUN python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install --no-cache-dir -r docker/requirements.txt

# Install Rust toolchain non-interactively and maturin is already installed via pip
# rustup bootstrap; installs toolchain (stable)
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y \
 && rustup toolchain install stable \
 && rustup default stable

# Build and install the Rust-Python extension into the container's Python environment.
# Use --manifest-path to avoid workspace detection issues.
RUN python -m maturin develop --release --manifest-path rust_connector/Cargo.toml

# Expose Streamlit port and run the app
EXPOSE 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]