# python/connectors/finnhub.py
"""
Finnhub connector for real-time market data via WebSocket.
Supports trades, quotes, and level 1 orderbook data.
"""

import json
import logging
import threading
from typing import Optional, Callable
import websocket
import time
import requests

logger = logging.getLogger(__name__)


class FinnhubConnector:
    """
    Finnhub connector using WebSocket API for real-time market data.
    
    Note: Finnhub provides trades and quotes, not full orderbook depth.
    For orderbook simulation, we maintain a synthetic book from quote updates.
    
    Free tier limits: 60 API calls/minute
    """
    
    def __init__(self, api_key: Optional[str] = None):
        # Auto-load API key from api_keys.properties if not provided
        if api_key is None:
            try:
                from python.api_keys import get_api_key
                api_key = get_api_key("FINNHUB_API_KEY")
            except ImportError:
                pass
        
        if not api_key:
            raise ValueError(
                "Finnhub API key not found. Please:\n"
                "1. Copy api_keys.properties.example to api_keys.properties\n"
                "2. Fill in FINNHUB_API_KEY\n"
                "Or provide the key explicitly to the constructor."
            )
        
        self.api_key = api_key
        self.name = "finnhub"
        self.ws_url = f"wss://ws.finnhub.io?token={api_key}"
        
        self.ws = None
        self.ws_thread = None
        self.running = False
        self.callback = None
        
        # Maintain latest quote as synthetic orderbook
        self.latest_bid = None
        self.latest_ask = None
        self.latest_symbol = None
        
        # Lock for thread-safe updates
        self._lock = threading.Lock()
    
    def list_symbols(self):
        """Return common symbols available on Finnhub."""
        return [
            "BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:BNBUSDT",
            "AAPL", "GOOGL", "MSFT", "TSLA", "AMZN",
            "COINBASE:BTC-USD", "COINBASE:ETH-USD"
        ]
    
    def fetch_orderbook_sync(self, symbol: str):
        """
        Fetch real-time quote via REST API and return synthetic orderbook.
        Finnhub doesn't provide full depth, so we create a 1-level book from quote.
        """
        # If WebSocket stream is running, return cached data
        with self._lock:
            if self.latest_bid is not None and self.latest_ask is not None:
                return {
                    "bids": [[self.latest_bid, 1.0]],
                    "asks": [[self.latest_ask, 1.0]]
                }
        
        # Otherwise, fetch via REST API
        try:
            # Fetch real-time quote from Finnhub REST API
            url = f"https://finnhub.io/api/v1/quote"
            params = {
                "symbol": symbol,
                "token": self.api_key
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # Extract current price (c), high (h), low (l), open (o), previous close (pc)
            current_price = data.get("c")
            
            if current_price and current_price > 0:
                # Create synthetic bid/ask with small spread (1 bps)
                spread = current_price * 0.0001
                bid = current_price - spread / 2
                ask = current_price + spread / 2
                
                # Update cached values
                with self._lock:
                    self.latest_bid = bid
                    self.latest_ask = ask
                    self.latest_symbol = symbol
                
                return {
                    "bids": [[bid, 1.0]],
                    "asks": [[ask, 1.0]]
                }
            else:
                logger.warning(f"No valid price data for {symbol}")
                return {"bids": [], "asks": []}
                
        except Exception as e:
            logger.error(f"Failed to fetch quote for {symbol}: {e}")
            return {"bids": [], "asks": []}
    
    def start_stream(self, symbol: str, callback: Callable):
        """
        Start WebSocket stream for the given symbol.
        Callback receives synthetic OrderBook objects.
        """
        if self.running:
            logger.warning("Stream already running, stopping first")
            self.stop_stream()
        
        self.callback = callback
        self.latest_symbol = symbol
        self.running = True
        
        self.ws_thread = threading.Thread(
            target=self._ws_run,
            args=(symbol,),
            daemon=True
        )
        self.ws_thread.start()
        logger.info(f"Started Finnhub stream for {symbol}")
    
    def stop_stream(self):
        """Stop the WebSocket stream."""
        self.running = False
        if self.ws:
            self.ws.close()
        if self.ws_thread:
            self.ws_thread.join(timeout=2)
        logger.info("Stopped Finnhub stream")
    
    def latest_snapshot(self):
        """Return latest synthetic orderbook."""
        with self._lock:
            if self.latest_bid is None or self.latest_ask is None:
                return None
            
            # Return dict that mimics Rust OrderBook structure
            return {
                "bids": [[self.latest_bid, 1.0]],
                "asks": [[self.latest_ask, 1.0]]
            }
    
    def _ws_run(self, symbol: str):
        """WebSocket thread main loop."""
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get("type") == "trade":
                    # Trade update: {type: 'trade', data: [{p: price, s: symbol, t: time, v: volume}]}
                    for trade in data.get("data", []):
                        price = trade.get("p")
                        if price:
                            # Update both bid and ask with small spread
                            spread = price * 0.0001  # 1 bps spread
                            with self._lock:
                                self.latest_bid = price - spread / 2
                                self.latest_ask = price + spread / 2
                            
                            # Call callback with synthetic orderbook
                            if self.callback:
                                try:
                                    ob = self._create_orderbook()
                                    self.callback(ob)
                                except Exception as e:
                                    logger.error(f"Callback error: {e}")
                
                elif data.get("type") == "ping":
                    # Respond to ping
                    ws.send(json.dumps({"type": "pong"}))
                
            except Exception as e:
                logger.error(f"Message parsing error: {e}")
        
        def on_error(ws, error):
            logger.error(f"WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        
        def on_open(ws):
            logger.info(f"WebSocket opened, subscribing to {symbol}")
            # Subscribe to trades
            subscribe_msg = json.dumps({
                "type": "subscribe",
                "symbol": symbol
            })
            ws.send(subscribe_msg)
        
        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        # Run WebSocket (blocks until closed)
        self.ws.run_forever()
    
    def _create_orderbook(self):
        """Create synthetic OrderBook-like object from latest quote."""
        with self._lock:
            # Try to import Rust OrderBook if available
            try:
                import rust_connector
                return rust_connector.OrderBook(
                    bids=[[self.latest_bid, 1.0]],
                    asks=[[self.latest_ask, 1.0]]
                )
            except Exception:
                # Return dict fallback
                return {
                    "bids": [[self.latest_bid, 1.0]],
                    "asks": [[self.latest_ask, 1.0]]
                }
    
    def set_api_credentials(self, api_key: str, api_secret: str):
        """Update API credentials (for compatibility with auth interface)."""
        self.api_key = api_key
        self.ws_url = f"wss://ws.finnhub.io?token={api_key}"
