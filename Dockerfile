FROM python:3.11-slim

# Install build deps for maturin / Rust if you plan to build rust extension inside container
RUN apt-get update && apt-get install -y build-essential curl pkg-config libssl-dev
# Install rustup & cargo for building rust extensions
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
# Optionally: build the rust module here with maturin develop/build
# RUN maturin develop --release
EXPOSE 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]