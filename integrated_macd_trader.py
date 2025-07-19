#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Integrated MACD Trading System

This script integrates real-time quote monitoring with MACD-based trading decisions
and executes trades on Alpaca. It forms a continuous workflow from live data feeds
to strategy calculation to order execution.
"""

import os
import time
import logging
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from alpaca.trading.enums import OrderSide, TimeInForce

# Import our components
from quote_monitor_selector import QuoteMonitor  # This will import from either Alpaca or Yahoo Finance
from strategies import MACDStrategy, StrategyFactory
from main import AlpacaTradingSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("integrated_trading.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IntegratedMACDTrader:
    """
    Integrated trading system that connects real-time quote data to MACD strategy and Alpaca execution.
    """
    
    def __init__(self, symbol, interval_seconds=60, fast_window=13, slow_window=21, signal_window=9, 
                 shares_per_trade=100, extended_hours=True, warmup_period_minutes=60):
        """
        Initialize the integrated trading system.
        
        Args:
            symbol: Stock symbol to trade
            interval_seconds: Update interval in seconds
            fast_window: Fast EMA window for MACD
            slow_window: Slow EMA window for MACD
            signal_window: Signal line window for MACD
            shares_per_trade: Number of shares per trade
            extended_hours: Whether to trade during extended hours
            warmup_period_minutes: Warm-up period in minutes before trading begins
        """
        # Load environment variables
        load_dotenv(override=True)
        
        # Store configuration
        self.symbol = symbol
        self.interval_seconds = interval_seconds
        self.shares_per_trade = shares_per_trade
        self.extended_hours = extended_hours
        self.warmup_period_minutes = warmup_period_minutes
        
        # Store MACD parameters
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        
        # Initialize components
        logger.info(f"Initializing integrated trading system for {symbol}")
        
        # 1. Initialize the Quote Monitor (either Alpaca or Yahoo Finance based on environment variable)
        self.quote_monitor = QuoteMonitor(
            symbol=symbol,
            max_records=max(slow_window * 3, 500),  # Keep enough records for good MACD calculation
            interval_seconds=interval_seconds,
            fast_window=fast_window,
            slow_window=slow_window,
            signal_window=signal_window
        )
        
        # 2. Initialize the MACD Strategy
        strategy_params = {
            'fast_window': fast_window,
            'slow_window': slow_window,
            'signal_window': signal_window,
            'shares_per_trade': shares_per_trade
        }
        self.strategy = StrategyFactory.get_strategy('macd', **strategy_params)
        
        # Set the quote monitor for the strategy
        self.strategy.set_quote_monitor(self.quote_monitor)
        
        # 3. Initialize the Alpaca Trading System
        self.trading_system = AlpacaTradingSystem()
        
        # Set trading parameters
        self.trading_system.extended_hours = extended_hours
        
        # System state
        self.is_running = False
        self.start_time = None
        self.last_trade_time = None
        self.position_type = "NONE"  # NONE, LONG, SHORT
        self.position_shares = 0
        
        logger.info(f"Integrated trading system initialized for {symbol}")
        logger.info(f"MACD Parameters: Fast={fast_window}, Slow={slow_window}, Signal={signal_window}")
        logger.info(f"Shares per trade: {shares_per_trade}")
        logger.info(f"Extended hours trading: {extended_hours}")
        logger.info(f"Warm-up period: {warmup_period_minutes} minutes")
    
    def is_warmup_complete(self):
        """Check if the warm-up period is complete."""
        if not self.start_time:
            return False
            
        elapsed_minutes = (datetime.now() - self.start_time).total_seconds() / 60
        return elapsed_minutes >= self.warmup_period_minutes
    
    def update_quotes(self):
        """
        Check if we have new quote data from the WebSocket stream.
        With WebSockets, quotes are automatically added to the dataframe
        as they arrive, so we just need to check if we have data.
        """
        # WebSocket already adds quotes to dataframe automatically
        # Just check if we have any quotes
        if not self.quote_monitor.quotes_df.empty:
            return True
        return False
    
    def get_current_position(self):
        """Get the current position from Alpaca."""
        try:
            positions = self.trading_system.trading_client.get_all_positions()
            current_position = next((p for p in positions if p.symbol == self.symbol), None)
            
            if current_position:
                qty = float(current_position.qty)
                side = current_position.side
                
                # Convert to our format
                if side == 'long':
                    self.position_type = 'LONG'
                    self.position_shares = qty
                elif side == 'short':
                    self.position_type = 'SHORT'
                    self.position_shares = -qty
                
                logger.info(f"Current position for {self.symbol}: {abs(qty)} shares, Side: {side}")
                return qty, side
            else:
                self.position_type = 'NONE'
                self.position_shares = 0
                logger.info(f"No current position for {self.symbol}")
                return 0, 'none'
        except Exception as e:
            logger.error(f"Error getting current position: {e}")
            return 0, 'none'
    
    def process_macd_signal(self):
        """
        Process the latest MACD signal and execute trades if necessary.
        
        Returns:
            bool: True if a trade was executed, False otherwise
        """
        # Get the latest MACD signal directly from the quote monitor
        macd_signal = self.quote_monitor.get_macd_signal()
        
        # If we don't have a valid signal yet, do nothing
        if macd_signal['macd_position'] is None:
            logger.info("Not enough data for MACD calculation yet")
            return False
        
        # Get the current position from Alpaca
        current_qty, current_side = self.get_current_position()
        
        # Extract signal information
        signal = macd_signal['signal']
        macd_position = macd_signal['macd_position']
        crossover = macd_signal['crossover']
        crossunder = macd_signal['crossunder']
        
        # Initialize action
        action = None
        qty = 0
        
        # No position yet
        if current_side == 'none':
            if macd_position == "ABOVE":
                # Initial buy
                action = "BUY"
                qty = self.shares_per_trade
                logger.info(f"No current position for {self.symbol} and MACD is ABOVE - taking initial BUY action")
            elif macd_position == "BELOW":
                # Initial short
                action = "SHORT"
                qty = self.shares_per_trade
                logger.info(f"No current position for {self.symbol} and MACD is BELOW - taking initial SHORT action")
        
        # Currently long
        elif current_side == 'long':
            if crossunder:
                # MACD crossed below signal line - sell and short
                action = "SELL_AND_SHORT"
                qty = current_qty + self.shares_per_trade  # Sell current position + short additional shares
                logger.info(f"MACD crossed BELOW signal line while LONG - selling position and shorting")
            elif macd_position == "BELOW" and self.last_trade_time:
                # Only act on position mismatch if we've already made at least one trade
                # MACD is below signal line but no recent crossunder - sell and short
                elapsed_minutes = 0
                if self.last_trade_time:
                    elapsed_minutes = (datetime.now() - self.last_trade_time).total_seconds() / 60
                
                # Only make this transition if it's been at least 15 minutes since last trade
                # to avoid over-trading during choppy markets
                if elapsed_minutes > 15:
                    action = "SELL_AND_SHORT"
                    qty = current_qty + self.shares_per_trade
                    logger.info(f"MACD is BELOW signal line while LONG - selling position and shorting")
        
        # Currently short
        elif current_side == 'short':
            if crossover:
                # MACD crossed above signal line - cover and buy
                action = "COVER_AND_BUY"
                qty = abs(current_qty) + self.shares_per_trade  # Cover short position + buy additional shares
                logger.info(f"MACD crossed ABOVE signal line while SHORT - covering position and buying")
            elif macd_position == "ABOVE" and self.last_trade_time:
                # Only act on position mismatch if we've already made at least one trade
                # MACD is above signal line but no recent crossover - cover and buy
                elapsed_minutes = 0
                if self.last_trade_time:
                    elapsed_minutes = (datetime.now() - self.last_trade_time).total_seconds() / 60
                
                # Only make this transition if it's been at least 15 minutes since last trade
                if elapsed_minutes > 15:
                    action = "COVER_AND_BUY"
                    qty = abs(current_qty) + self.shares_per_trade
                    logger.info(f"MACD is ABOVE signal line while SHORT - covering position and buying")
        
        # Execute the trade if we have an action and warm-up is complete
        if action and qty > 0 and self.is_warmup_complete():
            logger.info(f"Executing trade: {action} {qty} shares of {self.symbol}")
            
            # Import OrderSide from alpaca.trading.enums to avoid the attribute error
            from alpaca.trading.enums import OrderSide
            
            if action == "BUY":
                # Simple buy
                order_id = self.trading_system.place_market_order(
                    self.symbol, qty, OrderSide.BUY, 
                    extended_hours=self.extended_hours
                )
                
            elif action == "SHORT":
                # Simple short
                order_id = self.trading_system.place_market_order(
                    self.symbol, qty, OrderSide.SELL, 
                    extended_hours=self.extended_hours
                )
                
            elif action == "COVER_AND_BUY":
                # Cover short and buy long
                # First, cover the short position
                cover_qty = abs(current_qty)
                if cover_qty > 0:
                    cover_order_id = self.trading_system.place_market_order(
                        self.symbol, cover_qty, OrderSide.BUY,
                        extended_hours=self.extended_hours
                    )
                    logger.info(f"Covered {cover_qty} shares of {self.symbol}")
                    
                    # Wait for the cover order to complete
                    time.sleep(2)
                
                # Then buy additional shares
                buy_order_id = self.trading_system.place_market_order(
                    self.symbol, self.shares_per_trade, OrderSide.BUY,
                    extended_hours=self.extended_hours
                )
                
            elif action == "SELL_AND_SHORT":
                # Sell long and short
                # First, sell the long position
                if current_qty > 0:
                    sell_order_id = self.trading_system.place_market_order(
                        self.symbol, current_qty, OrderSide.SELL,
                        extended_hours=self.extended_hours
                    )
                    logger.info(f"Sold {current_qty} shares of {self.symbol}")
                    
                    # Wait for the sell order to complete
                    time.sleep(2)
                
                # Then short additional shares
                short_order_id = self.trading_system.place_market_order(
                    self.symbol, self.shares_per_trade, OrderSide.SELL,
                    extended_hours=self.extended_hours
                )
            
            # Update the last trade time
            self.last_trade_time = datetime.now()
            
            # Update trade state
            self.trading_system.save_strategy_state(self.symbol, self.strategy.name, {
                'position_type': 'LONG' if action in ["BUY", "COVER_AND_BUY"] else 'SHORT',
                'shares': qty if action in ["BUY", "COVER_AND_BUY"] else -qty,
                'last_action': action,
                'last_signal_time': datetime.now().isoformat()
            })
            
            return True
            
        elif action and qty > 0 and not self.is_warmup_complete():
            logger.info(f"Warm-up period not complete - skipping trade: {action} {qty} shares of {self.symbol}")
            
        return False
    
    def run(self):
        """Run the integrated trading system."""
        logger.info(f"Starting integrated MACD trading system for {self.symbol}")
        logger.info(f"Warm-up period: {self.warmup_period_minutes} minutes")
        logger.info(f"Press Ctrl+C to stop trading")
        
        self.is_running = True
        self.start_time = datetime.now()
        
        try:
            while self.is_running:
                # Update the quote data
                self.update_quotes()
                
                # Display the current status
                if len(self.quote_monitor.quotes_df) > 0:
                    self.quote_monitor.display_quotes()
                    
                    # Log warmup status
                    if not self.is_warmup_complete():
                        elapsed_minutes = (datetime.now() - self.start_time).total_seconds() / 60
                        remaining_minutes = max(0, self.warmup_period_minutes - elapsed_minutes)
                        logger.info(f"Warm-up in progress: {elapsed_minutes:.1f}/{self.warmup_period_minutes} minutes elapsed, {remaining_minutes:.1f} minutes remaining")
                    else:
                        # Process MACD signals only if warm-up is complete
                        logger.info(f"Warm-up complete, processing trading signals...")
                        self.process_macd_signal()
                
                # Wait for the next update
                logger.info(f"Waiting {self.interval_seconds} seconds until next update...")
                logger.info("\n" + "-" * 80 + "\n")
                time.sleep(self.interval_seconds)
        
        except KeyboardInterrupt:
            logger.info("Integrated trading system stopped by user")
            self.is_running = False
            
            # Save the quote data to CSV
            self.quote_monitor.save_to_csv()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Integrated MACD Trading System")
    
    parser.add_argument(
        "--symbol", 
        type=str, 
        default="NVDA",
        help="Stock symbol to trade (default: NVDA)"
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        default=60,
        help="Update interval in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--shares", 
        type=int, 
        default=100,
        help="Number of shares per trade (default: 100)"
    )
    
    parser.add_argument(
        "--fast-window", 
        type=int, 
        default=13,
        help="Fast EMA window for MACD (default: 13)"
    )
    
    parser.add_argument(
        "--slow-window", 
        type=int, 
        default=21,
        help="Slow EMA window for MACD (default: 21)"
    )
    
    parser.add_argument(
        "--signal-window", 
        type=int, 
        default=9,
        help="Signal line window for MACD (default: 9)"
    )
    
    parser.add_argument(
        "--extended-hours",
        action="store_true",
        help="Enable trading during extended hours"
    )
    
    parser.add_argument(
        "--warmup",
        type=int,
        default=60,
        help="Warm-up period in minutes before trading begins (default: 60)"
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Create and run the integrated trading system
    trader = IntegratedMACDTrader(
        symbol=args.symbol,
        interval_seconds=args.interval,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        signal_window=args.signal_window,
        shares_per_trade=args.shares,
        extended_hours=args.extended_hours,
        warmup_period_minutes=args.warmup
    )
    
    # Run the trader
    trader.run()