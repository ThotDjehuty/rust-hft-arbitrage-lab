# python/connectors/authenticated.py
"""
Python wrappers that add authentication to existing Rust connectors.
Uses HMAC-SHA256 signing for Binance and Coinbase authenticated endpoints.
"""

import hmac
import hashlib
import time
import requests
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

try:
    import rust_connector
    RUST_AVAILABLE = True
except ImportError:
    rust_connector = None
    RUST_AVAILABLE = False

# Import API keys loader
try:
    from python.api_keys import get_binance_credentials, get_coinbase_credentials, get_kraken_credentials
    API_KEYS_AVAILABLE = True
except ImportError:
    API_KEYS_AVAILABLE = False
    logger.warning("Could not import api_keys module")


class AuthenticatedBinance:
    """
    Wrapper around Rust Binance connector that adds authenticated REST endpoints.
    Public methods delegate to Rust; private methods use Python + HMAC signing.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        # Auto-load credentials from api_keys.properties if not provided
        if (api_key is None or api_secret is None) and API_KEYS_AVAILABLE:
            loaded_key, loaded_secret = get_binance_credentials()
            api_key = api_key or loaded_key
            api_secret = api_secret or loaded_secret
        
        if not api_key or not api_secret:
            raise ValueError(
                "Binance credentials not found. Please:\n"
                "1. Copy api_keys.properties.example to api_keys.properties\n"
                "2. Fill in BINANCE_API_KEY and BINANCE_API_SECRET\n"
                "Or provide credentials explicitly to the constructor."
            )
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.name = "binance_auth"
        
        # Delegate public data to Rust connector if available
        if RUST_AVAILABLE:
            try:
                self._rust_conn = rust_connector.get_connector("binance")
            except Exception as e:
                logger.warning(f"Rust connector failed, using pure Python: {e}")
                self._rust_conn = None
        else:
            self._rust_conn = None
        
        self.base_url = "https://api.binance.com"
    
    def list_symbols(self):
        """Delegate to Rust or return defaults."""
        if self._rust_conn and hasattr(self._rust_conn, "list_symbols"):
            return self._rust_conn.list_symbols()
        return ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    
    def fetch_orderbook_sync(self, symbol: str):
        """Public orderbook - delegate to Rust."""
        if self._rust_conn and hasattr(self._rust_conn, "fetch_orderbook_sync"):
            return self._rust_conn.fetch_orderbook_sync(symbol)
        # Fallback
        url = f"{self.base_url}/api/v3/depth?symbol={symbol.upper()}&limit=5"
        resp = requests.get(url)
        data = resp.json()
        bids = [[float(p), float(q)] for p, q in data.get("bids", [])]
        asks = [[float(p), float(q)] for p, q in data.get("asks", [])]
        return {"bids": bids, "asks": asks}
    
    def start_stream(self, symbol: str, callback):
        """Delegate WebSocket streaming to Rust."""
        if self._rust_conn and hasattr(self._rust_conn, "start_stream"):
            return self._rust_conn.start_stream(symbol, callback)
        raise NotImplementedError("Streaming requires Rust connector")
    
    def latest_snapshot(self):
        """Delegate to Rust."""
        if self._rust_conn and hasattr(self._rust_conn, "latest_snapshot"):
            return self._rust_conn.latest_snapshot()
        return None
    
    def _sign_request(self, params: Dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for Binance."""
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def get_account_info(self) -> Dict[str, Any]:
        """Authenticated endpoint: account info."""
        endpoint = "/api/v3/account"
        params = {"timestamp": int(time.time() * 1000)}
        params["signature"] = self._sign_request(params)
        
        headers = {"X-MBX-APIKEY": self.api_key}
        url = self.base_url + endpoint
        resp = requests.get(url, params=params, headers=headers)
        return resp.json()
    
    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Authenticated endpoint: open orders."""
        endpoint = "/api/v3/openOrders"
        params = {"timestamp": int(time.time() * 1000)}
        if symbol:
            params["symbol"] = symbol.upper()
        params["signature"] = self._sign_request(params)
        
        headers = {"X-MBX-APIKEY": self.api_key}
        url = self.base_url + endpoint
        resp = requests.get(url, params=params, headers=headers)
        return resp.json()
    
    def place_order(self, symbol: str, side: str, order_type: str, 
                   quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
        """Authenticated endpoint: place order."""
        endpoint = "/api/v3/order"
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
            "timestamp": int(time.time() * 1000)
        }
        if price is not None:
            params["price"] = price
            params["timeInForce"] = "GTC"
        
        params["signature"] = self._sign_request(params)
        headers = {"X-MBX-APIKEY": self.api_key}
        url = self.base_url + endpoint
        resp = requests.post(url, params=params, headers=headers)
        return resp.json()


class AuthenticatedCoinbase:
    """
    Wrapper around Rust Coinbase connector that adds authenticated REST endpoints.
    Uses CB-ACCESS-* headers for authentication.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, passphrase: Optional[str] = None):
        # Auto-load credentials from api_keys.properties if not provided
        if (api_key is None or api_secret is None or passphrase is None) and API_KEYS_AVAILABLE:
            loaded_key, loaded_secret, loaded_passphrase = get_coinbase_credentials()
            api_key = api_key or loaded_key
            api_secret = api_secret or loaded_secret
            passphrase = passphrase or loaded_passphrase
        
        if not api_key or not api_secret or not passphrase:
            raise ValueError(
                "Coinbase credentials not found. Please:\n"
                "1. Copy api_keys.properties.example to api_keys.properties\n"
                "2. Fill in COINBASE_API_KEY, COINBASE_API_SECRET, and COINBASE_PASSPHRASE\n"
                "Or provide credentials explicitly to the constructor."
            )
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.name = "coinbase_auth"
        
        # Delegate public data to Rust connector if available
        if RUST_AVAILABLE:
            try:
                self._rust_conn = rust_connector.get_connector("coinbase")
            except Exception as e:
                logger.warning(f"Rust connector failed: {e}")
                self._rust_conn = None
        else:
            self._rust_conn = None
        
        self.base_url = "https://api.exchange.coinbase.com"
    
    def list_symbols(self):
        """Delegate to Rust or return defaults."""
        if self._rust_conn and hasattr(self._rust_conn, "list_symbols"):
            return self._rust_conn.list_symbols()
        return ["BTC-USD", "ETH-USD"]
    
    def fetch_orderbook_sync(self, symbol: str):
        """Public orderbook - delegate to Rust."""
        if self._rust_conn and hasattr(self._rust_conn, "fetch_orderbook_sync"):
            return self._rust_conn.fetch_orderbook_sync(symbol)
        # Fallback
        url = f"{self.base_url}/products/{symbol}/book?level=2"
        resp = requests.get(url)
        data = resp.json()
        bids = [[float(p), float(q)] for p, q, _ in data.get("bids", [])]
        asks = [[float(p), float(q)] for p, q, _ in data.get("asks", [])]
        return {"bids": bids, "asks": asks}
    
    def start_stream(self, symbol: str, callback):
        """Delegate WebSocket streaming to Rust."""
        if self._rust_conn and hasattr(self._rust_conn, "start_stream"):
            return self._rust_conn.start_stream(symbol, callback)
        raise NotImplementedError("Streaming requires Rust connector")
    
    def latest_snapshot(self):
        """Delegate to Rust."""
        if self._rust_conn and hasattr(self._rust_conn, "latest_snapshot"):
            return self._rust_conn.latest_snapshot()
        return None
    
    def _sign_request(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        """Generate CB-ACCESS-SIGN header."""
        message = timestamp + method + path + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_auth_headers(self, method: str, path: str, body: str = '') -> Dict[str, str]:
        """Generate Coinbase Pro authentication headers."""
        timestamp = str(time.time())
        signature = self._sign_request(timestamp, method, path, body)
        return {
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-SIGN': signature,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    def get_accounts(self) -> list:
        """Authenticated endpoint: accounts."""
        path = '/accounts'
        headers = self._get_auth_headers('GET', path)
        url = self.base_url + path
        resp = requests.get(url, headers=headers)
        return resp.json()
    
    def get_orders(self, status: str = 'open') -> list:
        """Authenticated endpoint: orders."""
        path = f'/orders?status={status}'
        headers = self._get_auth_headers('GET', path)
        url = self.base_url + path
        resp = requests.get(url, headers=headers)
        return resp.json()
    
    def place_order(self, product_id: str, side: str, order_type: str,
                   size: Optional[float] = None, price: Optional[float] = None) -> Dict[str, Any]:
        """Authenticated endpoint: place order."""
        import json
        path = '/orders'
        body_dict = {
            'product_id': product_id,
            'side': side.lower(),
            'type': order_type.lower()
        }
        if size:
            body_dict['size'] = str(size)
        if price:
            body_dict['price'] = str(price)
        
        body = json.dumps(body_dict)
        headers = self._get_auth_headers('POST', path, body)
        url = self.base_url + path
        resp = requests.post(url, headers=headers, data=body)
        return resp.json()


class AuthenticatedKraken:
    """
    Wrapper around Rust Kraken connector that adds authenticated REST endpoints.
    Uses API-Key and API-Sign headers for authentication.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        # Auto-load credentials from api_keys.properties if not provided
        if (api_key is None or api_secret is None) and API_KEYS_AVAILABLE:
            loaded_key, loaded_secret = get_kraken_credentials()
            api_key = api_key or loaded_key
            api_secret = api_secret or loaded_secret
        
        if not api_key or not api_secret:
            raise ValueError(
                "Kraken credentials not found. Please:\n"
                "1. Copy api_keys.properties.example to api_keys.properties\n"
                "2. Fill in KRAKEN_API_KEY and KRAKEN_API_SECRET\n"
                "Or provide credentials explicitly to the constructor."
            )
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.name = "kraken_auth"
        
        # Delegate public data to Rust connector if available
        if RUST_AVAILABLE:
            try:
                self._rust_conn = rust_connector.get_connector("kraken")
            except Exception as e:
                logger.warning(f"Rust connector failed, using pure Python: {e}")
                self._rust_conn = None
        else:
            self._rust_conn = None
        
        self.base_url = "https://api.kraken.com"
    
    def list_symbols(self):
        """Delegate to Rust or return defaults."""
        if self._rust_conn and hasattr(self._rust_conn, "list_symbols"):
            return self._rust_conn.list_symbols()
        return ["XBTUSDT", "ETHUSDT", "XXBTZUSD"]
    
    def fetch_orderbook_sync(self, symbol: str):
        """Public orderbook - delegate to Rust."""
        if self._rust_conn and hasattr(self._rust_conn, "fetch_orderbook_sync"):
            return self._rust_conn.fetch_orderbook_sync(symbol)
        # Fallback
        url = f"{self.base_url}/0/public/Depth?pair={symbol}&count=5"
        resp = requests.get(url)
        data = resp.json()
        if "result" in data:
            for pair_data in data["result"].values():
                bids = [[float(p), float(q)] for p, q, *_ in pair_data.get("bids", [])]
                asks = [[float(p), float(q)] for p, q, *_ in pair_data.get("asks", [])]
                return {"bids": bids[:5], "asks": asks[:5]}
        return {"bids": [], "asks": []}
    
    def start_stream(self, symbol: str, callback):
        """Delegate WebSocket streaming to Rust."""
        if self._rust_conn and hasattr(self._rust_conn, "start_stream"):
            return self._rust_conn.start_stream(symbol, callback)
        raise NotImplementedError("Streaming requires Rust connector")
    
    def latest_snapshot(self):
        """Delegate to Rust."""
        if self._rust_conn and hasattr(self._rust_conn, "latest_snapshot"):
            return self._rust_conn.latest_snapshot()
        return None
    
    def _sign_request(self, urlpath: str, data: Dict[str, Any]) -> str:
        """Generate Kraken API signature."""
        import base64
        import urllib.parse
        
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        
        signature = hmac.new(
            base64.b64decode(self.api_secret),
            message,
            hashlib.sha512
        )
        return base64.b64encode(signature.digest()).decode()
    
    def get_account_balance(self) -> Dict[str, Any]:
        """Authenticated endpoint: account balance."""
        urlpath = "/0/private/Balance"
        data = {"nonce": str(int(time.time() * 1000))}
        
        headers = {
            "API-Key": self.api_key,
            "API-Sign": self._sign_request(urlpath, data)
        }
        
        url = self.base_url + urlpath
        resp = requests.post(url, headers=headers, data=data)
        return resp.json()
    
    def place_order(self, pair: str, type: str, ordertype: str,
                   volume: float, price: Optional[float] = None) -> Dict[str, Any]:
        """Authenticated endpoint: place order."""
        urlpath = "/0/private/AddOrder"
        data = {
            "nonce": str(int(time.time() * 1000)),
            "pair": pair,
            "type": type,  # buy or sell
            "ordertype": ordertype,  # market, limit
            "volume": str(volume)
        }
        if price is not None:
            data["price"] = str(price)
        
        headers = {
            "API-Key": self.api_key,
            "API-Sign": self._sign_request(urlpath, data)
        }
        
        url = self.base_url + urlpath
        resp = requests.post(url, headers=headers, data=data)
        return resp.json()
