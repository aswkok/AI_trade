#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Enhanced Quote Monitor for MACD Trading System

This is an enhanced version of the quote monitor that uses WebSockets for real-time
data streaming from Alpaca, providing more reliable and up-to-date quote information.
"""

import os
import time
import json
import logging
import argparse
import threading
import pandas as pd
import numpy as np
import websocket
from datetime import datetime, timezone
from dotenv import load_dotenv
from tabulate import tabulate
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnhancedQuoteMonitor:
    """
    Enhanced monitor for real-time bid and ask prices using WebSocket streaming.
    
    This class connects to Alpaca's WebSocket API to receive real-time quotes,
    calculates MACD indicators, and provides trading signals.
    """
    
    def __init__(self, symbol, max_records=200, interval_seconds=60, fast_window=13, slow_window=21, signal_window=9):
        """
        Initialize the quote monitor with WebSocket support.
        
        Args:
            symbol: Stock symbol to monitor
            max_records: Maximum number of records to keep in memory
            interval_seconds: Interval between display updates (WebSocket data comes in real-time)
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
        
        # Initialize REST clients (still useful for account info, etc.)
        self.trading_client = TradingClient(self.api_key, self.api_secret, paper=True)
        self.data_client = StockHistoricalDataClient(self.api_key, self.api_secret)
        
        # Monitor settings
        self.symbol = symbol.upper()  # Ensure uppercase for Alpaca API
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
        
        # WebSocket connection
        self.ws = None
        self.ws_thread = None
        self.connected = False
        self.last_quote = None
        
        # WebSocket URLs
        self.ws_url = "wss://stream.data.alpaca.markets/v2/iex"
        
        # Initialize WebSocket connection
        self._init_websocket()
        
        logger.info(f"Enhanced Quote Monitor initialized for {symbol} using WebSocket streaming")
        logger.info(f"API Key found, starts with: {self.api_key[:4]}...")
        logger.info(f"Display update interval: {interval_seconds} seconds")
        logger.info(f"Maximum records: {max_records}")
        logger.info(f"MACD Parameters: Fast={fast_window}, Slow={slow_window}, Signal={signal_window}")
    
    def _init_websocket(self):
        """
        Initialize the WebSocket connection to Alpaca's streaming API.
        """
        # Define WebSocket callbacks
        def on_open(ws):
            self.connected = True
            logger.info("WebSocket connection opened")
            # Authentication message
            auth_message = {
                "action": "auth",
                "key": self.api_key,
                "secret": self.api_secret
            }
            ws.send(json.dumps(auth_message))
            
            # Subscribe to quotes for our symbol
            subscribe_message = {
                "action": "subscribe",
                "quotes": [self.symbol]
            }
            ws.send(json.dumps(subscribe_message))
            logger.info(f"Subscribed to quotes for {self.symbol}")
        
        def on_message(ws, message):
            data = json.loads(message)
            
            # Handle different message types
            if isinstance(data, list):
                for msg in data:
                    self._process_message(msg)
            else:
                self._process_message(data)
        
        def on_error(ws, error):
            logger.error(f"WebSocket error: {error}")
            self.connected = False
            # Schedule reconnection
            self._schedule_reconnect()
        
        def on_close(ws, close_status_code, close_msg):
            logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")
            self.connected = False
            # Schedule reconnection
            self._schedule_reconnect()
        
        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(self.ws_url,
                                        on_open=on_open,
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close)
        
        # Start WebSocket in a separate thread
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True  # Thread will exit when main program exits
        self.ws_thread.start()
    
    def _schedule_reconnect(self):
        """
        Schedule a reconnection attempt after a short delay.
        """
        if not self.connected:
            logger.info("Scheduling WebSocket reconnection in 5 seconds...")
            reconnect_thread = threading.Thread(target=self._delayed_reconnect)
            reconnect_thread.daemon = True
            reconnect_thread.start()
    
    def _delayed_reconnect(self):
        """
        Wait a few seconds and then attempt to reconnect the WebSocket.
        """
        time.sleep(5)  # Wait 5 seconds before reconnecting
        logger.info("Attempting to reconnect WebSocket...")
        
        # Close existing connection if it exists
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        
        # Initialize a new connection
        self._init_websocket()
    
    def _process_message(self, msg):
        """
        Process incoming WebSocket messages.
        
        Args:
            msg: Message from WebSocket
        """
        try:
            # Check if it's a quote message
            if msg.get('T') == 'q' and msg.get('S') == self.symbol:
                # Extract quote data
                timestamp = datetime.fromtimestamp(msg.get('t') / 1e9, tz=timezone.utc)  # Convert nanoseconds to seconds
                bid_price = float(msg.get('bp', 0))
                ask_price = float(msg.get('ap', 0))
                
                # Calculate spread
                spread = ask_price - bid_price
                spread_pct = (spread / bid_price) * 100 if bid_price > 0 else 0
                
                # Store as the latest quote
                self.last_quote = (timestamp, bid_price, ask_price, spread, spread_pct)
                
                # Add to dataframe
                self.add_quote_to_dataframe(self.last_quote)
                
                # Log at debug level to avoid flooding logs
                logger.debug(f"Quote received: {self.symbol} - Bid: {bid_price}, Ask: {ask_price}")
            
            # Handle authentication response
            elif msg.get('T') == 'success' and msg.get('msg') == 'authenticated':
                logger.info("Successfully authenticated with Alpaca WebSocket API")
            
            # Handle subscription response
            elif msg.get('T') == 'subscription':
                logger.info(f"Subscription status: {msg}")
        
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def get_latest_quote(self):
        """
        Get the latest quote from WebSocket data.
        
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
        - MACD_position: 'ABOVE' or 'BELOW' indicating MACD position relative to signal line
        - crossover: True when MACD crosses above signal line
        - crossunder: True when MACD crosses below signal line
        """
        # Check if we have enough data
        warmup_period = max(self.slow_window * 3, self.fast_window * 3) + self.signal_window
        if len(self.quotes_df) < warmup_period:
            logger.info(f"Not enough data for reliable MACD calculation. Have {len(self.quotes_df)} records, need {warmup_period}.")
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
            latest = self.quotes_df.iloc[-1]
            self.last_macd_position = latest['MACD_position']
            
            # Log the current MACD position
            logger.debug(f"Current MACD: {latest['MACD']:.6f}, Signal: {latest['Signal']:.6f}, Position: {self.last_macd_position}")
    
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
        
        # Check for crossover/crossunder - handle potential DataFrame/Series values
        if 'crossover' in self.quotes_df.columns:
            crossover_val = latest['crossover']
            # Handle different types to avoid ambiguity
            if isinstance(crossover_val, (bool, int, float)):
                crossover = bool(crossover_val)
            elif hasattr(crossover_val, 'item'):
                # For pandas Series or numpy arrays
                crossover = bool(crossover_val.item())
            else:
                logger.warning(f"Unexpected crossover type: {type(crossover_val)}, using False")
                crossover = False
        else:
            crossover = False
            
        if 'crossunder' in self.quotes_df.columns:
            crossunder_val = latest['crossunder']
            # Handle different types to avoid ambiguity
            if isinstance(crossunder_val, (bool, int, float)):
                crossunder = bool(crossunder_val)
            elif hasattr(crossunder_val, 'item'):
                # For pandas Series or numpy arrays
                crossunder = bool(crossunder_val.item())
            else:
                logger.warning(f"Unexpected crossunder type: {type(crossunder_val)}, using False")
                crossunder = False
        else:
            crossunder = False
        
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
            now = datetime.now(timezone.utc)
            is_weekday = now.weekday() < 5  # Monday to Friday
            hour_et = (now.hour - 4) % 24  # Convert UTC to ET (approximation)
            
            if not is_weekday:
                logger.info("No quotes available - Market is closed (weekend).")
            elif hour_et < 4 or hour_et >= 20:  # Before 4 AM ET or after 8 PM ET
                logger.info("No quotes available - Market is closed (outside of extended hours).")
            elif hour_et < 9 or hour_et >= 16:  # Before 9:30 AM ET or after 4 PM ET
                logger.info("No quotes available - Regular market hours are closed, but extended hours may be active.")
            else:
                logger.info("No quotes available yet - WebSocket is connected but no data received.")
                
            # Print connection status
            logger.info(f"WebSocket connection status: {'Connected' if self.connected else 'Disconnected'}")
            return
        
        # Get the latest quotes
        latest_quotes = self.quotes_df.tail(10).copy()
        
        # Format the timestamp
        latest_quotes['time'] = latest_quotes['timestamp'].dt.strftime('%H:%M:%S')
        
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
            print(f"\nWebSocket connection status: {'Connected' if self.connected else 'Disconnected'}")
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
            print(f"\nWebSocket connection status: {'Connected' if self.connected else 'Disconnected'}")
            print(f"Total quotes collected: {len(self.quotes_df)}")
            print("MACD calculation pending - waiting for more data...")
        
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

