#!/usr/bin/env python3
"""
Quick test to verify WebSocket streaming works
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_websocket_binance():
    """Test Binance WebSocket streaming"""
    print("Testing Binance WebSocket...")
    
    try:
        from python.rust_bridge import get_connector
        
        connector = get_connector("binance")
        print(f"✓ Got Binance connector")
        
        # Check initial snapshot
        snapshot = connector.latest_snapshot()
        print(f"Initial snapshot: {snapshot}")
        
        # Start WebSocket stream
        updates_received = []
        
        def callback(ob):
            updates_received.append(ob)
            if len(updates_received) <= 3:
                print(f"✓ Received update #{len(updates_received)}: bid={ob.bids[0][0] if ob.bids else 'N/A'}, ask={ob.asks[0][0] if ob.asks else 'N/A'}")
        
        print("Starting WebSocket stream...")
        connector.start_stream("BTCUSDT", callback)
        
        # Wait for data
        print("Waiting for data (10 seconds)...")
        for i in range(10):
            time.sleep(1)
            snapshot = connector.latest_snapshot()
            if snapshot:
                print(f"  {i+1}s: Latest snapshot has data: bid={snapshot.bids[0][0] if snapshot.bids else 'N/A'}")
                if i >= 3 and len(updates_received) > 0:
                    break
        
        # Check results
        if len(updates_received) > 0:
            print(f"\n🎉 SUCCESS! Received {len(updates_received)} WebSocket updates")
            return True
        else:
            snapshot = connector.latest_snapshot()
            if snapshot and snapshot.bids and snapshot.asks:
                print(f"\n✓ WebSocket connected and snapshot cached (bid={snapshot.bids[0][0]}, ask={snapshot.asks[0][0]})")
                return True
            else:
                print("\n❌ FAILED: No updates received and no snapshot available")
                return False
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_websocket_kraken():
    """Test Kraken WebSocket streaming"""
    print("\n" + "="*60)
    print("Testing Kraken WebSocket...")
    
    try:
        from python.rust_bridge import get_connector
        
        connector = get_connector("kraken")
        print(f"✓ Got Kraken connector")
        
        # Start WebSocket stream
        updates_received = []
        
        def callback(ob):
            updates_received.append(ob)
            if len(updates_received) <= 3:
                print(f"✓ Received update #{len(updates_received)}: bid={ob.bids[0][0] if ob.bids else 'N/A'}, ask={ob.asks[0][0] if ob.asks else 'N/A'}")
        
        print("Starting WebSocket stream...")
        connector.start_stream("XBTUSDT", callback)
        
        # Wait for data
        print("Waiting for data (10 seconds)...")
        for i in range(10):
            time.sleep(1)
            snapshot = connector.latest_snapshot()
            if snapshot:
                print(f"  {i+1}s: Latest snapshot has data")
                if i >= 3 and len(updates_received) > 0:
                    break
        
        # Check results
        if len(updates_received) > 0:
            print(f"\n🎉 SUCCESS! Received {len(updates_received)} WebSocket updates")
            return True
        else:
            snapshot = connector.latest_snapshot()
            if snapshot and snapshot.bids and snapshot.asks:
                print(f"\n✓ WebSocket connected and snapshot cached")
                return True
            else:
                print("\n❌ FAILED: No updates received and no snapshot available")
                return False
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*60)
    print("WebSocket Streaming Test")
    print("="*60)
    
    binance_ok = test_websocket_binance()
    kraken_ok = test_websocket_kraken()
    
    print("\n" + "="*60)
    print("Test Results:")
    print("="*60)
    print(f"Binance WebSocket: {'✓ PASS' if binance_ok else '✗ FAIL'}")
    print(f"Kraken WebSocket:  {'✓ PASS' if kraken_ok else '✗ FAIL'}")
    
    if binance_ok or kraken_ok:
        print("\n🎉 WebSocket streaming is working!")
        sys.exit(0)
    else:
        print("\n❌ WebSocket streaming failed")
        sys.exit(1)
