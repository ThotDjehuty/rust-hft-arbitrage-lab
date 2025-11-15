# python/finnhub_helper.py
"""
Helper functions for fetching real market data from Finnhub in notebooks and apps.
"""

import time
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Try to import the Finnhub connector
try:
    from python.rust_bridge import get_connector
    FINNHUB_AVAILABLE = True
except ImportError:
    FINNHUB_AVAILABLE = False
    logger.warning("Could not import Finnhub connector")

# Try to import API keys utility
try:
    from python.api_keys import get_finnhub_key
    API_KEYS_AVAILABLE = True
except ImportError:
    API_KEYS_AVAILABLE = False
    logger.warning("Could not import api_keys module")


def get_finnhub_api_key() -> Optional[str]:
    """Get Finnhub API key from api_keys.properties file."""
    if API_KEYS_AVAILABLE:
        return get_finnhub_key()
    return None


def fetch_realtime_quotes(symbols: List[str], api_key: Optional[str] = None, duration_seconds: int = 30) -> pd.DataFrame:
    """
    Fetch real-time quotes from Finnhub for the given symbols.
    
    Args:
        symbols: List of symbols (e.g., ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT"])
        api_key: Finnhub API key (if None, tries to get from environment)
        duration_seconds: How long to collect data
    
    Returns:
        DataFrame with columns: timestamp, symbol, bid, ask, mid
    """
    if api_key is None:
        api_key = get_finnhub_api_key()
    
    if not api_key or not FINNHUB_AVAILABLE:
        logger.warning("Generating synthetic data instead of real Finnhub data")
        return generate_synthetic_data(symbols, duration_seconds)
    
    try:
        from python.connectors.finnhub import FinnhubConnector
        
        data_points = []
        connector = FinnhubConnector(api_key)
        
        for symbol in symbols:
            # Fetch current quote
            try:
                ob = connector.fetch_orderbook_sync(symbol)
                if ob['bids'] and ob['asks']:
                    bid = ob['bids'][0][0]
                    ask = ob['asks'][0][0]
                    mid = (bid + ask) / 2
                    
                    data_points.append({
                        'timestamp': pd.Timestamp.now(),
                        'symbol': symbol,
                        'bid': bid,
                        'ask': ask,
                        'mid': mid
                    })
                
                # Respect rate limits (60/min on free tier = 1 per second)
                time.sleep(1.1)
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
        
        if not data_points:
            logger.warning("No data fetched, using synthetic fallback")
            return generate_synthetic_data(symbols, duration_seconds)
        
        return pd.DataFrame(data_points)
    
    except Exception as e:
        logger.error(f"Finnhub data fetch failed: {e}")
        return generate_synthetic_data(symbols, duration_seconds)


def fetch_historical_simulation(symbols: List[str], periods: int = 1000, api_key: Optional[str] = None) -> pd.DataFrame:
    """
    Simulate historical data by fetching current quotes and generating synthetic history.
    For true historical data, Finnhub requires a premium subscription.
    
    Args:
        symbols: List of symbols
        periods: Number of historical periods to generate
        api_key: Finnhub API key
    
    Returns:
        DataFrame with columns: timestamp, symbol_mid columns
    """
    if api_key is None:
        api_key = get_finnhub_api_key()
    
    # Fetch current prices as starting points
    current_data = fetch_realtime_quotes(symbols, api_key, duration_seconds=5)
    
    if current_data.empty:
        logger.warning("Could not fetch current prices, using default starting values")
        starting_prices = {sym: 100.0 * (i + 1) for i, sym in enumerate(symbols)}
    else:
        starting_prices = dict(zip(current_data['symbol'], current_data['mid']))
    
    # Generate synthetic historical data based on current prices
    timestamps = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq='5min')
    data = {'timestamp': timestamps}
    
    for symbol in symbols:
        start_price = starting_prices.get(symbol, 100.0)
        # Generate random walk with mean reversion
        returns = np.random.randn(periods) * 0.01
        prices = start_price * (1 + returns).cumprod()
        
        # Ensure realistic price evolution
        prices = np.maximum(prices, start_price * 0.5)  # Don't drop below 50%
        prices = np.minimum(prices, start_price * 2.0)  # Don't rise above 200%
        
        data[f"{symbol}_mid"] = prices
    
    return pd.DataFrame(data)


def generate_synthetic_data(symbols: List[str], duration_seconds: int = 30) -> pd.DataFrame:
    """
    Generate synthetic market data when Finnhub is not available.
    
    Args:
        symbols: List of symbols
        duration_seconds: Duration to simulate
    
    Returns:
        DataFrame with realistic synthetic quotes
    """
    num_points = max(10, duration_seconds // 2)
    timestamps = pd.date_range(end=pd.Timestamp.now(), periods=num_points, freq='2s')
    
    data_points = []
    base_prices = {
        'BINANCE:BTCUSDT': 50000.0,
        'BINANCE:ETHUSDT': 3000.0,
        'BINANCE:BNBUSDT': 300.0,
        'COINBASE:BTC-USD': 50000.0,
        'COINBASE:ETH-USD': 3000.0,
        'AAPL': 180.0,
        'GOOGL': 140.0,
        'MSFT': 380.0,
    }
    
    for ts in timestamps:
        for symbol in symbols:
            base_price = base_prices.get(symbol, 100.0)
            # Add random walk
            mid = base_price * (1 + np.random.randn() * 0.001)
            spread = mid * 0.0001  # 1 bps spread
            
            data_points.append({
                'timestamp': ts,
                'symbol': symbol,
                'bid': mid - spread / 2,
                'ask': mid + spread / 2,
                'mid': mid
            })
    
    return pd.DataFrame(data_points)


def format_symbol_for_finnhub(symbol: str, exchange: str = "BINANCE") -> str:
    """
    Format a symbol for Finnhub API.
    
    Args:
        symbol: Symbol like "BTCUSDT" or "BTC/USD"
        exchange: Exchange name (BINANCE, COINBASE, etc.)
    
    Returns:
        Formatted symbol like "BINANCE:BTCUSDT"
    """
    # Remove slashes and dashes
    clean_symbol = symbol.replace('/', '').replace('-', '')
    
    # If already has exchange prefix, return as-is
    if ':' in clean_symbol:
        return clean_symbol
    
    return f"{exchange}:{clean_symbol}"


def create_orderbook_from_quote(bid: float, ask: float, size: float = 1.0) -> Dict:
    """
    Create an orderbook dict from bid/ask prices.
    
    Args:
        bid: Bid price
        ask: Ask price
        size: Size at each level
    
    Returns:
        Orderbook dict compatible with strategy code
    """
    return {
        'bids': [[bid, size]],
        'asks': [[ask, size]]
    }
