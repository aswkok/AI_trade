#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Broker Switching Demo

This script demonstrates the manual broker switching functionality.
Shows how to switch between IBKR (primary) and Alpaca (fallback).
"""

import logging
from broker_selector import UnifiedTradingSystem

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Demo the broker switching functionality."""
    
    print("🚀 BROKER SWITCHING DEMO")
    print("=" * 50)
    
    try:
        # Initialize unified trading system (auto mode - IBKR primary)
        print("\n1️⃣ Initializing Unified Trading System...")
        system = UnifiedTradingSystem()
        
        # Show current status
        status = system.get_status()
        print(f"\n📊 Current Status:")
        print(f"   Connected to: {status['current_broker']}")
        print(f"   Available brokers: {status['available_brokers']}")
        print(f"   Force broker setting: {status['force_broker']}")
        
        # Show account info
        print(f"\n💰 Account Information ({status['current_broker']}):")
        try:
            account = system.get_account_info()
            print(f"   Portfolio Value: ${account.get('portfolio_value', 0):,.2f}")
            print(f"   Buying Power: ${account.get('buying_power', 0):,.2f}")
        except Exception as e:
            print(f"   Error getting account info: {e}")
        
        # Test manual switching if multiple brokers available
        if len(status['available_brokers']) > 1:
            print(f"\n🔄 Testing Manual Broker Switching...")
            
            current = system.get_broker_type()
            target = 'ALPACA' if current == 'IBKR' else 'IBKR'
            
            print(f"   Switching from {current} to {target}...")
            
            if system.switch_to_broker(target):
                print(f"   ✅ Successfully switched to {target}")
                
                # Show new account info
                try:
                    account = system.get_account_info()
                    print(f"   New broker portfolio: ${account.get('portfolio_value', 0):,.2f}")
                except Exception as e:
                    print(f"   Error getting new account info: {e}")
                
                # Switch back
                print(f"\n🔄 Switching back to {current}...")
                if system.switch_to_broker(current):
                    print(f"   ✅ Successfully switched back to {current}")
                else:
                    print(f"   ❌ Failed to switch back to {current}")
            else:
                print(f"   ❌ Failed to switch to {target}")
        else:
            print(f"\n⚠️  Only one broker available: {status['available_brokers']}")
            print("   Cannot demonstrate switching")
        
        # Test forced broker modes
        print(f"\n🎯 Testing Forced Broker Modes...")
        
        # Test force IBKR
        try:
            print("   Testing FORCE_BROKER=IBKR...")
            ibkr_system = UnifiedTradingSystem(force_broker="IBKR")
            print(f"   ✅ Forced IBKR: {ibkr_system.get_broker_type()}")
            ibkr_system.disconnect()
        except Exception as e:
            print(f"   ❌ Force IBKR failed: {e}")
        
        # Test force Alpaca
        try:
            print("   Testing FORCE_BROKER=ALPACA...")
            alpaca_system = UnifiedTradingSystem(force_broker="ALPACA")
            print(f"   ✅ Forced Alpaca: {alpaca_system.get_broker_type()}")
            alpaca_system.disconnect()
        except Exception as e:
            print(f"   ❌ Force Alpaca failed: {e}")
        
        # Interactive demo
        print(f"\n🎮 Interactive Demo:")
        print("   Type 'switch' to manually switch brokers")
        print("   Type 'status' to show current status")
        print("   Type 'quit' to exit")
        
        while True:
            try:
                command = input(f"\n[{system.get_broker_type()}] Enter command: ").strip().lower()
                
                if command == 'quit':
                    break
                elif command == 'switch':
                    system.interactive_switch()
                elif command == 'status':
                    status = system.get_status()
                    print(f"   Current: {status['current_broker']}")
                    print(f"   Available: {status['available_brokers']}")
                elif command == '':
                    continue
                else:
                    print("   Commands: switch, status, quit")
                    
            except KeyboardInterrupt:
                print("\n\n   Ctrl+C pressed. Type 'quit' to exit or 'switch' to change brokers.")
                continue
        
        print(f"\n✅ Demo completed!")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logger.error(f"Demo error: {e}")
        
    finally:
        try:
            if 'system' in locals():
                system.disconnect()
                print("🔌 Disconnected from brokers")
        except:
            pass

if __name__ == "__main__":
    main()