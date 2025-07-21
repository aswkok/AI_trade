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
        """Get real-time data with Yahoo Finance as PRIMARY source."""
        # Try Yahoo Finance first (PRIMARY for real-time data)
        try:
            logger.info(f"Attempting to get real-time data from Yahoo Finance (PRIMARY) for {symbol}")
            import yfinance as yf
            import pandas as pd
            from datetime import datetime
            
            ticker = yf.Ticker(symbol)
            
            # Get the latest quote information
            quote_info = ticker.info
            history = ticker.history(period="1d", interval="1m", prepost=True)
            
            if not history.empty:
                latest_bar = history.iloc[-1]
                
                # Try to get real-time price from different sources
                current_price = None
                is_extended_hours = False
                
                # Check for post-market price
                if 'postMarketPrice' in quote_info and quote_info['postMarketPrice'] and quote_info['postMarketPrice'] > 0:
                    current_price = float(quote_info['postMarketPrice'])
                    is_extended_hours = True
                    logger.info(f"Using post-market price: ${current_price}")
                # Check for pre-market price
                elif 'preMarketPrice' in quote_info and quote_info['preMarketPrice'] and quote_info['preMarketPrice'] > 0:
                    current_price = float(quote_info['preMarketPrice'])
                    is_extended_hours = True
                    logger.info(f"Using pre-market price: ${current_price}")
                # Check for regular market price
                elif 'regularMarketPrice' in quote_info and quote_info['regularMarketPrice'] and quote_info['regularMarketPrice'] > 0:
                    current_price = float(quote_info['regularMarketPrice'])
                    logger.info(f"Using regular market price: ${current_price}")
                # Fall back to latest close from history
                else:
                    current_price = float(latest_bar['Close'])
                    logger.info(f"Using latest close price: ${current_price}")
                
                # Determine actual session type
                current_hour = datetime.now().hour
                session_type = "regular hours"
                
                if current_hour >= 20 or current_hour < 4:  # 8 PM - 4 AM ET
                    session_type = "overnight"
                elif current_hour >= 16:  # 4 PM - 8 PM ET
                    session_type = "after-hours"
                elif current_hour < 9 or (current_hour == 9 and datetime.now().minute < 30):  # 4 AM - 9:30 AM ET
                    session_type = "pre-market"
                
                # Estimate bid/ask from the current price (typical spread varies by session)
                if session_type == "overnight":
                    spread_pct = 0.003  # Wider spread during overnight (0.3%)
                elif session_type in ["after-hours", "pre-market"]:
                    spread_pct = 0.002  # Moderate spread during extended hours (0.2%)
                else:
                    spread_pct = 0.001  # Normal spread during regular hours (0.1%)
                
                spread = current_price * spread_pct
                bid_price = current_price - (spread / 2)
                ask_price = current_price + (spread / 2)
                
                # Create a DataFrame with the latest data
                latest_data = pd.DataFrame({
                    'timestamp': [datetime.now()],
                    'open': [float(latest_bar['Open'])],
                    'high': [max(float(latest_bar['High']), current_price)],
                    'low': [min(float(latest_bar['Low']), current_price)],
                    'close': [current_price],
                    'volume': [float(latest_bar['Volume'])]
                })
                latest_data.set_index('timestamp', inplace=True)
                
                logger.info(f"Retrieved real-time data from Yahoo Finance (PRIMARY): ${current_price} ({session_type})")
                return latest_data
            else:
                logger.warning(f"No recent history data from Yahoo Finance for {symbol}")
                
        except Exception as e:
            logger.error(f"Yahoo Finance (PRIMARY) real-time data failed for {symbol}: {e}")
        
        # Fall back to broker real-time data if Yahoo Finance fails
        try:
            if not self.current_broker:
                raise ConnectionError("No broker connected")
            logger.info(f"Falling back to {self.broker_type} for real-time data for {symbol}")
            return self.current_broker.get_realtime_data(symbol)
        except Exception as e:
            logger.error(f"Broker ({self.broker_type}) real-time data also failed for {symbol}: {e}")
            return pd.DataFrame()  # Return empty DataFrame if all sources fail
    
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
    
    def _display_trading_summary(self, symbols, signals_data, historical_data):
        """Display a summary table showing recent 10 time periods with current column structure."""
        try:
            from tabulate import tabulate
            from datetime import datetime
            import numpy as np
            import pandas as pd
            
            print("\n" + "=" * 80)
            print(f"🎯 TRADING SUMMARY - {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 80)
            
            # Create summary data for recent 10 time periods
            summary_rows = []
            
            for symbol in symbols:
                try:
                    if symbol not in signals_data or symbol not in historical_data:
                        continue
                    
                    signals = signals_data[symbol]
                    data = historical_data[symbol]
                    
                    if signals.empty or data.empty:
                        continue
                    
                    # Get last 10 periods (or fewer if not available)
                    recent_periods = min(10, len(signals), len(data))
                    
                    # Display most recent periods first (reverse order like integrated_macd_trader)
                    for i in range(recent_periods-1, -1, -1):
                        try:
                            signal_row = signals.iloc[-(i+1)]  # Get from most recent backwards
                            data_row = data.iloc[-(i+1)]
                            
                            # Get timestamp for this period
                            if hasattr(data_row.name, 'strftime'):
                                time_str = data_row.name.strftime('%H:%M:%S')
                            else:
                                # Fallback time display
                                time_str = f"{recent_periods-i:02d}:00"
                            
                            # Extract key information
                            current_price = f"${data_row.get('close', 0):.2f}"
                            action = signal_row.get('action', '')
                            macd_position = signal_row.get('macd_position', 'UNKNOWN')
                            signal_strength = signal_row.get('signal', 0)
                            
                            # Format action with indicators
                            action_display = ''
                            if action == 'BUY':
                                action_display = '↑ BUY'
                            elif action == 'SELL' or action == 'SHORT':
                                action_display = '↓ SELL'
                            elif action == 'COVER_AND_BUY':
                                action_display = '🔄 COVER→BUY'
                            elif action == 'SELL_AND_SHORT':
                                action_display = '🔄 SELL→SHORT'
                            else:
                                action_display = '➡ HOLD'
                            
                            # MACD values if available (check both column naming conventions)
                            macd_val = signal_row.get('MACD', np.nan)
                            signal_val = signal_row.get('Signal', signal_row.get('MACD_signal', np.nan))
                            
                            # Calculate histogram if we have both MACD and Signal values
                            if not pd.isna(macd_val) and not pd.isna(signal_val):
                                histogram = macd_val - signal_val
                            else:
                                histogram = signal_row.get('MACD_histogram', np.nan)
                            
                            # Format MACD values - only check for NaN, zero is a valid value
                            macd_str = f"{macd_val:.6f}" if not pd.isna(macd_val) else "N/A"
                            signal_str = f"{signal_val:.6f}" if not pd.isna(signal_val) else "N/A"
                            histogram_str = f"{histogram:.6f}" if not pd.isna(histogram) else "N/A"
                            
                            # Add time column and keep existing structure
                            summary_rows.append([
                                time_str,  # Time instead of symbol for recent periods
                                symbol,
                                current_price,
                                macd_str,
                                signal_str, 
                                histogram_str,
                                macd_position,
                                action_display,
                                f"{signal_strength:.2f}" if signal_strength != 0 else "0.00"
                            ])
                            
                        except Exception as e:
                            logger.warning(f"Error processing period {i} for {symbol}: {e}")
                            continue
                    
                except Exception as e:
                    logger.warning(f"Error creating summary for {symbol}: {e}")
                    continue
            
            if summary_rows:
                headers = ['Time', 'Symbol', 'Price', 'MACD', 'Signal', 'Histogram', 'Position', 'Action', 'Strength']
                print(tabulate(
                    summary_rows,
                    headers=headers,
                    tablefmt='pretty',
                    showindex=False
                ))
            else:
                print("📊 No trading data available for display")
            
            # Show broker and connection status
            print(f"\n🔗 Broker: {self.broker_type}")
            print(f"📡 Data Source: Yahoo Finance (PRIMARY)")
            print(f"⏰ Next update in {1} minute(s)")
            print("=" * 80 + "\n")
            
        except ImportError:
            # Fallback if tabulate is not available
            print(f"\n📊 TRADING SUMMARY - {datetime.now().strftime('%H:%M:%S')}")
            print(f"🔗 Broker: {self.broker_type} | 📡 Data: Yahoo Finance (PRIMARY)")
            for symbol in symbols:
                if symbol in signals_data and not signals_data[symbol].empty:
                    latest_signal = signals_data[symbol].iloc[-1]
                    action = latest_signal.get('action', 'HOLD')
                    print(f"  {symbol}: {action}")
            print("-" * 50 + "\n")
        except Exception as e:
            logger.error(f"Error displaying trading summary: {e}")

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
        import pandas as pd
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
        
        # Initialize strategies and data storage
        strategy_instances = {}
        historical_data = {}
        signals_data = {}
        quotes_history = {}  # Store recent quotes for display
        
        for symbol in symbols:
            try:
                # Get historical data - use minute bars for continuous trading
                data = self.get_historical_data(symbol, timeframe='Minute', limit=250)
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
                        
                        # Note: During overnight hours (8 PM - 4 AM), most stocks have no real market activity
                        # Yahoo Finance will return the last known prices from market close
                        # This is expected behavior - the price should remain static until pre-market opens
                        
                        # Update historical data
                        updated_data = pd.concat([historical_data[symbol], realtime_data])
                        updated_data = updated_data.iloc[-250:]  # Keep last 250 bars
                        historical_data[symbol] = updated_data
                        
                        # Generate signals
                        signals = strategy.generate_signals(updated_data)
                        
                        if not signals.empty:
                            # Store signals for display
                            signals_data[symbol] = signals
                            
                            latest_signal = signals.iloc[-1]
                            action = latest_signal.get('action', '')
                            
                            if action:
                                self._execute_ibkr_signal(symbol, latest_signal, strategy)
                        
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                
                # Display trading summary table (similar to integrated_macd_trader)
                if signals_data:
                    self._display_trading_summary(symbols, signals_data, historical_data)
                else:
                    print(f"\n⏳ Collecting data... {len(symbols)} symbol(s) being monitored")
                    print(f"🔗 Broker: {self.broker_type} | 📡 Data Source: Yahoo Finance (PRIMARY)")
                    print(f"⏰ Next update in {interval} minute(s)\n")
                
                # Wait for next interval
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