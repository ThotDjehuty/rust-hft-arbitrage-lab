#!/usr/bin/env python3
"""
Test script to verify api_keys.properties loading works correctly.
Run this after setting up your api_keys.properties file.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_api_keys_module():
    """Test the api_keys module loads correctly."""
    print("Testing api_keys module...")
    try:
        from python.api_keys import load_api_keys, get_api_key
        keys = load_api_keys()
        print(f"✓ Module loaded successfully")
        print(f"✓ Found {len(keys)} API keys in properties file")
        return True
    except Exception as e:
        print(f"✗ Failed to load api_keys module: {e}")
        return False

def test_finnhub_key():
    """Test Finnhub API key loading."""
    print("\nTesting Finnhub API key...")
    try:
        from python.api_keys import get_api_key
        key = get_api_key("FINNHUB_API_KEY")
        if key:
            print(f"✓ Finnhub key found: {key[:8]}...")
            return True
        else:
            print("⚠ Finnhub key not configured (optional)")
            return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_binance_credentials():
    """Test Binance credentials loading."""
    print("\nTesting Binance credentials...")
    try:
        from python.api_keys import get_binance_credentials
        key, secret = get_binance_credentials()
        if key and secret:
            print(f"✓ Binance key found: {key[:8]}...")
            print(f"✓ Binance secret found: {secret[:8]}...")
            return True
        else:
            print("⚠ Binance credentials not configured (optional)")
            return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_coinbase_credentials():
    """Test Coinbase credentials loading."""
    print("\nTesting Coinbase credentials...")
    try:
        from python.api_keys import get_coinbase_credentials
        key, secret, passphrase = get_coinbase_credentials()
        if key and secret and passphrase:
            print(f"✓ Coinbase key found: {key[:8]}...")
            print(f"✓ Coinbase secret found: {secret[:8]}...")
            print(f"✓ Coinbase passphrase found: {passphrase[:4]}...")
            return True
        else:
            print("⚠ Coinbase credentials not configured (optional)")
            return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_finnhub_connector():
    """Test FinnhubConnector initialization."""
    print("\nTesting FinnhubConnector...")
    try:
        from python.connectors.finnhub import FinnhubConnector
        connector = FinnhubConnector()  # Should auto-load key
        print(f"✓ FinnhubConnector initialized successfully")
        print(f"✓ Connector name: {connector.name}")
        return True
    except ValueError as e:
        print(f"⚠ FinnhubConnector not configured: {e}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_authenticated_binance():
    """Test AuthenticatedBinance initialization."""
    print("\nTesting AuthenticatedBinance...")
    try:
        from python.connectors.authenticated import AuthenticatedBinance
        connector = AuthenticatedBinance()  # Should auto-load credentials
        print(f"✓ AuthenticatedBinance initialized successfully")
        print(f"✓ Connector name: {connector.name}")
        return True
    except ValueError as e:
        print(f"⚠ AuthenticatedBinance not configured: {e}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_authenticated_coinbase():
    """Test AuthenticatedCoinbase initialization."""
    print("\nTesting AuthenticatedCoinbase...")
    try:
        from python.connectors.authenticated import AuthenticatedCoinbase
        connector = AuthenticatedCoinbase()  # Should auto-load credentials
        print(f"✓ AuthenticatedCoinbase initialized successfully")
        print(f"✓ Connector name: {connector.name}")
        return True
    except ValueError as e:
        print(f"⚠ AuthenticatedCoinbase not configured: {e}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_rust_bridge():
    """Test rust_bridge get_connector with auto-loading."""
    print("\nTesting rust_bridge.get_connector()...")
    try:
        from python.rust_bridge import get_connector
        
        # Test Finnhub
        try:
            connector = get_connector("finnhub")
            print(f"✓ get_connector('finnhub') works")
        except ValueError:
            print(f"⚠ Finnhub not configured in properties file")
        
        # Test Binance Auth
        try:
            connector = get_connector("binance_auth")
            print(f"✓ get_connector('binance_auth') works")
        except ValueError:
            print(f"⚠ Binance not configured in properties file")
        
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def main():
    print("=" * 60)
    print("API Keys Migration Test Suite")
    print("=" * 60)
    
    # Check if properties file exists
    props_file = Path(__file__).parent / "api_keys.properties"
    if not props_file.exists():
        print("\n⚠ WARNING: api_keys.properties not found!")
        print("Please run: cp api_keys.properties.example api_keys.properties")
        print("Then edit it with your actual credentials.\n")
    
    results = []
    
    # Run tests
    results.append(("API Keys Module", test_api_keys_module()))
    results.append(("Finnhub Key", test_finnhub_key()))
    results.append(("Binance Credentials", test_binance_credentials()))
    results.append(("Coinbase Credentials", test_coinbase_credentials()))
    results.append(("FinnhubConnector", test_finnhub_connector()))
    results.append(("AuthenticatedBinance", test_authenticated_binance()))
    results.append(("AuthenticatedCoinbase", test_authenticated_coinbase()))
    results.append(("Rust Bridge", test_rust_bridge()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! API keys migration is working correctly.")
        return 0
    else:
        print("\n⚠ Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
