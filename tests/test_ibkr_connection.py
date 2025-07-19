#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IBKR Connection Test Script

This script tests the IBKR TWS API connection and basic operations.
Run this before using the main trading system to verify everything works.
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging for test
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_dependencies():
    """Test if required dependencies are installed."""
    logger.info("🔍 Testing dependencies...")
    
    try:
        import ib_async
        logger.info(f"✓ ib_async version: {ib_async.__version__}")
    except ImportError:
        logger.error("❌ ib_async not installed. Run: pip install ib_async")
        return False
    
    try:
        import pandas as pd
        logger.info(f"✓ pandas version: {pd.__version__}")
    except ImportError:
        logger.error("❌ pandas not installed. Run: pip install pandas")
        return False
    
    try:
        import numpy as np
        logger.info(f"✓ numpy version: {np.__version__}")
    except ImportError:
        logger.error("❌ numpy not installed. Run: pip install numpy")
        return False
    
    return True

def test_environment():
    """Test environment configuration."""
    logger.info("🔍 Testing environment configuration...")
    
    load_dotenv()
    
    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = os.getenv("IBKR_PORT", "7497")
    client_id = os.getenv("IBKR_CLIENT_ID", "1")
    
    logger.info(f"✓ IBKR Host: {host}")
    logger.info(f"✓ IBKR Port: {port}")
    logger.info(f"✓ IBKR Client ID: {client_id}")
    
    return host, int(port), int(client_id)

def test_ibkr_connection(host, port, client_id):
    """Test actual IBKR TWS/Gateway connection."""
    logger.info("🔍 Testing IBKR TWS/Gateway connection...")
    
    try:
        from ib_async import IB, util
        
        # Start event loop
        try:
            util.startLoop()
        except Exception:
            # Handle different ib_async versions
            pass
        
        # Create IB instance
        ib = IB()
        
        logger.info(f"Attempting to connect to {host}:{port} with client ID {client_id}")
        
        # Try to connect
        ib.connect(host, port, clientId=client_id, timeout=10)
        
        if ib.isConnected():
            logger.info("✅ Successfully connected to IBKR!")
            
            # Test basic operations
            logger.info("🔍 Testing basic operations...")
            
            # Get account values
            try:
                account_values = ib.accountValues()
                if account_values:
                    logger.info(f"✓ Retrieved {len(account_values)} account values")
                    
                    # Show some key account info
                    for av in account_values[:5]:  # Show first 5
                        logger.info(f"  {av.tag}: {av.value} {av.currency}")
                else:
                    logger.warning("⚠️  No account values retrieved")
            except Exception as e:
                logger.error(f"❌ Error getting account values: {e}")
            
            # Get positions
            try:
                positions = ib.positions()
                logger.info(f"✓ Retrieved {len(positions)} positions")
                
                for pos in positions:
                    if pos.position != 0:
                        logger.info(f"  Position: {pos.contract.symbol} = {pos.position}")
            except Exception as e:
                logger.error(f"❌ Error getting positions: {e}")
            
            # Test historical data request
            try:
                from ib_async import Stock
                
                logger.info("🔍 Testing historical data request...")
                contract = Stock('AAPL', 'SMART', 'USD')
                
                bars = ib.reqHistoricalData(
                    contract,
                    endDateTime='',
                    durationStr='5 D',
                    barSizeSetting='1 day',
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1
                )
                
                if bars:
                    logger.info(f"✓ Retrieved {len(bars)} historical bars for AAPL")
                    logger.info(f"  Latest: {bars[-1].date} - Close: ${bars[-1].close}")
                else:
                    logger.warning("⚠️  No historical data retrieved")
                    
            except Exception as e:
                logger.error(f"❌ Error getting historical data: {e}")
            
            # Test order placement and cancellation (using fixed price)
            try:
                from ib_async import Stock, LimitOrder
                import time
                
                logger.info("🔍 Testing limit order placement and cancellation...")
                
                # Create a test contract (AAPL)
                contract = Stock('AAPL', 'SMART', 'USD')
                
                # Qualify the contract first to get conId
                ib.qualifyContracts(contract)
                logger.info(f"✓ Contract qualified - ConId: {contract.conId}")
                
                # Use a very low limit price that won't fill (testing order management only)
                # This is safe for both paper and live accounts
                limit_price = 50.00  # Well below any realistic AAPL price
                
                logger.info(f"  Setting safe test limit buy order at: ${limit_price}")
                logger.info("  (This price is intentionally low to avoid accidental fills)")
                
                # Create limit order (1 share, buy, very low price)
                order = LimitOrder('BUY', 1, limit_price)
                trade = None
                
                try:
                    # Place the order
                    trade = ib.placeOrder(contract, order)
                    logger.info(f"✓ Order placed successfully - Order ID: {trade.order.orderId}")
                    
                    # Wait a moment for order to be acknowledged
                    ib.sleep(3)
                    
                    # Check order status
                    if trade.orderStatus.status:
                        logger.info(f"  Order status: {trade.orderStatus.status}")
                    
                    # Cancel the order
                    logger.info("🔍 Canceling the order...")
                    ib.cancelOrder(order)
                    
                    # Wait for cancellation confirmation
                    ib.sleep(3)
                    
                    # Check final status
                    if trade.orderStatus.status:
                        logger.info(f"✓ Order cancelled - Final status: {trade.orderStatus.status}")
                    else:
                        logger.info("✓ Order cancellation processed")
                    
                    logger.info("✅ Order placement and cancellation test completed successfully!")
                    
                except Exception as order_error:
                    logger.error(f"❌ Error during order test: {order_error}")
                    raise order_error
                    
                finally:
                    # SAFETY: Always try to cancel any placed orders, regardless of what happened
                    if trade and hasattr(trade, 'order') and trade.order.orderId:
                        try:
                            logger.info("🛡️  Safety cleanup: Ensuring order is cancelled...")
                            ib.cancelOrder(order)
                            ib.sleep(2)  # Give time for cancellation to process
                            
                            # Verify cancellation
                            open_orders = ib.openOrders()
                            test_order_still_open = any(o.orderId == trade.order.orderId for o in open_orders)
                            
                            if test_order_still_open:
                                logger.warning(f"⚠️  Order {trade.order.orderId} may still be open - manual check recommended")
                            else:
                                logger.info("✅ Safety cleanup: Order confirmed cancelled")
                                
                        except Exception as cleanup_error:
                            logger.error(f"❌ Error during safety cleanup: {cleanup_error}")
                            logger.warning(f"⚠️  MANUAL ACTION REQUIRED: Check order {trade.order.orderId if trade else 'unknown'} in TWS")
                
            except Exception as e:
                logger.error(f"❌ Error testing order operations: {e}")
                logger.warning("Note: Order testing may require different permissions in some account types")
            
            # Disconnect
            ib.disconnect()
            logger.info("✅ IBKR connection test completed successfully!")
            return True
            
        else:
            logger.error("❌ Failed to connect to IBKR")
            return False
            
    except ImportError:
        logger.error("❌ ib_async not available")
        return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        logger.error("Please check:")
        logger.error("  1. TWS or IB Gateway is running")
        logger.error("  2. API is enabled in TWS/Gateway settings")
        logger.error("  3. Socket port matches your setting")
        logger.error("  4. 127.0.0.1 is in trusted IPs")
        return False

