# python/rust_bridge.py
# Async-aware bridge that prefers the Rust implementation when available.
# Presents the same API used by the Streamlit UI and notebooks.

from typing import Any, List
import logging

logger = logging.getLogger(__name__)
try:
    import rust_connector  # type: ignore
    RUST_AVAILABLE = True
    logger.info("rust_connector available")
except Exception as e:
    rust_connector = None
    RUST_AVAILABLE = False
    logger.warning("rust_connector not available: %s", e)

def list_connectors() -> List[str]:
    """List all available connectors including authenticated and third-party."""
    base_connectors = ["binance", "coinbase", "uniswap", "mock"]
    
    if RUST_AVAILABLE and hasattr(rust_connector, "list_connectors"):
        try:
            base_connectors = rust_connector.list_connectors()
        except Exception:
            logger.exception("rust list_connectors failed")
    
    # Add authenticated and external connectors
    return base_connectors + ["binance_auth", "coinbase_auth", "kraken_auth", "finnhub"]

from typing import Optional


def get_connector(name: str, api_key: Optional[str] = None, api_secret: Optional[str] = None, 
                 passphrase: Optional[str] = None):
    """Return a connector instance. If credentials are provided, attempt to set them on the
    returned connector object (works for Python fallback and, where available, Rust connector
    implementations exposing a credentials setter).
    
    Special connectors:
    - binance_auth, coinbase_auth: Use authenticated Python wrappers
    - finnhub: Use Finnhub Python connector
    """
    # Handle authenticated Python wrappers
    if name == "binance_auth":
        from python.connectors.authenticated import AuthenticatedBinance
        # Credentials are optional - auto-loaded from api_keys.properties if not provided
        return AuthenticatedBinance(api_key, api_secret)
    
    if name == "coinbase_auth":
        from python.connectors.authenticated import AuthenticatedCoinbase
        # Credentials are optional - auto-loaded from api_keys.properties if not provided
        return AuthenticatedCoinbase(api_key, api_secret, passphrase)
    
    if name == "kraken_auth":
        from python.connectors.authenticated import AuthenticatedKraken
        # Credentials are optional - auto-loaded from api_keys.properties if not provided
        return AuthenticatedKraken(api_key, api_secret)
    
    if name == "finnhub":
        from python.connectors.finnhub import FinnhubConnector
        # API key is optional - auto-loaded from api_keys.properties if not provided
        return FinnhubConnector(api_key)
    
    # Standard Rust connectors
    if RUST_AVAILABLE and hasattr(rust_connector, "get_connector"):
        try:
            conn = rust_connector.get_connector(name)
            # Best-effort: try setting credentials if the Rust-side connector exposes a setter.
            if api_key or api_secret:
                try:
                    if hasattr(conn, "set_api_credentials"):
                        conn.set_api_credentials(api_key or "", api_secret or "")
                    elif hasattr(conn, "set_api_key") and api_key:
                        conn.set_api_key(api_key)
                except Exception:
                    logger.exception("Failed to set credentials on rust connector (ignored)")
            return conn
        except Exception:
            logger.exception("rust get_connector failed; falling back to Python adapter")

    # Fallback adapter with same methods and optional credentials storage
    class _Fallback:
        def __init__(self, n, api_key: Optional[str] = None, api_secret: Optional[str] = None):
            import time
            import random
            self.name = n
            self.symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
            self.api_key = api_key
            self.api_secret = api_secret
            self._base_prices = {"BTCUSDT": 43000.0, "ETHUSDT": 2300.0, "BNBUSDT": 310.0}
            self._random = random.Random()

        def list_symbols(self):
            return self.symbols

        def fetch_orderbook_sync(self, symbol):
            # Generate realistic-looking orderbook with some random variation
            import time
            base_price = self._base_prices.get(symbol, 100.0)
            # Add some time-based variation
            variation = (time.time() % 100) / 1000  # Small variation based on time
            price = base_price * (1.0 + variation + self._random.uniform(-0.001, 0.001))
            spread = price * 0.0002  # 2 bps spread
            bid = price - spread / 2
            ask = price + spread / 2
            return {"bids": [[bid, 1.0]], "asks": [[ask, 1.0]]}

        def start_stream(self, symbol, cb):
            raise NotImplementedError("Fallback connector does not support streaming")

        def latest_snapshot(self):
            return None

        def set_api_credentials(self, api_key: str, api_secret: str):
            self.api_key = api_key
            self.api_secret = api_secret

    return _Fallback(name, api_key, api_secret)

def compute_dex_cex_arbitrage(ob_cex: Any, ob_dex: Any, fee_cex: float = 0.001, fee_dex: float = 0.002):
    if RUST_AVAILABLE and hasattr(rust_connector, "compute_dex_cex_arbitrage"):
        try:
            return rust_connector.compute_dex_cex_arbitrage(ob_cex, ob_dex, fee_cex, fee_dex)
        except Exception:
            logger.exception("rust compute_dex_cex_arbitrage failed")
    # fallback python
    try:
        cex_bid = ob_cex["bids"][0][0] if isinstance(ob_cex, dict) else ob_cex.bids[0][0]
        dex_price = ob_dex["bids"][0][0] if isinstance(ob_dex, dict) else ob_dex.bids[0][0]
        gross = cex_bid / dex_price - 1.0 if dex_price != 0 else 0.0
        net = (1 - fee_dex) * (1 + gross) * (1 - fee_cex) - 1.0
        return {"gross": gross, "net": net}
    except Exception:
        return {"gross": 0.0, "net": 0.0}