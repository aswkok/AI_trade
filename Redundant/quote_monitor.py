#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Quote Monitor - Real-time Bid/Ask Price Tracker

This script fetches real-time bid and ask prices for a specified stock using
Alpaca API, stores the data in memory, and provides live monitoring capabilities.
"""

import os
import time
import logging
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class QuoteMonitor:
    """Monitor real-time bid and ask prices for a specified stock.
    
    This class fetches real-time quotes and maintains a rolling window of the most recent
    quotes. It can be used as a data source for technical indicators like MACD.
    """
    
    def __init__(self, symbol, max_records=100, interval_seconds=60, fast_window=13, slow_window=21, signal_window=9):
        """
        Initialize the quote monitor.
        
        Args:
            symbol: Stock symbol to monitor
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
        
        # Monitor settings
        self.symbol = symbol
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
        
        logger.info(f"Quote Monitor initialized for {symbol}")
        logger.info(f"API Key found, starts with: {self.api_key[:4]}...")
        logger.info(f"Monitoring interval: {interval_seconds} seconds")
        logger.info(f"Maximum records: {max_records}")
        logger.info(f"MACD Parameters: Fast={fast_window}, Slow={slow_window}, Signal={signal_window}")
    
    def get_latest_quote(self):
        """
        Fetch the latest quote for the symbol.
        
        Returns:
            tuple: (timestamp, bid_price, ask_price, spread, spread_percentage)
        """
        try:
            # Create the quote request
            quote_request = StockLatestQuoteRequest(symbol_or_symbols=[self.symbol])
            
            # Get the latest quote
            quotes = self.data_client.get_stock_latest_quote(quote_request)
            
            if self.symbol in quotes:
                quote = quotes[self.symbol]
                timestamp = quote.timestamp
                bid_price = float(quote.bid_price)
                ask_price = float(quote.ask_price)
                
                # Calculate spread
                spread = ask_price - bid_price
                spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
                
                return timestamp, bid_price, ask_price, spread, spread_pct
            else:
                logger.warning(f"No quote data available for {self.symbol}")
                return None
        except Exception as e:
            logger.error(f"Error fetching quote: {e}")
            return None
    
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
        - MACD_position: 'ABOVE' or 'BELOW' indicating MACD position relative to signal line
        - crossover: True when MACD crosses above signal line
        - crossunder: True when MACD crosses below signal line
        """
        # Check if we have enough data
        if len(self.quotes_df) < max(self.slow_window * 3, self.fast_window * 3) + self.signal_window:
            logger.info(f"Not enough data for reliable MACD calculation. Have {len(self.quotes_df)} records.")
            return
        
        # Calculate MACD components using standard method with mid prices
        self.quotes_df['EMAfast'] = self.quotes_df['mid'].ewm(span=self.fast_window, adjust=False).mean()
        self.quotes_df['EMAslow'] = self.quotes_df['mid'].ewm(span=self.slow_window, adjust=False).mean()
        self.quotes_df['MACD'] = self.quotes_df['EMAfast'] - self.quotes_df['EMAslow']
        self.quotes_df['Signal'] = self.quotes_df['MACD'].ewm(span=self.signal_window, adjust=False).mean()
        self.quotes_df['Histogram'] = self.quotes_df['MACD'] - self.quotes_df['Signal']
        
        # Determine MACD position (above or below signal line)
        self.quotes_df['MACD_position'] = np.where(self.quotes_df['MACD'] > self.quotes_df['Signal'], 'ABOVE', 'BELOW')
        
        # Calculate previous values for crossover detection
        self.quotes_df['MACD_prev'] = self.quotes_df['MACD'].shift(1)
        self.quotes_df['Signal_prev'] = self.quotes_df['Signal'].shift(1)
        
        # Detect crossovers and crossunders
        self.quotes_df['crossover'] = (self.quotes_df['MACD'] > self.quotes_df['Signal']) & \
                                     (self.quotes_df['MACD_prev'] <= self.quotes_df['Signal_prev'])
        self.quotes_df['crossunder'] = (self.quotes_df['MACD'] < self.quotes_df['Signal']) & \
                                      (self.quotes_df['MACD_prev'] >= self.quotes_df['Signal_prev'])
        
        # Update the last MACD position
        if len(self.quotes_df) > 0:
            self.last_macd_position = self.quotes_df['MACD_position'].iloc[-1]
    
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
        """Display the current quotes in a formatted table."""
        if self.quotes_df.empty:
            logger.info("No quotes available yet.")
            return
        
        # Format the dataframe for display
        display_df = self.quotes_df.copy()
        
        # Convert timestamp to local time string
        display_df['timestamp'] = display_df['timestamp'].apply(
            lambda x: x.strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # Format numeric columns
        display_df['bid'] = display_df['bid'].apply(lambda x: f"${x:.2f}")
        display_df['ask'] = display_df['ask'].apply(lambda x: f"${x:.2f}")
        display_df['mid'] = display_df['mid'].apply(lambda x: f"${x:.2f}")
        display_df['spread'] = display_df['spread'].apply(lambda x: f"${x:.2f}")
        display_df['spread_pct'] = display_df['spread_pct'].apply(lambda x: f"{x:.2f}%")
        
        # Display the last 5 records of quote data
        last_n = min(5, len(display_df))
        quote_columns = ['timestamp', 'bid', 'ask', 'mid', 'spread', 'spread_pct']
        quote_table = tabulate(
            display_df.tail(last_n)[quote_columns], 
            headers='keys', 
            tablefmt='pretty',
            showindex=False
        )
        
        print("\n" + "=" * 80)
        print(f"Latest {last_n} quotes for {self.symbol} (Total records: {len(self.quotes_df)})")
        print("=" * 80)
        print(quote_table)
        
        # Display MACD information if available
        if 'MACD' in self.quotes_df.columns:
            # Get the latest MACD signal
            macd_signal = self.get_macd_signal()
            
            # Display MACD table
            if len(display_df) > 0 and 'MACD' in display_df.columns:
                # Format MACD columns
                if 'MACD' in display_df.columns:
                    display_df['MACD'] = display_df['MACD'].apply(lambda x: f"{x:.6f}")
                if 'Signal' in display_df.columns:
                    display_df['Signal'] = display_df['Signal'].apply(lambda x: f"{x:.6f}")
                if 'Histogram' in display_df.columns:
                    display_df['Histogram'] = display_df['Histogram'].apply(lambda x: f"{x:.6f}")
                
                # Display the last 5 records of MACD data
                macd_columns = ['timestamp', 'mid', 'MACD', 'Signal', 'Histogram', 'MACD_position']
                macd_columns = [col for col in macd_columns if col in display_df.columns]
                
                if macd_columns:
                    macd_table = tabulate(
                        display_df.tail(last_n)[macd_columns], 
                        headers='keys', 
                        tablefmt='pretty',
                        showindex=False
                    )
                    
                    print("\n" + "=" * 80)
                    print(f"MACD Analysis for {self.symbol}")
                    print("=" * 80)
                    print(macd_table)
                    
                    # Display current signal
                    if macd_signal['macd_position'] is not None:
                        signal_str = "BUY" if macd_signal['signal'] > 0 else "SELL" if macd_signal['signal'] < 0 else "HOLD"
                        position_str = "LONG" if macd_signal['position'] > 0 else "SHORT" if macd_signal['position'] < 0 else "NONE"
                        
                        print("\n" + "=" * 80)
                        print(f"Current MACD Signal: {signal_str}")
                        print(f"Current Position: {position_str}")
                        print(f"MACD Position: {macd_signal['macd_position']} signal line")
                        if macd_signal['crossover']:
                            print(f"BULLISH SIGNAL: MACD just crossed ABOVE signal line!")
                        if macd_signal['crossunder']:
                            print(f"BEARISH SIGNAL: MACD just crossed BELOW signal line!")
        
        print("=" * 80 + "\n")
    
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
            filename = f"{self.symbol}_quotes_{today}.csv"
        
        try:
            self.quotes_df.to_csv(filename, index=False)
            logger.info(f"Quotes saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving quotes to CSV: {e}")
    
    def run(self):
        """Run the quote monitor continuously."""
        logger.info(f"Starting quote monitor for {self.symbol}")
        logger.info(f"Press Ctrl+C to stop monitoring")
        
        try:
            while True:
                # Get the latest quote
                quote_data = self.get_latest_quote()
                
                if quote_data:
                    # Add to dataframe
                    self.add_quote_to_dataframe(quote_data)
                    
                    # Display the quotes
                    self.display_quotes()
                
                # Wait for the next interval
                logger.info(f"Waiting {self.interval_seconds} seconds until next update...")
                time.sleep(self.interval_seconds)
        
        except KeyboardInterrupt:
            logger.info("Quote monitor stopped by user")
            
            # Save the quotes to CSV before exiting
            self.save_to_csv()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Real-time stock quote monitor")
    
    parser.add_argument(
        "--symbol", 
        type=str, 
        default="AAPL",
        help="Stock symbol to monitor (default: AAPL)"
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
    
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Create and run the quote monitor
    monitor = QuoteMonitor(
        symbol=args.symbol,
        max_records=args.max_records,
        interval_seconds=args.interval
    )
    
    # Run the monitor
    monitor.run()