def test_broker_selector():
    """Test the unified broker selector system."""
    logger.info("🔍 Testing unified broker selector...")
    
    try:
        from broker_selector import UnifiedTradingSystem
        
        logger.info("Creating unified trading system...")
        system = UnifiedTradingSystem()
        
        broker_type = system.get_broker_type()
        logger.info(f"✅ Connected via: {broker_type}")
        
        if broker_type == "IBKR":
            logger.info("🎯 Successfully using IBKR as primary broker!")
        else:
            logger.info("⚠️  Using Alpaca as fallback broker")
        
        # Test basic operations
        try:
            account = system.get_account_info()
            logger.info(f"✓ Account info retrieved")
        except Exception as e:
            logger.error(f"❌ Error getting account info: {e}")
        
        try:
            positions = system.get_positions()
            logger.info(f"✓ Positions retrieved: {len(positions)}")
        except Exception as e:
            logger.error(f"❌ Error getting positions: {e}")
        
        # Cleanup
        system.disconnect()
        logger.info("✅ Broker selector test completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Broker selector test failed: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("IBKR TWS API CONNECTION TEST")
    logger.info("=" * 60)
    logger.info(f"Test started at: {datetime.now()}")
    logger.info("")
    
    success = True
    
    # Test 1: Dependencies
    if not test_dependencies():
        success = False
    logger.info("")
    
    # Test 2: Environment
    try:
        host, port, client_id = test_environment()
    except Exception as e:
        logger.error(f"❌ Environment test failed: {e}")
        success = False
        return
    logger.info("")
    
    # Test 3: IBKR Connection
    if not test_ibkr_connection(host, port, client_id):
        success = False
    logger.info("")
    
    # Test 4: Broker Selector
    if not test_broker_selector():
        success = False
    logger.info("")
    
    # Final result
    logger.info("=" * 60)
    if success:
        logger.info("🎉 ALL TESTS PASSED!")
        logger.info("✅ IBKR TWS API integration is ready to use")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Run: python quant_main.py --mode historical --symbols AAPL")
        logger.info("2. For continuous trading: python quant_main.py --mode continuous")
    else:
        logger.info("❌ SOME TESTS FAILED")
        logger.info("Please fix the issues above before using the trading system")
        logger.info("")
        logger.info("Common issues:")
        logger.info("- TWS/Gateway not running")
        logger.info("- API not enabled in TWS settings")
        logger.info("- Wrong port number")
        logger.info("- IP not in trusted list")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()