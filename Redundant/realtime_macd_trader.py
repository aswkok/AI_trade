#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Real-time MACD Trader

This script integrates real-time quote monitoring with MACD-based trading decisions.
It fetches real-time bid and ask prices, calculates MACD indicators, and executes
trades based on MACD signals.
"""

import os
import time
import logging
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

# Import the QuoteMonitor class
from quote_monitor import QuoteMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RealTimeMACDTrader:
    """Real-time MACD-based trading system using live quote data."""
    
    def __init__(self, symbol, shares_per_trade=100, max_records=100, interval_seconds=60,
                 fast_window=13, slow_window=21, signal_window=9):
        """
        Initialize the real-time MACD trader.
        
        Args:
            symbol: Stock symbol to trade
            shares_per_trade: Number of shares to trade per signal
            max_records: Maximum number of records to keep in memory
            interval_seconds: Interval between quote fetches in seconds
            fast_window: Window for the fast EMA in MACD calculation
            slow_window: Window for the slow EMA in MACD calculation
            signal_window: Window for the signal line in MACD calculation
        """
        # Load environment variables
        load_dotenv()
        
        # API credentials
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_API_SECRET")
        
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not found. Please set ALPACA_API_KEY and ALPACA_API_SECRET in .env file.")
        
        # Initialize clients
        self.trading_client = TradingClient(self.api_key, self.api_secret, paper=True)
        self.data_client = StockHistoricalDataClient(self.api_key, self.api_secret)
        
        # Trading settings
        self.symbol = symbol
        self.shares_per_trade = shares_per_trade
        self.interval_seconds = interval_seconds
        
        # Extended hours settings
        self.extended_hours = os.getenv("EXTENDED_HOURS", "True").lower() in ["true", "1", "t", "yes"]
        self.overnight_trading = os.getenv("OVERNIGHT_TRADING", "True").lower() in ["true", "1", "t", "yes"]
        
        # Initialize the quote monitor
        self.quote_monitor = QuoteMonitor(
            symbol=symbol,
            max_records=max_records,
            interval_seconds=interval_seconds,
            fast_window=fast_window,
            slow_window=slow_window,
            signal_window=signal_window
        )
        
        # Trading state
        self.position_type = "NONE"  # NONE, LONG, SHORT
        self.position_shares = 0
        self.last_action = None
        self.last_signal_time = None
        
        logger.info(f"Real-time MACD Trader initialized for {symbol}")
        logger.info(f"MACD Parameters: Fast={fast_window}, Slow={slow_window}, Signal={signal_window}")
        logger.info(f"Shares per trade: {shares_per_trade}")
        logger.info(f"Extended hours trading: {self.extended_hours}")
        logger.info(f"Overnight trading: {self.overnight_trading}")
    
    def get_current_position(self):
        """
        Get the current position for the symbol.
        
        Returns:
            tuple: (position_qty, position_side)
        """
        try:
            # Get all positions
            positions = self.trading_client.get_all_positions()
            
            # Find position for the symbol
            for position in positions:
                if position.symbol == self.symbol:
                    qty = int(position.qty)
                    side = "LONG" if qty > 0 else "SHORT" if qty < 0 else "NONE"
                    return qty, side
            
            return 0, "NONE"
        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return 0, "NONE"
    
    def place_order(self, side, qty, limit_price=None):
        """
        Place an order with support for extended hours trading.
        
        Args:
            side: Buy or sell side
            qty: Quantity of shares to buy/sell
            limit_price: Limit price for extended hours trading
            
        Returns:
            Order object or None if order placement failed
        """
        # Check if we're in a valid trading session
        now = datetime.now()
        is_market_hours = self.is_market_hours(now)
        is_pre_market = self.is_pre_market(now)
        is_after_hours = self.is_after_hours(now)
        is_overnight = self.is_overnight(now)
        
        # Log the current trading session
        if is_market_hours:
            logger.info("Trading during regular market hours")
        elif is_pre_market:
            logger.info("Trading during pre-market session")
        elif is_after_hours:
            logger.info("Trading during after-hours session")
        elif is_overnight:
            logger.info("Trading during overnight session")
        
        # Check if we can trade in the current session
        use_extended_hours = self.extended_hours
        can_trade_by_settings = is_market_hours or \
                   (use_extended_hours and (is_pre_market or is_after_hours)) or \
                   (self.overnight_trading and is_overnight)
        
        if not can_trade_by_settings:
            logger.warning(f"Cannot place order for {self.symbol} - outside of allowed trading hours")
            logger.warning(f"Extended hours trading: {self.extended_hours}, Overnight trading: {self.overnight_trading}")
            return None
        
        # For extended hours or overnight trading, check eligibility
        if use_extended_hours or is_overnight:
            account_eligible, symbol_eligible, error_message = self.check_extended_hours_eligibility()
            
            if not account_eligible:
                logger.warning(f"Your account does not support extended hours trading: {error_message}")
                return None
                
            if not symbol_eligible:
                logger.warning(f"{self.symbol} is not eligible for extended hours trading: {error_message}")
                logger.warning("Attempting to place the order anyway, but it may be rejected by the broker")
        
        # For extended hours and overnight trading, we MUST use limit orders
        if use_extended_hours or is_overnight:
            # Get the latest quote to determine a good limit price if not provided
            if limit_price is None:
                try:
                    # Use the quote from our monitor
                    if not self.quote_monitor.quotes_df.empty:
                        latest_quote = self.quote_monitor.quotes_df.iloc[-1]
                        ask_price = float(latest_quote['ask'])
                        bid_price = float(latest_quote['bid'])
                        spread = ask_price - bid_price
                        spread_percentage = (spread / bid_price) * 100 if bid_price > 0 else 0
                        
                        # Log the current spread information
                        logger.info(f"Current quote - Ask: ${ask_price}, Bid: ${bid_price}, Spread: ${spread:.2f} ({spread_percentage:.2f}%)")
                        
                        # Adjust limit price based on session and spread
                        if is_overnight:
                            # During overnight, spreads can be wider, so use more aggressive pricing
                            if side == OrderSide.BUY:
                                buffer_percentage = min(max(1.0, spread_percentage), 3.0)
                                limit_price = round(ask_price * (1 + buffer_percentage/100), 2)
                                logger.info(f"Overnight BUY order - Using {buffer_percentage:.2f}% buffer above ask")
                            else:  # SELL
                                buffer_percentage = min(max(1.0, spread_percentage), 3.0)
                                limit_price = round(bid_price * (1 - buffer_percentage/100), 2)
                                logger.info(f"Overnight SELL order - Using {buffer_percentage:.2f}% buffer below bid")
                        else:  # Extended hours (pre-market or after-hours)
                            # During extended hours, spreads are typically narrower than overnight
                            if side == OrderSide.BUY:
                                buffer_percentage = min(max(0.5, spread_percentage/2), 1.5)
                                limit_price = round(ask_price * (1 + buffer_percentage/100), 2)
                                logger.info(f"Extended hours BUY order - Using {buffer_percentage:.2f}% buffer above ask")
                            else:  # SELL
                                buffer_percentage = min(max(0.5, spread_percentage/2), 1.5)
                                limit_price = round(bid_price * (1 - buffer_percentage/100), 2)
                                logger.info(f"Extended hours SELL order - Using {buffer_percentage:.2f}% buffer below bid")
                    else:
                        # Fallback to Alpaca API if our monitor doesn't have data yet
                        quote_request = StockLatestQuoteRequest(symbol_or_symbols=[self.symbol])
                        quotes = self.data_client.get_stock_latest_quote(quote_request)
                        
                        if self.symbol in quotes:
                            quote = quotes[self.symbol]
                            ask_price = float(quote.ask_price)
                            bid_price = float(quote.bid_price)
                            
                            # Set limit price with default buffer
                            if side == OrderSide.BUY:
                                limit_price = round(ask_price * 1.01, 2)  # 1% above ask
                            else:  # SELL
                                limit_price = round(bid_price * 0.99, 2)  # 1% below bid
                        else:
                            logger.warning(f"Could not get quote for {self.symbol}, cannot place extended hours order without price")
                            return None
                except Exception as e:
                    logger.error(f"Error getting quote: {e}")
                    return None
            
            logger.info(f"Setting limit price for {side} order to ${limit_price}")
            
            # Create a limit order for extended/overnight hours
            logger.info(f"Creating limit order for extended/overnight hours: {self.symbol} at ${limit_price}")
            order_data = LimitOrderRequest(
                symbol=self.symbol,
                qty=qty,
                side=side,
                limit_price=limit_price,
                time_in_force=TimeInForce.DAY,
                extended_hours=True
            )
        else:
            # Create a market order for regular hours
            logger.info(f"Creating market order for regular hours: {self.symbol}")
            order_data = MarketOrderRequest(
                symbol=self.symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY
            )
        
        # Place the order
        try:
            order = self.trading_client.submit_order(order_data)
            
            # Log the order details
            if use_extended_hours or is_overnight:
                logger.info(f"Order placed during {'overnight' if is_overnight else 'extended hours'} - Symbol: {self.symbol}, Side: {side}, Qty: {qty}, Order ID: {order.id}")
            else:
                logger.info(f"Order placed during regular hours - Symbol: {self.symbol}, Side: {side}, Qty: {qty}, Order ID: {order.id}")
            
            return order
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    def check_extended_hours_eligibility(self):
        """
        Check if the account and symbol are eligible for extended hours trading.
            
        Returns:
            tuple: (account_eligible, symbol_eligible, error_message)
        """
        try:
            # Check if the account supports extended hours trading
            account = self.trading_client.get_account()
            account_eligible = True  # Assume eligible by default
            
            # Check if the symbol is available for extended hours trading
            try:
                # Get asset information
                asset = self.trading_client.get_asset(self.symbol)
                
                if not asset.tradable:
                    return False, False, f"{self.symbol} is not tradable"
                
                if not asset.easy_to_borrow:
                    logger.warning(f"{self.symbol} is not easy to borrow, which may limit short selling")
                
                # Check if the asset is fractionable (indicates higher liquidity)
                symbol_eligible = asset.fractionable
                
                # Additional check for extended hours eligibility
                if hasattr(asset, 'extended_hours_eligible'):
                    symbol_eligible = asset.extended_hours_eligible
                
                # Log the asset details
                logger.info(f"Asset details for {self.symbol}: Tradable: {asset.tradable}, Easy to borrow: {asset.easy_to_borrow}, Fractionable: {asset.fractionable}")
                
                return account_eligible, symbol_eligible, ""
            except Exception as e:
                logger.warning(f"Error checking symbol eligibility for {self.symbol}: {e}")
                return account_eligible, False, f"Error checking symbol: {e}"
                
        except Exception as e:
            logger.error(f"Error checking account eligibility: {e}")
            return False, False, f"Error checking account: {e}"
    
    def is_market_hours(self, dt=None):
        """Check if the current time is during regular market hours (9:30 AM - 4:00 PM ET)."""
        dt = dt or datetime.now()
        
        # Convert to Eastern Time (ET)
        # Note: This is a simplified approach. For production, use pytz or dateutil.
        # For now, we're assuming the system is already in Eastern Time.
        
        # Check if it's a weekday (Monday=0, Sunday=6)
        if dt.weekday() > 4:  # Saturday or Sunday
            return False
        
        # Check if it's between 9:30 AM and 4:00 PM ET
        market_open = dt.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = dt.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= dt < market_close
    
    def is_pre_market(self, dt=None):
        """Check if the current time is during pre-market hours (4:00 AM - 9:30 AM ET)."""
        dt = dt or datetime.now()
        
        # Check if it's a weekday
        if dt.weekday() > 4:  # Saturday or Sunday
            return False
        
        # Check if it's between 4:00 AM and 9:30 AM ET
        pre_market_open = dt.replace(hour=4, minute=0, second=0, microsecond=0)
        market_open = dt.replace(hour=9, minute=30, second=0, microsecond=0)
        
        return pre_market_open <= dt < market_open
    
    def is_after_hours(self, dt=None):
        """Check if the current time is during after-hours (4:00 PM - 8:00 PM ET)."""
        dt = dt or datetime.now()
        
        # Check if it's a weekday
        if dt.weekday() > 4:  # Saturday or Sunday
            return False
        
        # Check if it's between 4:00 PM and 8:00 PM ET
        market_close = dt.replace(hour=16, minute=0, second=0, microsecond=0)
        after_hours_close = dt.replace(hour=20, minute=0, second=0, microsecond=0)
        
        return market_close <= dt < after_hours_close
    
    def is_overnight(self, dt=None):
        """Check if the current time is during overnight hours (8:00 PM - 4:00 AM ET)."""
        dt = dt or datetime.now()
        
        # For overnight, we need to check across days
        overnight_start = dt.replace(hour=20, minute=0, second=0, microsecond=0)
        overnight_end = dt.replace(hour=4, minute=0, second=0, microsecond=0)
        
        # If it's between 8:00 PM and midnight
        if dt.hour >= 20:
            # Check if it's Sunday-Thursday (next day is a trading day)
            return dt.weekday() < 4  # Monday-Thursday
        
        # If it's between midnight and 4:00 AM
        elif dt.hour < 4:
            # Check if it's Monday-Friday (current day is a trading day)
            return dt.weekday() <= 4  # Tuesday-Friday
        
        return False
    
    def process_macd_signal(self):
        """
        Process the latest MACD signal and execute trades if necessary.
        
        Returns:
            bool: True if a trade was executed, False otherwise
        """
        # Get the current MACD signal
        macd_signal = self.quote_monitor.get_macd_signal()
        
        # If we don't have a valid signal yet, do nothing
        if macd_signal['macd_position'] is None:
            logger.info("Not enough data for MACD calculation yet")
            return False
        
        # Get the current position
        current_qty, current_side = self.get_current_position()
        logger.info(f"Current position for {self.symbol}: {current_qty} shares, Side: {current_side}")
        
        # Extract signal information
        signal = macd_signal['signal']
        macd_position = macd_signal['macd_position']
        crossover = macd_signal['crossover']
        crossunder = macd_signal['crossunder']
        
        # Initialize action
        action = None
        qty = 0
        
        # No position yet
        if current_side == "NONE":
            if macd_position == "ABOVE":
                # Initial buy
                action = "BUY"
                qty = self.shares_per_trade
                logger.info(f"No current position for {self.symbol} and MACD is ABOVE - taking initial action")
                logger.info(f"Forcing initial BUY for {self.symbol} based on MACD position ABOVE")
            elif macd_position == "BELOW":
                # Initial short
                action = "SELL"
                qty = self.shares_per_trade
                logger.info(f"No current position for {self.symbol} and MACD is BELOW - taking initial action")
                logger.info(f"Forcing initial SHORT for {self.symbol} based on MACD position BELOW")
        
        # Currently long
        elif current_side == "LONG":
            if crossunder:
                # MACD crossed below signal line - sell and short
                action = "SELL"
                qty = current_qty + self.shares_per_trade  # Sell current position + short additional shares
                logger.info(f"MACD crossed BELOW signal line while LONG - selling position and shorting")
            elif macd_position == "BELOW" and not self.last_action == "SELL":
                # MACD is below signal line but no recent crossunder - sell and short
                action = "SELL"
                qty = current_qty + self.shares_per_trade
                logger.info(f"MACD is BELOW signal line while LONG - selling position and shorting")
        
        # Currently short
        elif current_side == "SHORT":
            if crossover:
                # MACD crossed above signal line - cover and buy
                action = "BUY"
                qty = abs(current_qty) + self.shares_per_trade  # Cover short position + buy additional shares
                logger.info(f"MACD crossed ABOVE signal line while SHORT - covering position and buying")
            elif macd_position == "ABOVE" and not self.last_action == "BUY":
                # MACD is above signal line but no recent crossover - cover and buy
                action = "BUY"
                qty = abs(current_qty) + self.shares_per_trade
                logger.info(f"MACD is ABOVE signal line while SHORT - covering position and buying")
        
        # Execute the trade if we have an action
        if action and qty > 0:
            side = OrderSide.BUY if action == "BUY" else OrderSide.SELL
            
            # Log the trading decision
            logger.info(f"{self.symbol} - Signal: {signal}, Position: {macd_signal['position']}, MACD Position: {macd_position}, Action: {action}, Shares: {qty}")
            
            # Place the order
            order = self.place_order(side, qty)
            
            if order:
                # Update trading state
                self.last_action = action
                self.last_signal_time = datetime.now()
                self.position_type = "LONG" if action == "BUY" else "SHORT"
                self.position_shares = qty if action == "BUY" else -qty
                
                # Log the trade
                logger.info(f"{action}: {qty} shares of {self.symbol} - MACD_{self.quote_monitor.fast_window}_{self.quote_monitor.slow_window}_{self.quote_monitor.signal_window} strategy")
                
                # Log the updated state
                logger.info(f"Strategy state for {self.symbol} (MACD_{self.quote_monitor.fast_window}_{self.quote_monitor.slow_window}_{self.quote_monitor.signal_window}): "
                           f"{{'position_type': '{self.position_type}', 'shares': {self.position_shares}, "
                           f"'last_action': '{self.last_action}', 'last_signal_time': '{self.last_signal_time.isoformat()}'}}")
                
                return True
        
        return False
    
    def run(self):
        """Run the real-time MACD trader."""
        logger.info(f"Starting real-time MACD trader for {self.symbol}")
        logger.info(f"Press Ctrl+C to stop trading")
        
        try:
            while True:
                # Get the latest quote
                quote_data = self.quote_monitor.get_latest_quote()
                
                if quote_data:
                    # Add to dataframe
                    self.quote_monitor.add_quote_to_dataframe(quote_data)
                    
                    # Process MACD signal
                    self.process_macd_signal()
                    
                    # Display the quotes and MACD information
                    self.quote_monitor.display_quotes()
                
                # Wait for the next interval
                logger.info(f"Waiting {self.interval_seconds} seconds until next update...")
                logger.info("\n" + "-" * 80)
                time.sleep(self.interval_seconds)
        
        except KeyboardInterrupt:
            logger.info("Real-time MACD trader stopped by user")
            
            # Save the quotes to CSV before exiting
            self.quote_monitor.save_to_csv()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Real-time MACD Trader")
    
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
        help="Interval between quote fetches in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--max-records", 
        type=int, 
        default=100,
        help="Maximum number of records to keep in memory (default: 100)"
    )
    
    parser.add_argument(
        "--shares", 
        type=int, 
        default=100,
        help="Number of shares to trade per signal (default: 100)"
    )
    
    parser.add_argument(
        "--fast-window", 
        type=int, 
        default=13,
        help="Window for the fast EMA in MACD calculation (default: 13)"
    )
    
    parser.add_argument(
        "--slow-window", 
        type=int, 
        default=21,
        help="Window for the slow EMA in MACD calculation (default: 21)"
    )
    
    parser.add_argument(
        "--signal-window", 
        type=int, 
        default=9,
        help="Window for the signal line in MACD calculation (default: 9)"
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Create and run the real-time MACD trader
    trader = RealTimeMACDTrader(
        symbol=args.symbol,
        shares_per_trade=args.shares,
        max_records=args.max_records,
        interval_seconds=args.interval,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        signal_window=args.signal_window
    )
    
    # Run the trader
    trader.run()
