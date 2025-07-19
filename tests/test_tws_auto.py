#!/usr/bin/env python3
"""
Automated TWS Connection Test Script
Tests connection to Interactive Brokers TWS API without user input
"""

import time
import threading
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.common import TickerId


class TWSApp(EWrapper, EClient):
    """Main application class for TWS connection testing"""
    
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.next_order_id = None
        self.connection_successful = False
        
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson=""):
        """Handle error messages"""
        if errorCode == 502:
            print(f"❌ Connection failed: TWS not running or API not enabled")
        elif errorCode == 504:
            print(f"❌ Connection failed: Not connected to TWS")
        else:
            print(f"Error {errorCode}: {errorString}")
        
    def connectAck(self):
        """Called when connection is acknowledged"""
        print("✅ Connection acknowledged by TWS")
        self.connection_successful = True
        
    def connectionClosed(self):
        """Called when connection is closed"""
        print("❌ Connection closed")
        self.connected = False
        
    def nextValidId(self, orderId: int):
        """Receive next valid order id"""
        print(f"✅ Next valid order ID: {orderId}")
        self.next_order_id = orderId
        
    def managedAccounts(self, accountsList: str):
        """Receive managed accounts"""
        accounts = accountsList.split(",")
        print(f"✅ Managed accounts: {accounts}")


def test_connection_auto():
    """Automatically test connection to TWS"""
    app = TWSApp()
    
    # Connection parameters
    host = "127.0.0.1"
    port = 7497  # Paper trading port
    client_id = 1
    
    print("TWS Connection Test (Automated)")
    print("=" * 50)
    print(f"Attempting connection to {host}:{port}")
    print("Testing paper trading port (7497)...")
    print("-" * 50)
    
    try:
        # Connect to TWS
        app.connect(host, port, client_id)
        
        # Start the socket in a separate thread
        api_thread = threading.Thread(target=app.run)
        api_thread.daemon = True
        api_thread.start()
        
        # Wait for connection
        timeout = 5
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if app.isConnected():
                break
            time.sleep(0.1)
        
        if app.isConnected():
            print("✅ Successfully connected to TWS!")
            
            # Wait for initial data
            time.sleep(2)
            
            # Request managed accounts
            app.reqManagedAccts()
            time.sleep(1)
            
            print("✅ Connection test successful!")
            return True
            
        else:
            print("❌ Failed to connect to TWS")
            print("\nTroubleshooting:")
            print("1. Make sure TWS is running")
            print("2. Enable API in TWS: Configure > API > Settings")
            print("3. Check 'Enable ActiveX and Socket Clients'")
            print("4. Verify port 7497 is set for Socket Port")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
        
    finally:
        if app.isConnected():
            app.disconnect()
        time.sleep(1)


def test_live_port():
    """Test connection to live trading port"""
    app = TWSApp()
    
    print("\nTesting live trading port (7496)...")
    print("-" * 50)
    
    try:
        app.connect("127.0.0.1", 7496, 2)
        
        api_thread = threading.Thread(target=app.run)
        api_thread.daemon = True
        api_thread.start()
        
        time.sleep(3)
        
        if app.isConnected():
            print("✅ Live trading port accessible")
            app.disconnect()
            return True
        else:
            print("❌ Live trading port not accessible")
            return False
            
    except Exception as e:
        print(f"❌ Live port error: {e}")
        return False


if __name__ == "__main__":
    # Test paper trading port
    paper_success = test_connection_auto()
    
    # Test live trading port
    live_success = test_live_port()
    
    print("\n" + "=" * 50)
    print("CONNECTION TEST SUMMARY")
    print("=" * 50)
    print(f"Paper Trading (7497): {'✅ SUCCESS' if paper_success else '❌ FAILED'}")
    print(f"Live Trading (7496):  {'✅ SUCCESS' if live_success else '❌ FAILED'}")
    
    if not paper_success and not live_success:
        print("\n❌ No TWS connections available")
        print("\nSetup Instructions:")
        print("1. Download and install TWS from Interactive Brokers")
        print("2. Login to TWS")
        print("3. Go to Configure > API > Settings")
        print("4. Check 'Enable ActiveX and Socket Clients'")
        print("5. Set Socket Port to 7497 (paper) or 7496 (live)")
        print("6. Add 127.0.0.1 to Trusted IPs if needed")
    else:
        print("\n✅ TWS API connection is working!")