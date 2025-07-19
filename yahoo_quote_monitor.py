#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Yahoo Finance Quote Monitor for MACD Trading System

This is an alternative version of the quote monitor that uses Yahoo Finance API
for real-time data streaming, providing a fallback option when Alpaca is unavailable
or during extended hours trading.
"""

import os
import sys
import time
import logging
import threading
import argparse
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from tabulate import tabulate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class YahooQuoteMonitor:
    """
    Enhanced monitor for real-time bid and ask prices using Yahoo Finance.
    
    This class fetches real-time quotes from Yahoo Finance API,
    calculates MACD indicators, and provides trading signals.
    """
    
    def __init__(self, symbol, max_records=200, interval_seconds=5, fast_window=13, slow_window=21, signal_window=9):
        """
        Initialize the quote monitor with Yahoo Finance support.
        
        Args:
            symbol: Stock symbol to monitor
            max_records: Maximum number of records to keep in memory
            interval_seconds: Interval between data fetches in seconds
            fast_window: Window for the fast EMA in MACD calculation
            slow_window: Window for the slow EMA in MACD calculation
            signal_window: Window for the signal line in MACD calculation
        """
        # Load environment variables (for compatibility)
        load_dotenv()
        
        # Monitor settings
        self.symbol = symbol.upper()  # Ensure uppercase for Yahoo Finance API
        self.max_records = max_records
        self.interval_seconds = interval_seconds
        
        # Data storage
        self.quotes_df = pd.DataFrame(columns=['timestamp', 'bid', 'ask', 'spread', 'spread_pct', 'mid'])
        
        # MACD parameters
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        
        # MACD state tracking
        self.last_macd_position = None  # 'ABOVE' or 'BELOW'
        self.last_signal_time = None
        
        # Yahoo Finance ticker
        self.ticker = yf.Ticker(self.symbol)
        self.last_quote = None
        self.connected = True  # Assume connected initially
        
        # Enable extended hours data
        self.include_extended_hours = True  # Always include pre/post market data
        
        # Fetch thread
        self.fetch_thread = None
        self.is_running = False
        self.stop_event = threading.Event()
        
        # Fetch initial historical data including extended hours
        self._fetch_initial_data()
        
        # Start the background fetching thread
        self._start_fetching()
        
        logger.info(f"Yahoo Quote Monitor initialized for {symbol}")
        logger.info(f"Data fetch interval: {interval_seconds} seconds")
        logger.info(f"Maximum records: {max_records}")
        logger.info(f"MACD Parameters: Fast={fast_window}, Slow={slow_window}, Signal={signal_window}")
        logger.info(f"Extended hours data: {'Enabled' if self.include_extended_hours else 'Disabled'}")
    
    def _fetch_initial_data(self):
        """
        Fetch initial historical data to populate the quotes dataframe.
        """
        try:
            # Calculate the start date based on how many candles we need
            # For MACD calculation, we need at least slow + signal periods
            min_periods = self.slow_period + self.signal_period
            
            # Add some buffer to ensure we have enough data
            buffer_factor = 3
            periods_needed = min_periods * buffer_factor
            
            # For 1-minute data, we'll fetch the last X minutes
            # For daily data, we'll fetch the last X days
            if self.interval < 60:  # Less than 60 seconds
                # For intraday, get more data to ensure we have enough
                period = "5d"  # Get 5 days of data
                interval = "1m"  # 1-minute intervals
            else:  # Daily or longer
                # For daily data, get more historical data
                period = "60d"  # Get 60 days of data
                interval = "1h"  # 1-hour intervals
            
            logger.info(f"Fetching initial historical data for {self.symbol} with period={period}, interval={interval}")
            
            # Force a refresh of the ticker to avoid stale data
            self.ticker = yf.Ticker(self.symbol)
            
            # Fetch historical data from Yahoo Finance with all options specified to avoid caching
            # Include extended hours data if requested
            hist_data = self.ticker.history(
                period=period, 
                interval=interval, 
                prepost=self.include_extended_hours,
                actions=False,
                auto_adjust=True,
                back_adjust=False,
                repair=False
            )
            
            if hist_data.empty:
                logger.error(f"No historical data available for {self.symbol}")
                return False
                
            logger.info(f"Received {len(hist_data)} historical data points")
                
            # Process each row and add to our dataframe
            for idx, row in hist_data.iterrows():
                try:
                    # Convert index to datetime - pandas timestamps from yfinance need special handling
                    timestamp = idx.to_pydatetime()
                    # Ensure timezone-naive datetime
                    if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                        timestamp = timestamp.replace(tzinfo=None)
                except (AttributeError, TypeError):
                    # If conversion fails, try another approach
                    try:
                        timestamp = pd.to_datetime(idx)
                        # Ensure timezone-naive datetime
                        if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                            timestamp = timestamp.replace(tzinfo=None)
                    except:
                        # Last resort fallback
                        timestamp = datetime.now().replace(tzinfo=None)
                
                # Use close price as mid price
                mid_price = float(row['Close'])
                
                # Calculate a synthetic spread (0.05%)
                spread_pct = 0.05
                spread = mid_price * (spread_pct / 100)
                
                # Calculate bid and ask from mid price and spread
                bid_price = mid_price - (spread / 2)
                ask_price = mid_price + (spread / 2)
                
                # Add to our quotes dataframe
                self._add_quote(timestamp, bid_price, ask_price, spread, spread_pct)
            
            # Calculate initial MACD values
            self._calculate_macd()
            
            return True
            
        except Exception as e:
            logger.error(f"Error fetching initial data: {e}")
            return False
    
    def _start_fetching(self):
        """
        Start the background thread for fetching quotes from Yahoo Finance.
        """
        self.is_running = True
        self.fetch_thread = threading.Thread(target=self._fetch_loop)
        self.fetch_thread.daemon = True
        self.fetch_thread.start()
        logger.info(f"Started background fetching thread for {self.symbol}")
    
    def _fetch_loop(self):
        """
        Background loop that continuously fetches quotes from Yahoo Finance.
        """
        while not self.stop_event.is_set():
            try:
                # Fetch the latest quote
                quote_data = self._fetch_yahoo_quote()
                
                if quote_data:
                    # Add to dataframe
                    self.add_quote_to_dataframe(quote_data)
                    self.last_quote = quote_data
                    self.connected = True
                else:
                    logger.warning(f"Failed to fetch quote for {self.symbol}")
                    self.connected = False
                
                # Sleep for the interval
                time.sleep(self.interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in fetch loop: {e}")
                self.connected = False
                time.sleep(self.interval_seconds)  # Sleep and retry
    
    def _fetch_yahoo_quote(self):
        """
        Fetch the latest quote from Yahoo Finance using direct API calls.
        
        Returns:
            tuple: (timestamp, bid_price, ask_price, spread, spread_percentage)
        """
        try:
            # Get the current timestamp in local time as a timezone-naive datetime object
            timestamp = datetime.now().replace(tzinfo=None)
            
            # Use a completely different approach - fetch real-time data directly
            # This bypasses the yfinance caching mechanism
            
            # Method 1: Get the latest quote using history with a very short period
            # This forces a new request each time
            try:
                # Use a random interval to avoid caching
                intervals = ["1m", "2m"]
                interval = random.choice(intervals)
                
                # Force a fresh request with a unique parameter combination each time
                # The random interval and timestamp in the period helps avoid cache hits
                current_time = int(time.time())
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
                    # Get the latest price - fix the FutureWarning by using .iloc[0].item()
                    current_price = hist_data['Close'].iloc[0].item()
                    logger.debug(f"Got fresh price via download: {current_price}")
                    
                    # Create a synthetic spread (this is an approximation)
                    if 'High' in hist_data and 'Low' in hist_data:
                        # Use the day's high and low to estimate a realistic spread
                        high = hist_data['High'].iloc[0].item()
                        low = hist_data['Low'].iloc[0].item()
                        # Use a portion of the high-low range as the spread
                        spread = (high - low) * 0.1  # 10% of the day's range
                        if spread <= 0 or spread > (current_price * 0.03):  # Cap at 3% of price
                            spread = current_price * 0.0025  # Default to 0.25% of price
                    else:
                        # Default spread if high/low not available
                        spread = current_price * 0.0025  # 0.25% of price
                    
                    # Calculate bid and ask from the current price and spread
                    bid_price = current_price - (spread / 2)
                    ask_price = current_price + (spread / 2)
                    spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
                    
                    # Make sure we have reasonable values
                    if bid_price <= 0 or ask_price <= 0 or spread_pct > 5:
                        # Fallback to a more conservative spread
                        spread = current_price * 0.001  # 0.1% of price
                        bid_price = current_price - (spread / 2)
                        ask_price = current_price + (spread / 2)
                        spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
                    
                    logger.debug(f"Using prices: bid={bid_price}, ask={ask_price}, spread={spread_pct}%")
                    return timestamp, bid_price, ask_price, spread, spread_pct
            except Exception as e:
                logger.debug(f"Error in direct download method: {e}")
                # Continue to fallback method
            
            # Method 2: Fallback to ticker.info but force a new ticker instance
            # This helps avoid some caching issues
            self.ticker = yf.Ticker(self.symbol)
            quote_info = self.ticker.info
            
            # Get the regular market price
            if 'regularMarketPrice' in quote_info and quote_info['regularMarketPrice'] > 0:
                current_price = float(quote_info['regularMarketPrice'])
            else:
                # If no regular price, try previous close
                current_price = float(quote_info.get('previousClose', 100.0))  # Default to 100 if all else fails
            
            # Check for extended hours prices
            is_extended_hours = False
            if self.include_extended_hours:
                if 'postMarketPrice' in quote_info and quote_info['postMarketPrice'] > 0:
                    current_price = float(quote_info['postMarketPrice'])
                    is_extended_hours = True
                    logger.debug(f"Using post-market price: {current_price}")
                elif 'preMarketPrice' in quote_info and quote_info['preMarketPrice'] > 0:
                    current_price = float(quote_info['preMarketPrice'])
                    is_extended_hours = True
                    logger.debug(f"Using pre-market price: {current_price}")
            
            # Use actual bid/ask if available
            if 'bid' in quote_info and quote_info['bid'] > 0 and 'ask' in quote_info and quote_info['ask'] > 0:
                bid_price = float(quote_info['bid'])
                ask_price = float(quote_info['ask'])
                spread = ask_price - bid_price
                spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
                logger.debug(f"Using actual bid/ask: {bid_price}/{ask_price}")
                return timestamp, bid_price, ask_price, spread, spread_pct
            
            # Otherwise estimate bid/ask from the current price
            spread = current_price * 0.0025  # 0.25% of price
            bid_price = current_price - (spread / 2)
            ask_price = current_price + (spread / 2)
            spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
            
            logger.debug(f"Using estimated bid/ask: {bid_price}/{ask_price}")
            return timestamp, bid_price, ask_price, spread, spread_pct
            
        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance quote: {e}")
            return None
    
    def get_latest_quote(self):
        """
        Get the latest quote from Yahoo Finance.
        
        Returns:
            tuple: (timestamp, bid_price, ask_price, spread, spread_percentage)
        """
        return self.last_quote
    
    def add_quote_to_dataframe(self, quote_data):
        """
        Add a quote to the dataframe and maintain max_records limit.
        
        Args:
            quote_data: Tuple of (timestamp, bid_price, ask_price, spread, spread_pct)
        """
        if quote_data is None:
            return
        
        timestamp, bid_price, ask_price, spread, spread_pct = quote_data
        
        # Calculate mid price (average of bid and ask)
        mid_price = (bid_price + ask_price) / 2
        
        # Create a new row
        new_row = pd.DataFrame({
            'timestamp': [timestamp],
            'bid': [bid_price],
            'ask': [ask_price],
            'spread': [spread],
            'spread_pct': [spread_pct],
            'mid': [mid_price]
        })
        
        # Log the new quote for debugging
        logger.debug(f"Adding new quote: {timestamp}, bid=${bid_price:.2f}, ask=${ask_price:.2f}, mid=${mid_price:.2f}")
        
        # Append to dataframe
        self.quotes_df = pd.concat([self.quotes_df, new_row], ignore_index=True)
        
        # Trim to max_records
        if len(self.quotes_df) > self.max_records:
            self.quotes_df = self.quotes_df.iloc[-self.max_records:]
            
        # Calculate MACD if we have enough data
        self.calculate_macd()
    
    def calculate_macd(self):
        """
        Calculate MACD based on the mid-prices in the quotes dataframe.
        
        This method adds the following columns to the dataframe:
        - EMAfast: Fast EMA of mid prices
        - EMAslow: Slow EMA of mid prices
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
        
        # Calculate EMAs
        self.quotes_df['EMAfast'] = self.quotes_df['mid'].ewm(span=self.fast_window, adjust=False).mean()
        self.quotes_df['EMAslow'] = self.quotes_df['mid'].ewm(span=self.slow_window, adjust=False).mean()
        
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
    
    def get_macd_signal(self):
        """
        Get the current MACD trading signal based on the latest data.
        
        Returns:
            dict: A dictionary containing signal information:
            - signal: 1.0 for buy, -1.0 for sell, 0.0 for hold
            - position: Current position (1.0 for long, -1.0 for short, 0.0 for none)
            - macd_position: 'ABOVE' or 'BELOW'
            - crossover: True if MACD just crossed above signal line
            - crossunder: True if MACD just crossed below signal line
            - macd_value: Current MACD value
            - signal_value: Current signal line value
            - histogram: Current histogram value
        """
        if len(self.quotes_df) == 0 or 'MACD' not in self.quotes_df.columns:
            return {
                'signal': 0.0,
                'position': 0.0,
                'macd_position': None,
                'crossover': False,
                'crossunder': False,
                'macd_value': None,
                'signal_value': None,
                'histogram': None
            }
        
        # Get the latest values
        latest = self.quotes_df.iloc[-1]
        
        # Check for crossover/crossunder
        crossover = latest['crossover'] if 'crossover' in self.quotes_df.columns else False
        crossunder = latest['crossunder'] if 'crossunder' in self.quotes_df.columns else False
        
        # Determine signal
        signal = 0.0
        if crossover:
            signal = 1.0
            self.last_signal_time = latest['timestamp']
        elif crossunder:
            signal = -1.0
            self.last_signal_time = latest['timestamp']
        
        # Create result dictionary
        result = {
            'signal': signal,
            'position': 1.0 if latest['MACD_position'] == 'ABOVE' else -1.0 if latest['MACD_position'] == 'BELOW' else 0.0,
            'macd_position': latest['MACD_position'],
            'crossover': crossover,
            'crossunder': crossunder,
            'macd_value': latest['MACD'],
            'signal_value': latest['Signal'],
            'histogram': latest['Histogram'],
            'timestamp': latest['timestamp'],
            'mid_price': latest['mid']
        }
        
        # Log the signal if it's a buy or sell
        if signal != 0.0:
            action = "BUY" if signal > 0 else "SELL"
            logger.info(f"MACD Signal: {action} at ${latest['mid']:.2f}")
            logger.info(f"MACD: {latest['MACD']:.6f}, Signal: {latest['Signal']:.6f}, Histogram: {latest['Histogram']:.6f}")
        
        return result
        
    def display_quotes(self):
        """
        Display the latest quotes and MACD information in a formatted table.
        """
        if len(self.quotes_df) == 0:
            # Check if market is likely open
            now = datetime.now()  # Use local time
            is_weekday = now.weekday() < 5  # Monday to Friday
            hour = now.hour  # Use local hour directly
            
            if not is_weekday:
                logger.info("No quotes available - Market is closed (weekend).")
            elif hour < 4 or hour >= 20:  # Before 4 AM or after 8 PM local time
                logger.info("No quotes available - Market is closed (outside of extended hours).")
            elif hour < 9 or hour >= 16:  # Before 9 AM or after 4 PM local time
                logger.info("No quotes available - Regular market hours are closed, but extended hours may be active.")
            else:
                logger.info("No quotes available yet - Yahoo Finance connection may be experiencing issues.")
                
            # Print connection status
            logger.info(f"Yahoo Finance connection status: {'Connected' if self.connected else 'Disconnected'}")
            return
        
        # Get the latest quotes
        latest_quotes = self.quotes_df.tail(10).copy()
        
        # Format the timestamp - ensure all timestamps are timezone-naive
        latest_quotes['timestamp'] = latest_quotes['timestamp'].apply(lambda x: x.replace(tzinfo=None) if hasattr(x, 'tzinfo') else x)
        latest_quotes['time'] = latest_quotes['timestamp'].apply(lambda x: x.strftime('%H:%M:%S') if isinstance(x, datetime) else str(x))
        
        # Format the prices
        latest_quotes['bid'] = latest_quotes['bid'].map('${:.2f}'.format)
        latest_quotes['ask'] = latest_quotes['ask'].map('${:.2f}'.format)
        latest_quotes['mid'] = latest_quotes['mid'].map('${:.2f}'.format)
        latest_quotes['spread'] = latest_quotes['spread'].map('${:.4f}'.format)
        latest_quotes['spread_pct'] = latest_quotes['spread_pct'].map('{:.2f}%'.format)
        
        # Format MACD values if they exist
        if 'MACD' in latest_quotes.columns:
            latest_quotes['MACD'] = latest_quotes['MACD'].map('{:.6f}'.format)
            latest_quotes['Signal'] = latest_quotes['Signal'].map('{:.6f}'.format)
            latest_quotes['Histogram'] = latest_quotes['Histogram'].map('{:.6f}'.format)
            
            # Create a position indicator
            latest_quotes['Position'] = latest_quotes['MACD_position']
            
            # Create a signal indicator
            latest_quotes['Signal_Indicator'] = ''
            latest_quotes.loc[latest_quotes['crossover'] == True, 'Signal_Indicator'] = '↑ BUY'
            latest_quotes.loc[latest_quotes['crossunder'] == True, 'Signal_Indicator'] = '↓ SELL'
            
            # Display the table with MACD information
            print(tabulate(
                latest_quotes[['time', 'bid', 'ask', 'mid', 'MACD', 'Signal', 'Histogram', 'Position', 'Signal_Indicator']].iloc[::-1],
                headers='keys',
                tablefmt='pretty',
                showindex=False
            ))
            
            # Print connection status
            print(f"\nYahoo Finance connection status: {'Connected' if self.connected else 'Disconnected'}")
            print(f"Total quotes collected: {len(self.quotes_df)}")
            
            # Get the latest MACD signal
            macd_signal = self.get_macd_signal()
            
            # Display current signal
            if macd_signal['macd_position'] is not None:
                signal_str = "BUY" if macd_signal['signal'] > 0 else "SELL" if macd_signal['signal'] < 0 else "HOLD"
                position_str = "LONG" if macd_signal['position'] > 0 else "SHORT" if macd_signal['position'] < 0 else "NONE"
                
                print(f"\nCurrent MACD Signal: {signal_str}")
                print(f"Current Position: {position_str}")
                print(f"MACD Position: {macd_signal['macd_position']} signal line")
                if macd_signal['crossover']:
                    print(f"BULLISH SIGNAL: MACD just crossed ABOVE signal line!")
                if macd_signal['crossunder']:
                    print(f"BEARISH SIGNAL: MACD just crossed BELOW signal line!")
        else:
            # Display the table without MACD information
            print(tabulate(
                latest_quotes[['time', 'bid', 'ask', 'mid', 'spread', 'spread_pct']].iloc[::-1],
                headers='keys',
                tablefmt='pretty',
                showindex=False
            ))
            
            # Print connection status
            print(f"\nYahoo Finance connection status: {'Connected' if self.connected else 'Disconnected'}")
            print(f"Total quotes collected: {len(self.quotes_df)}")
            print("MACD calculation pending - waiting for more data...")
    
    def save_to_csv(self, filename=None):
        """
        Save the current quotes to a CSV file.
        
        Args:
            filename: Optional filename, defaults to symbol_quotes_YYYYMMDD.csv
        """
        if self.quotes_df.empty:
            logger.info("No quotes to save.")
            return
        
        if filename is None:
            today = datetime.now().strftime('%Y%m%d')
            filename = f"{self.symbol}_yahoo_quotes_{today}.csv"
        
        try:
            self.quotes_df.to_csv(filename, index=False)
            logger.info(f"Quotes saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving quotes to CSV: {e}")
    
    def _is_likely_extended_hours(self):
        """
        Check if we're likely in extended trading hours based on the current time.
        
        Returns:
            bool: True if we're likely in extended hours, False otherwise
        """
        now = datetime.now()  # Local time
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check the hour
        hour = now.hour
        
        # Pre-market: 4:00 AM - 9:30 AM
        # Regular market: 9:30 AM - 4:00 PM
        # After-hours: 4:00 PM - 8:00 PM
        if (hour >= 4 and hour < 9) or (hour == 9 and now.minute < 30):  # Pre-market
            return True
        elif (hour >= 16 and hour < 20):  # After-hours
            return True
        elif (hour >= 9 and hour < 16):  # Regular market hours
            return False
        else:  # Outside of all trading hours
            return False
    
    def close(self):
        """
        Close the Yahoo Finance connection and stop the fetching thread.
        """
        logger.info("Closing Yahoo Finance quote monitor...")
        self.stop_event.set()
        if self.fetch_thread and self.fetch_thread.is_alive():
            self.fetch_thread.join(timeout=2)
        logger.info("Yahoo Finance quote monitor closed")

# Create an alias for compatibility with the existing system
EnhancedQuoteMonitor = YahooQuoteMonitor

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Yahoo Finance real-time stock quote monitor")
    
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
    
    # Create the quote monitor with Yahoo Finance support
    monitor = YahooQuoteMonitor(
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
        logger.info("Quote monitor stopped by user")
        
        # Close the monitor
        monitor.close()
        
        # Save the quotes to CSV before exiting
        monitor.save_to_csv()
