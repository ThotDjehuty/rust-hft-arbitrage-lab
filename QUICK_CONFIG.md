# Quick Setup Guide

## API Keys Configuration

All API keys are managed through the `api_keys.properties` file in the project root.

### Setup Steps

1. **Copy the example file:**
   ```bash
   cp api_keys.properties.example api_keys.properties
   ```

2. **Edit `api_keys.properties` and fill in your credentials:**
   ```properties
   # Finnhub (free tier - get key at https://finnhub.io/register)
   FINNHUB_API_KEY=your_actual_finnhub_key_here
   
   # Binance (optional - only if using authenticated trading)
   BINANCE_API_KEY=your_binance_key_here
   BINANCE_API_SECRET=your_binance_secret_here
   
   # Coinbase (optional - only if using authenticated trading)
   COINBASE_API_KEY=your_coinbase_key_here
   COINBASE_API_SECRET=your_coinbase_secret_here
   COINBASE_PASSPHRASE=your_coinbase_passphrase_here
   ```

3. **That's it!** All connectors, notebooks, and apps will automatically load credentials from this file.

### Security Notes

- `api_keys.properties` is git-ignored (never committed)
- Only `api_keys.properties.example` (template) is tracked in git
- The file is mounted read-only in Docker containers

## Running the Project

### Local Development

```bash
# Install dependencies
pip install -r docker/requirements.txt

# Build Rust extension
maturin develop --manifest-path rust_connector/Cargo.toml

# Run Streamlit
streamlit run app/streamlit_strategies.py

# Or Jupyter
jupyter notebook
```

### Docker

```bash
# Start Streamlit
docker-compose up lab

# Start Jupyter
docker-compose up jupyter

# Start both
docker-compose up
```

## Usage

- **Without API keys**: Uses synthetic data (works fine for testing strategies)
- **With Finnhub key**: Fetches real market data
- **With exchange keys**: Enables authenticated trading (use with caution!)

All credentials are automatically loaded from `api_keys.properties` - no environment variables needed!
