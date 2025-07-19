#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Yahoo Finance Close Price Monitor for MACD Trading System

This is a specialized version of the Yahoo quote monitor that uses closing prices
instead of mid-prices (bid+ask)/2 for MACD calculations, allowing for comparison
of different price sources for signal generation.
"""

import os
import sys
import time
import logging
import threading
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
from dotenv import load_dotenv
from tabulate import tabulate

# Import the base YahooQuoteMonitor to extend it
from yahoo_quote_monitor import YahooQuoteMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class YahooCloseQuoteMonitor(YahooQuoteMonitor):
    """
    Enhanced monitor for Yahoo Finance that uses closing prices for MACD calculations.
    
    This class extends the YahooQuoteMonitor but uses historical closing prices
    for calculating MACD indicators instead of mid-prices from bid/ask.
    """
    
    def __init__(self, symbol, max_records=200, interval_seconds=5, fast_window=13, slow_window=21, signal_window=9):
        """
        Initialize the close price monitor with Yahoo Finance support.
        
        Args:
            symbol: Stock symbol to monitor
            max_records: Maximum number of records to keep in memory
            interval_seconds: Interval between data fetches in seconds
            fast_window: Window for the fast EMA in MACD calculation
            slow_window: Window for the slow EMA in MACD calculation
            signal_window: Window for the signal line in MACD calculation
        """
        # Call the parent class constructor
        super().__init__(symbol, max_records, interval_seconds, fast_window, slow_window, signal_window)
        
        # Modify the dataframe to include a close column
        self.quotes_df['close'] = 0.0
        
        # Log that we're using close prices
        logger.info(f"Yahoo Close Price Monitor initialized for {symbol}")
        logger.info(f"Using CLOSE prices for MACD calculation instead of mid-prices")
    
    def _fetch_initial_data(self):
        """
        Fetch initial historical data to populate the quotes dataframe with close prices.
        """
        try:
            # Calculate the start date based on how many candles we need
            # For MACD calculation, we need at least slow_window + signal_window periods
            min_periods = self.slow_window + self.signal_window
            
            # Add some buffer to ensure we have enough data
            buffer_factor = 3
            periods_needed = min_periods * buffer_factor
            
            # For 1-minute data, we'll fetch the last X minutes
            # For daily data, we'll fetch the last X days
            interval = "1m"  # 1-minute data
            period = f"{periods_needed}m"  # Last X minutes
            
            # For longer periods, use days
            if periods_needed > 60:
                days_needed = max(1, periods_needed // 390)  # ~390 minutes in a trading day
                period = f"{days_needed + 1}d"  # Add 1 day for safety
            
            logger.info(f"Fetching initial {period} of {interval} historical data for {self.symbol}")
            
            # Download historical data
            hist_data = yf.download(
                tickers=self.symbol,
                period=period,
                interval=interval,
                prepost=self.include_extended_hours,
                progress=False,
                threads=False
            )
            
            if hist_data.empty:
                logger.warning(f"No historical data available for {self.symbol}")
                return
            
            # Process the historical data
            for idx, row in hist_data.iterrows():
                # Convert to local timezone
                timestamp = idx.to_pydatetime()
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.replace(tzinfo=None)
                
                # Get the close price
                close_price = row['Close']
                
                # Estimate bid/ask from close (for compatibility with base class)
                spread = close_price * 0.0025  # 0.25% of price
                bid_price = close_price - (spread / 2)
                ask_price = close_price + (spread / 2)
                spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
                
                # Calculate mid price for compatibility
                mid_price = (bid_price + ask_price) / 2
                
                # Create a new row
                new_row = pd.DataFrame({
                    'timestamp': [timestamp],
                    'bid': [bid_price],
                    'ask': [ask_price],
                    'spread': [spread],
                    'spread_pct': [spread_pct],
                    'mid': [mid_price],
                    'close': [close_price]  # Add the close price
                })
                
                # Append to dataframe
                self.quotes_df = pd.concat([self.quotes_df, new_row], ignore_index=True)
            
            # Trim to max_records
            if len(self.quotes_df) > self.max_records:
                self.quotes_df = self.quotes_df.iloc[-self.max_records:]
            
            logger.info(f"Loaded {len(self.quotes_df)} historical data points for {self.symbol}")
            
        except Exception as e:
            logger.error(f"Error fetching initial historical data: {e}")
    
    def _fetch_yahoo_quote(self):
        """
        Fetch the latest quote from Yahoo Finance, including close price.
        
        Returns:
            tuple: (timestamp, bid_price, ask_price, spread, spread_percentage, close_price)
        """
        try:
            # Get the current timestamp in local time
            timestamp = datetime.now().replace(tzinfo=None)
            
            # Method 1: Get the latest quote using history with a very short period
            try:
                # Use a random interval to avoid caching
                intervals = ["1m", "2m"]
                interval = random.choice(intervals)
                
                # Force a fresh request with a unique parameter combination
                hist_data = yf.download(
                    tickers=self.symbol,
                    period=f"1d",
                    interval=interval,
                    prepost=self.include_extended_hours,
                    progress=False,
                    threads=False,
                    proxy=None,
                    rounding=True
                ).tail(1)
                
                if not hist_data.empty:
                    # Get the latest close price
                    close_price = hist_data['Close'].iloc[0].item()
                    logger.debug(f"Got fresh close price via download: {close_price}")
                    
                    # Create a synthetic spread (this is an approximation)
                    if 'High' in hist_data and 'Low' in hist_data:
                        high = hist_data['High'].iloc[0].item()
                        low = hist_data['Low'].iloc[0].item()
                        spread = (high - low) * 0.1  # 10% of the day's range
                        if spread <= 0 or spread > (close_price * 0.03):  # Cap at 3% of price
                            spread = close_price * 0.0025  # Default to 0.25% of price
                    else:
                        spread = close_price * 0.0025  # 0.25% of price
                    
                    # Calculate bid and ask from the close price and spread
                    bid_price = close_price - (spread / 2)
                    ask_price = close_price + (spread / 2)
                    spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
                    
                    # Make sure we have reasonable values
                    if bid_price <= 0 or ask_price <= 0 or spread_pct > 5:
                        spread = close_price * 0.001  # 0.1% of price
                        bid_price = close_price - (spread / 2)
                        ask_price = close_price + (spread / 2)
                        spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
                    
                    logger.debug(f"Using close price: {close_price}, bid={bid_price}, ask={ask_price}")
                    return timestamp, bid_price, ask_price, spread, spread_pct, close_price
            except Exception as e:
                logger.debug(f"Error in direct download method: {e}")
                # Continue to fallback method
            
            # Method 2: Fallback to ticker.info
            self.ticker = yf.Ticker(self.symbol)
            quote_info = self.ticker.info
            
            # Get the regular market price as close price
            if 'regularMarketPrice' in quote_info and quote_info['regularMarketPrice'] > 0:
                close_price = float(quote_info['regularMarketPrice'])
            else:
                # If no regular price, try previous close
                close_price = float(quote_info.get('previousClose', 100.0))
            
            # Check for extended hours prices
            is_extended_hours = False
            if self.include_extended_hours:
                if 'postMarketPrice' in quote_info and quote_info['postMarketPrice'] > 0:
                    close_price = float(quote_info['postMarketPrice'])
                    is_extended_hours = True
                    logger.debug(f"Using post-market price as close: {close_price}")
                elif 'preMarketPrice' in quote_info and quote_info['preMarketPrice'] > 0:
                    close_price = float(quote_info['preMarketPrice'])
                    is_extended_hours = True
                    logger.debug(f"Using pre-market price as close: {close_price}")
            
            # Use actual bid/ask if available
            if 'bid' in quote_info and quote_info['bid'] > 0 and 'ask' in quote_info and quote_info['ask'] > 0:
                bid_price = float(quote_info['bid'])
                ask_price = float(quote_info['ask'])
                spread = ask_price - bid_price
                spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
                logger.debug(f"Using actual bid/ask with close: {bid_price}/{ask_price}, close={close_price}")
                return timestamp, bid_price, ask_price, spread, spread_pct, close_price
            
            # Otherwise estimate bid/ask from the close price
            spread = close_price * 0.0025  # 0.25% of price
            bid_price = close_price - (spread / 2)
            ask_price = close_price + (spread / 2)
            spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
            
            logger.debug(f"Using estimated bid/ask from close: {bid_price}/{ask_price}, close={close_price}")
            return timestamp, bid_price, ask_price, spread, spread_pct, close_price
            
        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance quote: {e}")
            return None
    
    def add_quote_to_dataframe(self, quote_data):
        """
        Add a quote to the dataframe and maintain max_records limit.
        
        Args:
            quote_data: Tuple of (timestamp, bid_price, ask_price, spread, spread_pct, close_price)
        """
        if quote_data is None:
            return
        
        # Unpack the quote data
        if len(quote_data) == 6:  # New format with close price
            timestamp, bid_price, ask_price, spread, spread_pct, close_price = quote_data
        else:  # Old format without close price
            timestamp, bid_price, ask_price, spread, spread_pct = quote_data
            close_price = (bid_price + ask_price) / 2  # Use mid as close if not provided
        
        # Calculate mid price (average of bid and ask)
        mid_price = (bid_price + ask_price) / 2
        
        # Create a new row
        new_row = pd.DataFrame({
            'timestamp': [timestamp],
            'bid': [bid_price],
            'ask': [ask_price],
            'spread': [spread],
            'spread_pct': [spread_pct],
            'mid': [mid_price],
            'close': [close_price]  # Add the close price
        })
        
        # Log the new quote for debugging
        logger.debug(f"Adding new quote: {timestamp}, bid=${bid_price:.2f}, ask=${ask_price:.2f}, close=${close_price:.2f}")
        
        # Append to dataframe
        self.quotes_df = pd.concat([self.quotes_df, new_row], ignore_index=True)
        
        # Trim to max_records
        if len(self.quotes_df) > self.max_records:
            self.quotes_df = self.quotes_df.iloc[-self.max_records:]
            
        # Calculate MACD if we have enough data
        self.calculate_macd()
    
    def calculate_macd(self):
        """
        Calculate MACD based on the closing prices in the quotes dataframe.
        
        This method adds the following columns to the dataframe:
        - EMAfast: Fast EMA of close prices
        - EMAslow: Slow EMA of close prices
        - MACD: MACD line (EMAfast - EMAslow)
        - Signal: Signal line (EMA of MACD)
        - Histogram: MACD - Signal
        - MACD_position: 'ABOVE' or 'BELOW' indicating MACD position relative to signal
        - crossover: True when MACD crosses above signal line
        - crossunder: True when MACD crosses below signal line
        """
        # Need at least slow_window + signal_window data points for a valid MACD
        min_periods = self.slow_window + self.signal_window
        
        if len(self.quotes_df) < min_periods:
            logger.debug(f"Not enough data for MACD calculation. Need {min_periods}, have {len(self.quotes_df)}")
            return
        
        # Calculate EMAs using close prices instead of mid prices
        self.quotes_df['EMAfast'] = self.quotes_df['close'].ewm(span=self.fast_window, adjust=False).mean()
        self.quotes_df['EMAslow'] = self.quotes_df['close'].ewm(span=self.slow_window, adjust=False).mean()
        
        # Calculate MACD line
        self.quotes_df['MACD'] = self.quotes_df['EMAfast'] - self.quotes_df['EMAslow']
        
        # Calculate Signal line
        self.quotes_df['Signal'] = self.quotes_df['MACD'].ewm(span=self.signal_window, adjust=False).mean()
        
        # Calculate Histogram
        self.quotes_df['Histogram'] = self.quotes_df['MACD'] - self.quotes_df['Signal']
        
        # Determine if MACD is above or below signal line
        self.quotes_df['MACD_position'] = 'BELOW'
        self.quotes_df.loc[self.quotes_df['MACD'] > self.quotes_df['Signal'], 'MACD_position'] = 'ABOVE'
        
        # Detect crossovers and crossunders
        self.quotes_df['crossover'] = False
        self.quotes_df['crossunder'] = False
        
        # Need at least 2 rows to detect crossovers
        if len(self.quotes_df) >= 2:
            # Get the current and previous positions
            current_position = self.quotes_df.iloc[-1]['MACD_position']
            previous_position = self.quotes_df.iloc[-2]['MACD_position']
            
            # Detect crossover (MACD crosses above signal)
            if current_position == 'ABOVE' and previous_position == 'BELOW':
                self.quotes_df.iloc[-1, self.quotes_df.columns.get_loc('crossover')] = True
                logger.info(f"MACD Crossover detected (BULLISH) at {self.quotes_df.iloc[-1]['timestamp']}")
            
            # Detect crossunder (MACD crosses below signal)
            elif current_position == 'BELOW' and previous_position == 'ABOVE':
                self.quotes_df.iloc[-1, self.quotes_df.columns.get_loc('crossunder')] = True
                logger.info(f"MACD Crossunder detected (BEARISH) at {self.quotes_df.iloc[-1]['timestamp']}")
    
    def display_quotes(self):
        """
        Display the latest quotes and MACD information in a formatted table.
        """
        if self.quotes_df.empty:
            print("No quotes available yet.")
            return
        
        # Get the latest quote
        latest = self.quotes_df.iloc[-1]
        
        # Display the latest quote information
        print("\n" + "=" * 80)
        print(f"Yahoo Finance Quote for {self.symbol} (Using CLOSE prices for MACD)")
        print("=" * 80)
        
        # Format the latest quote
        timestamp_str = latest['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        bid_str = f"${latest['bid']:.2f}"
        ask_str = f"${latest['ask']:.2f}"
        mid_str = f"${latest['mid']:.2f}"
        close_str = f"${latest['close']:.2f}"
        spread_str = f"${latest['spread']:.2f} ({latest['spread_pct']:.2f}%)"
        
        # Display the quote
        print(f"Time: {timestamp_str}")
        print(f"Bid: {bid_str} | Ask: {ask_str} | Mid: {mid_str} | Close: {close_str}")
        print(f"Spread: {spread_str}")
        
        # Check if we have MACD data
        if 'MACD' in self.quotes_df.columns:
            # Format MACD information
            macd_str = f"{latest['MACD']:.4f}"
            signal_str = f"{latest['Signal']:.4f}"
            histogram_str = f"{latest['Histogram']:.4f}"
            position_str = latest['MACD_position']
            
            # Determine if we have a crossover or crossunder
            signal_event = ""
            if latest['crossover']:
                signal_event = "BULLISH CROSSOVER (MACD crossed above Signal)"
            elif latest['crossunder']:
                signal_event = "BEARISH CROSSUNDER (MACD crossed below Signal)"
            
            # Display MACD information
            print("\nMACD Information (Using CLOSE prices):")
            print(f"MACD: {macd_str} | Signal: {signal_str} | Histogram: {histogram_str}")
            print(f"Position: {position_str}")
            
            if signal_event:
                print(f"Signal Event: {signal_event}")
        
        # Display recent quotes in a table
        print("\nRecent Quotes:")
        
        # Get the last few rows
        num_rows = min(10, len(self.quotes_df))
        recent_quotes = self.quotes_df.tail(num_rows).copy()
        
        # Format the timestamps
        recent_quotes['time'] = recent_quotes['timestamp'].dt.strftime('%H:%M:%S')
        
        # Select and format columns for display
        display_df = recent_quotes[['time', 'bid', 'ask', 'close']].copy()
        
        # Format prices
        for col in ['bid', 'ask', 'close']:
            display_df[col] = display_df[col].apply(lambda x: f"${x:.2f}")
        
        # Add MACD columns if available
        if 'MACD' in recent_quotes.columns:
            display_df['MACD'] = recent_quotes['MACD'].apply(lambda x: f"{x:.4f}")
            display_df['Signal'] = recent_quotes['Signal'].apply(lambda x: f"{x:.4f}")
            display_df['Hist'] = recent_quotes['Histogram'].apply(lambda x: f"{x:.4f}")
            display_df['Pos'] = recent_quotes['MACD_position']
        
        # Display the table
        print(tabulate(display_df, headers='keys', tablefmt='pretty', showindex=False))

# Create an alias for compatibility with the existing system
CloseQuoteMonitor = YahooCloseQuoteMonitor

if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Yahoo Finance close price monitor for MACD")
    
    parser.add_argument(
        "--symbol", 
        type=str, 
        default="AAPL",
        help="Stock symbol to monitor (default: AAPL)"
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        default=5,
        help="Interval between data fetches in seconds (default: 5)"
    )
    
    parser.add_argument(
        "--max-records", 
        type=int, 
        default=200,
        help="Maximum number of records to keep in memory (default: 200)"
    )
    
    args = parser.parse_args()
    
    # Create the quote monitor with Yahoo Finance close prices
    monitor = YahooCloseQuoteMonitor(
        symbol=args.symbol,
        max_records=args.max_records,
        interval_seconds=args.interval
    )
    
    # Give it a moment to fetch initial data
    logger.info("Waiting for initial data...")
    time.sleep(3)
    
    # Run the monitor - fetching happens in background thread
    try:
        while True:
            # Display the current quotes
            monitor.display_quotes()
            
            # Wait for the next display update
            logger.info(f"Waiting {args.interval} seconds until next display update...")
            time.sleep(args.interval)
    
    except KeyboardInterrupt:
        logger.info("Close price monitor stopped by user")
        
        # Close the monitor
        monitor.close()
        
        # Save the quotes to CSV before exiting
        monitor.save_to_csv()
