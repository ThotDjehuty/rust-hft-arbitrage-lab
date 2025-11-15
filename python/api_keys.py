"""
Simple utility to load API keys from api_keys.properties file.
"""

import os
from pathlib import Path
from typing import Optional, Dict

_API_KEYS: Dict[str, str] = {}
_LOADED = False


def load_api_keys() -> Dict[str, str]:
    """Load API keys from api_keys.properties file."""
    global _API_KEYS, _LOADED
    
    if _LOADED:
        return _API_KEYS
    
    # Find api_keys.properties in project root
    current_file = Path(__file__)
    project_root = current_file.parent.parent
    props_file = project_root / 'api_keys.properties'
    
    if not props_file.exists():
        _LOADED = True
        return _API_KEYS
    
    try:
        with open(props_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Only load non-placeholder values
                    if value and not value.startswith('your_'):
                        _API_KEYS[key] = value
    except Exception as e:
        print(f"Warning: Could not load api_keys.properties: {e}")
    
    _LOADED = True
    return _API_KEYS


def get_api_key(key_name: str) -> Optional[str]:
    """
    Get an API key by name.
    Priority: api_keys.properties > environment variable
    """
    load_api_keys()
    
    # Try properties file first
    if key_name in _API_KEYS:
        return _API_KEYS[key_name]
    
    # Fall back to environment variable
    env_value = os.environ.get(key_name)
    if env_value and env_value.strip() and not env_value.startswith('your_'):
        return env_value.strip()
    
    return None


# Convenience functions for specific APIs
def get_finnhub_key() -> Optional[str]:
    return get_api_key('FINNHUB_API_KEY')


def get_binance_credentials() -> tuple[Optional[str], Optional[str]]:
    return (get_api_key('BINANCE_API_KEY'), get_api_key('BINANCE_API_SECRET'))


def get_coinbase_credentials() -> tuple[Optional[str], Optional[str], Optional[str]]:
    return (
        get_api_key('COINBASE_API_KEY'),
        get_api_key('COINBASE_API_SECRET'),
        get_api_key('COINBASE_PASSPHRASE')
    )


def get_kraken_credentials() -> tuple[Optional[str], Optional[str]]:
    return (get_api_key('KRAKEN_API_KEY'), get_api_key('KRAKEN_API_SECRET'))