# This class is a drop-in replacement for the original QuoteMonitor
# Just import this and use EnhancedQuoteMonitor instead of QuoteMonitor
QuoteMonitor = EnhancedQuoteMonitor

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Enhanced real-time stock quote monitor using WebSockets")
    
    parser.add_argument(
        "--symbol", 
        type=str, 
        default="NVDA",
        help="Stock symbol to monitor (default: NVDA)"
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        default=5,
        help="Interval between display updates in seconds (default: 5)"
    )
    
    parser.add_argument(
        "--max-records", 
        type=int, 
        default=200,
        help="Maximum number of records to keep in memory (default: 200)"
    )
    
    args = parser.parse_args()
    
    # Create the quote monitor with WebSocket support
    monitor = EnhancedQuoteMonitor(
        symbol=args.symbol,
        max_records=args.max_records,
        interval_seconds=args.interval
    )
    
    # Give WebSocket time to connect and authenticate
    logger.info("Waiting for WebSocket connection to establish...")
    time.sleep(3)
    
    # Run the monitor - WebSocket runs in background thread
    try:
        while True:
            # Display the current quotes (WebSocket updates happen in background)
            monitor.display_quotes()
            
            # Wait for the next display update
            logger.info(f"Waiting {args.interval} seconds until next display update...")
            time.sleep(args.interval)
    
    except KeyboardInterrupt:
        logger.info("Quote monitor stopped by user")
        
        # Close WebSocket connection
        if monitor.ws:
            monitor.ws.close()
            logger.info("WebSocket connection closed")
        
        # Save the quotes to CSV before exiting
        monitor.save_to_csv()