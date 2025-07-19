#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Broker Selector System

This module automatically selects the appropriate broker:
1. Primary: IBKR TWS API (if available and connected)
2. Fallback: Alpaca API (if IBKR fails or unavailable)

The selector provides a unified interface that existing strategies can use
without modification.
"""

import os
import logging
from typing import Optional, Any
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

class BrokerSelector:
    """
    Unified broker interface that automatically selects between IBKR and Alpaca.
    IBKR is the primary broker, Alpaca is the fallback.
    Can also manually switch between brokers.
    """
    
    def __init__(self, force_broker=None):
        """
        Initialize broker selector.
        
        Args:
            force_broker: Force specific broker ("IBKR", "ALPACA", or None for auto)
        """
        self.current_broker = None
        self.broker_type = None
        self.trading_client = None
        self.data_client = None
        self.force_broker = force_broker or os.getenv("FORCE_BROKER", "AUTO").upper()
        
        # Initialize brokers based on preference
        self._initialize_brokers()
    
    def _initialize_brokers(self):
        """Initialize brokers based on preference: IBKR default, manual override possible."""
        
        if self.force_broker == "IBKR":
            logger.info("🎯 FORCING IBKR (per configuration)")
            if not self._try_ibkr():
                raise ConnectionError("Could not connect to IBKR (forced mode)")
        elif self.force_broker == "ALPACA":
            logger.info("🎯 FORCING ALPACA (per configuration)")
            if not self._try_alpaca():
                raise ConnectionError("Could not connect to Alpaca (forced mode)")
        else:
            logger.info("🔄 AUTO MODE: IBKR primary, Alpaca fallback")
            # Try IBKR first (DEFAULT/PRIMARY)
            if not self._try_ibkr():
                logger.warning("IBKR unavailable, trying Alpaca fallback...")
                if not self._try_alpaca():
                    logger.error("❌ No broker connection available!")
                    raise ConnectionError("Could not connect to any broker (IBKR or Alpaca)")

    def _try_ibkr(self):
        """Try to connect to IBKR."""
        try:
            from ibkr_trading_system import IBKRTradingSystem, IBKRTradingClient
            
            logger.info("Attempting to connect to IBKR TWS API...")
            ibkr_system = IBKRTradingSystem()
            
            if ibkr_system.connect():
                self.current_broker = ibkr_system
                self.broker_type = "IBKR"
                self.trading_client = IBKRTradingClient(ibkr_system)
                self.data_client = ibkr_system
                logger.info("✅ Successfully connected to IBKR TWS API")
                return True
            else:
                logger.warning("Failed to connect to IBKR TWS API")
                return False
                
        except ImportError:
            logger.warning("IBKR dependencies not available (install ib_async)")
            return False
        except Exception as e:
            logger.warning(f"IBKR connection failed: {e}")
            return False

    def _try_alpaca(self):
        """Try to connect to Alpaca."""
        try:
            import sys
            import importlib.util
            
            # Import main.py as a module to get AlpacaTradingSystem
            main_path = os.path.join(os.path.dirname(__file__), 'quant_main.py')
            spec = importlib.util.spec_from_file_location("main", main_path)
            main_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(main_module)
            
            logger.info("Attempting to connect to Alpaca API...")
            alpaca_system = main_module.AlpacaTradingSystem()
            
            # Test connection
            account = alpaca_system.get_account_info()
            if account:
                self.current_broker = alpaca_system
                self.broker_type = "ALPACA"
                self.trading_client = alpaca_system.trading_client
                self.data_client = alpaca_system.data_client
                logger.info("✅ Successfully connected to Alpaca API")
                return True
            else:
                logger.error("Failed to connect to Alpaca API")
                return False
                
        except Exception as e:
            logger.error(f"Alpaca connection failed: {e}")
            return False
    
    def get_broker_type(self) -> str:
        """Get current broker type."""
        return self.broker_type
    
    def is_connected(self) -> bool:
        """Check if connected to any broker."""
        return self.current_broker is not None
    
    def reconnect(self):
        """Attempt to reconnect, preferring IBKR."""
        logger.info("Attempting to reconnect to brokers...")
        self.current_broker = None
        self.broker_type = None
        self.trading_client = None
        self.data_client = None
        self._initialize_brokers()
    
    def switch_to_broker(self, broker_type):
        """
        Manually switch to a specific broker.
        
        Args:
            broker_type: "IBKR" or "ALPACA"
            
        Returns:
            bool: True if switch successful, False otherwise
        """
        broker_type = broker_type.upper()
        
        if broker_type == self.broker_type:
            logger.info(f"Already using {broker_type}")
            return True
        
        logger.info(f"🔄 Switching from {self.broker_type} to {broker_type}...")
        
        # Disconnect current broker
        if self.current_broker:
            try:
                self.current_broker.disconnect()
            except:
                pass
            self.current_broker = None
            self.broker_type = None
            self.trading_client = None
            self.data_client = None
        
        # Connect to requested broker
        if broker_type == "IBKR":
            if self._try_ibkr():
                logger.info("✅ Successfully switched to IBKR")
                return True
        elif broker_type == "ALPACA":
            if self._try_alpaca():
                logger.info("✅ Successfully switched to Alpaca")
                return True
        
        logger.error(f"❌ Failed to switch to {broker_type}")
        return False
    
    def get_available_brokers(self):
        """
        Test and return list of available brokers.
        
        Returns:
            list: Available broker names
        """
        available = []
        
        # Test IBKR availability
        try:
            from ibkr_trading_system import IBKRTradingSystem
            test_ibkr = IBKRTradingSystem()
            if test_ibkr.connect():
                available.append("IBKR")
                test_ibkr.disconnect()
        except:
            pass
        
        # Test Alpaca availability  
        try:
            import sys
            import importlib.util
            
            main_path = os.path.join(os.path.dirname(__file__), 'quant_main.py')
            spec = importlib.util.spec_from_file_location("main", main_path)
            main_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(main_module)
            
            test_alpaca = main_module.AlpacaTradingSystem()
            if test_alpaca.get_account_info():
                available.append("ALPACA")
        except:
            pass
        
        return available
    
    def get_status(self):
        """
        Get current broker status.
        
        Returns:
            dict: Status information
        """
        return {
            "current_broker": self.broker_type,
            "is_connected": self.is_connected(),
            "force_broker": self.force_broker,
            "available_brokers": self.get_available_brokers()
        }
    
    # Unified interface methods that delegate to the current broker
    
    def get_account_info(self):
        """Get account information."""
        if not self.current_broker:
            raise ConnectionError("No broker connected")
        return self.current_broker.get_account_info()
    
    def get_all_positions(self):
        """Get all positions."""
        if not self.current_broker:
            raise ConnectionError("No broker connected")
        return self.current_broker.get_all_positions()
    
    def get_positions(self):
        """Alias for get_all_positions."""
        return self.get_all_positions()
    
    def get_historical_data(self, symbol, timeframe=None, limit=250):
        """Get historical data."""
        if not self.current_broker:
            raise ConnectionError("No broker connected")
        return self.current_broker.get_historical_data(symbol, timeframe, limit)
    
    def get_realtime_data(self, symbol):
        """Get real-time data."""
        if not self.current_broker:
            raise ConnectionError("No broker connected")
        return self.current_broker.get_realtime_data(symbol)
    
    def place_market_order(self, symbol, qty, side, extended_hours=None):
        """Place market order."""
        if not self.current_broker:
            raise ConnectionError("No broker connected")
        
        logger.info(f"Placing market order via {self.broker_type}: {side} {qty} {symbol}")
        return self.current_broker.place_market_order(symbol, qty, side, extended_hours)
    
    def get_clock(self):
        """Get market clock."""
        if not self.current_broker:
            raise ConnectionError("No broker connected")
        return self.current_broker.get_clock()
    
    def save_strategy_state(self, symbol, strategy_name, state_data):
        """Save strategy state."""
        if not self.current_broker:
            raise ConnectionError("No broker connected")
        return self.current_broker.save_strategy_state(symbol, strategy_name, state_data)
    
    def get_strategy_state(self, symbol, strategy_name):
        """Get strategy state."""
        if not self.current_broker:
            raise ConnectionError("No broker connected")
        return self.current_broker.get_strategy_state(symbol, strategy_name)
    
    def is_paper_trading(self):
        """Check if paper trading."""
        if not self.current_broker:
            raise ConnectionError("No broker connected")
        return self.current_broker.is_paper_trading()
    
    def disconnect(self):
        """Disconnect from current broker."""
        if self.current_broker:
            logger.info(f"Disconnecting from {self.broker_type}")
            self.current_broker.disconnect()
            self.current_broker = None
            self.broker_type = None
            self.trading_client = None
            self.data_client = None


class UnifiedTradingSystem(BrokerSelector):
    """
    Unified trading system that replaces AlpacaTradingSystem.
    This provides complete backward compatibility while using IBKR as primary.
    """
    
    def __init__(self, force_broker=None):
        """Initialize unified trading system."""
        super().__init__(force_broker)
        
        # Set attributes for compatibility with existing code
        self.extended_hours = os.getenv("EXTENDED_HOURS", "True").lower() == "true"
        self.overnight_trading = os.getenv("OVERNIGHT_TRADING", "True").lower() == "true"
        self.risk_per_trade = float(os.getenv("RISK_PER_TRADE", "0.02"))
        self.max_positions = int(os.getenv("MAX_POSITIONS", "5"))
        
        logger.info(f"Unified Trading System initialized with {self.broker_type}")
        logger.info(f"Extended hours: {self.extended_hours}, Overnight: {self.overnight_trading}")
    
    def run_continuous_strategy(self, symbols, strategy_name="macd", interval=1, **strategy_params):
        """Run continuous strategy (delegates to current broker)."""
        if self.broker_type == "ALPACA":
            # Use existing Alpaca implementation
            return self.current_broker.run_continuous_strategy(
                symbols, strategy_name, interval, **strategy_params
            )
        else:
            # Implement IBKR continuous strategy
            return self._run_ibkr_continuous_strategy(
                symbols, strategy_name, interval, **strategy_params
            )
    
    def _run_ibkr_continuous_strategy(self, symbols, strategy_name, interval, **strategy_params):
        """Run continuous strategy with IBKR."""
        import time
        import signal
        import sys
        from datetime import datetime
        from strategies import StrategyFactory
        
        logger.info(f"Running continuous IBKR strategy: {strategy_name}")
        logger.info(f"Symbols: {symbols}, Interval: {interval} minutes")
        
        # Signal handler for graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutting down IBKR continuous strategy...")
            self.disconnect()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # Initialize strategies
        strategy_instances = {}
        historical_data = {}
        
        for symbol in symbols:
            try:
                # Get historical data
                data = self.get_historical_data(symbol, limit=250)
                if data.empty:
                    logger.error(f"No historical data for {symbol}")
                    continue
                
                # Create strategy
                strategy = StrategyFactory.get_strategy(strategy_name, **strategy_params)
                strategy_instances[symbol] = strategy
                historical_data[symbol] = data
                
                logger.info(f"Initialized {strategy.name} for {symbol}")
                
            except Exception as e:
                logger.error(f"Error initializing strategy for {symbol}: {e}")
        
        if not strategy_instances:
            logger.error("No valid symbols to trade")
            return
        
        # Main continuous loop
        logger.info("Starting continuous strategy execution...")
        
        while True:
            try:
                logger.info(f"Running strategy at {datetime.now()}")
                
                # Check market status
                clock = self.get_clock()
                if not clock.is_open and not self.extended_hours:
                    logger.info("Market closed and extended hours disabled")
                    time.sleep(interval * 60)
                    continue
                
                # Process each symbol
                for symbol in symbols:
                    if symbol not in strategy_instances:
                        continue
                    
                    try:
                        strategy = strategy_instances[symbol]
                        
                        # Get latest real-time data
                        realtime_data = self.get_realtime_data(symbol)
                        if realtime_data.empty:
                            logger.warning(f"No real-time data for {symbol}")
                            continue
                        
                        # Update historical data
                        updated_data = pd.concat([historical_data[symbol], realtime_data])
                        updated_data = updated_data.iloc[-250:]  # Keep last 250 bars
                        historical_data[symbol] = updated_data
                        
                        # Generate signals
                        signals = strategy.generate_signals(updated_data)
                        
                        if not signals.empty:
                            latest_signal = signals.iloc[-1]
                            action = latest_signal.get('action', '')
                            
                            if action:
                                self._execute_ibkr_signal(symbol, latest_signal, strategy)
                        
                        logger.info(f"Processed {symbol}")
                        
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                
                # Wait for next interval
                logger.info(f"Waiting {interval} minutes for next execution...")
                time.sleep(interval * 60)
                
            except KeyboardInterrupt:
                logger.info("Strategy stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in continuous strategy: {e}")
                time.sleep(interval * 60)
    
    def _execute_ibkr_signal(self, symbol, signal, strategy):
        """Execute trading signal with IBKR."""
        action = signal.get('action', '')
        shares = signal.get('shares', 100)
        
        if not action:
            return
        
        try:
            # Import OrderSide for compatibility
            from alpaca.trading.enums import OrderSide
            
            if action == 'BUY':
                self.place_market_order(symbol, shares, OrderSide.BUY)
            elif action == 'SHORT':
                self.place_market_order(symbol, shares, OrderSide.SELL)
            elif action == 'COVER_AND_BUY':
                # Cover short first, then buy
                positions = self.get_all_positions()
                current_pos = next((p for p in positions if p.symbol == symbol), None)
                if current_pos and current_pos.side == 'short':
                    cover_qty = int(current_pos.qty)
                    self.place_market_order(symbol, cover_qty, OrderSide.BUY)
                    time.sleep(2)
                self.place_market_order(symbol, shares, OrderSide.BUY)
            elif action == 'SELL_AND_SHORT':
                # Sell long first, then short
                positions = self.get_all_positions()
                current_pos = next((p for p in positions if p.symbol == symbol), None)
                if current_pos and current_pos.side == 'long':
                    sell_qty = int(current_pos.qty)
                    self.place_market_order(symbol, sell_qty, OrderSide.SELL)
                    time.sleep(2)
                self.place_market_order(symbol, shares, OrderSide.SELL)
            
            # Save strategy state
            self.save_strategy_state(symbol, strategy.name, {
                'last_action': action,
                'shares': shares,
                'last_signal_time': datetime.now().isoformat()
            })
            
            logger.info(f"Executed {action} for {symbol}: {shares} shares")
            
        except Exception as e:
            logger.error(f"Error executing signal for {symbol}: {e}")
    
    def run_with_realtime_data(self, symbols, strategy_name="macd", **strategy_params):
        """Run with real-time data (delegates to current broker)."""
        if self.broker_type == "ALPACA":
            return self.current_broker.run_with_realtime_data(symbols, strategy_name, **strategy_params)
        else:
            # Simple IBKR real-time implementation
            logger.info(f"Running IBKR real-time strategy for {symbols}")
            for symbol in symbols:
                try:
                    data = self.get_historical_data(symbol)
                    realtime = self.get_realtime_data(symbol)
                    # Process and execute strategies...
                    logger.info(f"Processed real-time data for {symbol}")
                except Exception as e:
                    logger.error(f"Error with real-time data for {symbol}: {e}")
    
    def interactive_switch(self):
        """Interactive broker switching with user prompt."""
        available = self.get_available_brokers()
        
        print(f"\n📊 Current broker: {self.broker_type}")
        print(f"📋 Available brokers: {available}")
        
        if len(available) > 1:
            target = 'ALPACA' if self.broker_type == 'IBKR' else 'IBKR'
            choice = input(f"\n🔄 Switch to {target}? (y/n): ")
            if choice.lower() in ['y', 'yes']:
                print(f"🔄 Switching to {target}...")
                if self.switch_to_broker(target):
                    print(f"✅ Successfully switched to {target}")
                    return True
                else:
                    print(f"❌ Failed to switch to {target}")
                    return False
        else:
            print("ℹ️  Only one broker available")
            return False
    
    def run(self, symbols=None, strategy_name="macd", **strategy_params):
        """Run trading system (delegates to current broker)."""
        if symbols is None:
            symbols = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META']
        
        logger.info(f"Running {self.broker_type} trading system")
        logger.info(f"Symbols: {symbols}, Strategy: {strategy_name}")
        
        # Display account info
        self.get_account_info()
        self.get_positions()
        
        # Run strategies
        if self.broker_type == "ALPACA":
            # Use existing Alpaca run method
            for symbol in symbols:
                self.current_broker.run_strategy(symbol, strategy_name, **strategy_params)
        else:
            # IBKR implementation
            from strategies import StrategyFactory
            
            for symbol in symbols:
                try:
                    data = self.get_historical_data(symbol)
                    if data.empty:
                        continue
                    
                    strategy = StrategyFactory.get_strategy(strategy_name, **strategy_params)
                    signals = strategy.generate_signals(data)
                    
                    if not signals.empty:
                        latest_signal = signals.iloc[-1]
                        self._execute_ibkr_signal(symbol, latest_signal, strategy)
                        
                except Exception as e:
                    logger.error(f"Error running strategy for {symbol}: {e}")


# Create global instance for easy import
trading_system = None

def get_trading_system():
    """Get or create the unified trading system instance."""
    global trading_system
    if trading_system is None:
        trading_system = UnifiedTradingSystem()
    return trading_system


if __name__ == "__main__":
    # Test broker selection
    try:
        system = UnifiedTradingSystem()
        print(f"Connected to: {system.get_broker_type()}")
        
        # Test basic operations
        account = system.get_account_info()
        print(f"Account: {account}")
        
        positions = system.get_positions()
        print(f"Positions: {len(positions)}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'system' in locals():
            system.disconnect()