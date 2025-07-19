#!/usr/bin/env python3
"""
TWS Connection Test Script
Tests connection to Interactive Brokers TWS API
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
        self.account_info = {}
        
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson=""):
        """Handle error messages"""
        print(f"Error {errorCode}: {errorString}")
        
    def connectAck(self):
        """Called when connection is acknowledged"""
        print("✅ Connection acknowledged by TWS")
        
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
        
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """Receive account summary"""
        print(f"Account {account}: {tag} = {value} {currency}")
        
    def accountSummaryEnd(self, reqId: int):
        """Account summary complete"""
        print("✅ Account summary complete")
        
    def tickPrice(self, reqId: TickerId, tickType: int, price: float, attrib):
        """Receive tick price data"""
        tick_types = {1: "Bid", 2: "Ask", 4: "Last", 6: "High", 7: "Low", 9: "Close"}
        tick_name = tick_types.get(tickType, f"Type_{tickType}")
        print(f"✅ {tick_name} price: ${price}")


def test_connection():
    """Test connection to TWS"""
    app = TWSApp()
    
    # Connection parameters
    host = "127.0.0.1"  # localhost
    port = 7497         # TWS paper trading port (7496 for live)
    client_id = 1       # unique client ID
    
    print("🔌 Attempting to connect to TWS...")
    print(f"Host: {host}, Port: {port}, Client ID: {client_id}")
    print("Make sure TWS is running and API is enabled!")
    print("-" * 50)
    
    try:
        # Connect to TWS
        app.connect(host, port, client_id)
        
        # Start the socket in a separate thread
        api_thread = threading.Thread(target=app.run)
        api_thread.daemon = True
        api_thread.start()
        
        # Wait a moment for connection
        time.sleep(2)
        
        if app.isConnected():
            print("✅ Successfully connected to TWS!")
            app.connected = True
            
            # Request managed accounts
            print("\n📊 Requesting account information...")
            app.reqManagedAccts()
            time.sleep(1)
            
            # Request account summary
            if app.next_order_id:
                app.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds")
                time.sleep(2)
            
            # Test market data request for AAPL
            print("\n📈 Testing market data request for AAPL...")
            contract = Contract()
            contract.symbol = "AAPL"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            app.reqMktData(1001, contract, "", False, False, [])
            time.sleep(3)
            
            # Cancel market data
            app.cancelMktData(1001)
            
        else:
            print("❌ Failed to connect to TWS")
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        
    finally:
        print("\n🔌 Disconnecting...")
        if app.isConnected():
            app.disconnect()
        time.sleep(1)
        print("✅ Test complete!")


if __name__ == "__main__":
    print("TWS Connection Test")
    print("=" * 50)
    print("Prerequisites:")
    print("1. TWS (Trader Workstation) must be running")
    print("2. API must be enabled in TWS (Configure > API > Settings)")
    print("3. Socket port should be 7497 (paper) or 7496 (live)")
    print("4. 'Enable ActiveX and Socket Clients' should be checked")
    print("=" * 50)
    
    input("Press Enter when TWS is ready...")
    test_connection()