#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Quote Monitor Service

This module implements a standalone service that continuously collects market data
through the quote monitor, independent of any trading logic. It allows for:
- Running during extended hours
- Warming up and collecting quote data in advance
- Providing a data source for trading systems when they're ready to execute
"""

import os
import sys
import time
import logging
import argparse
import signal
import json
import threading
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv

# Import the quote monitor
from quote_monitor_selector import QuoteMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("quote_monitor_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class QuoteMonitorService:
    """
    Service that runs quote monitors for multiple symbols independently.
    
    This class handles:
    - Continuous data collection for multiple symbols
    - Extended hours monitoring
    - Data persistence and management
    - Providing data access to trading systems
    """
    
    def __init__(self, symbols, interval_seconds=5, max_records=500,
                 fast_window=13, slow_window=21, signal_window=9,
                 include_extended_hours=True, data_dir="quote_data"):
        """
        Initialize the quote monitor service.
        
        Args:
            symbols: List of symbols to monitor
            interval_seconds: Interval between data fetches in seconds
            max_records: Maximum number of records to keep in memory
            fast_window: Fast EMA window for MACD calculation
            slow_window: Slow EMA window for MACD calculation
            signal_window: Signal line window for MACD calculation
            include_extended_hours: Whether to include extended hours data
            data_dir: Directory to store quote data
        """
        # Load environment variables
        load_dotenv()
        
        # Store configuration
        self.symbols = symbols if isinstance(symbols, list) else [symbols]
        self.interval_seconds = interval_seconds
        self.max_records = max_records
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.include_extended_hours = include_extended_hours
        self.data_dir = data_dir
        
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # System state
        self.is_running = False
        self.stop_event = threading.Event()
        self.monitors = {}  # Dictionary of quote monitors by symbol
        self.monitor_status = {}  # Status of each monitor
        self.last_save_time = datetime.now()
        self.save_interval = 300  # Save data every 5 minutes
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        # Initialize the quote monitors
        self._initialize_monitors()
        
        logger.info(f"Quote Monitor Service initialized for symbols: {self.symbols}")
        logger.info(f"Data collection interval: {interval_seconds} seconds")
        logger.info(f"Extended hours data: {'Enabled' if include_extended_hours else 'Disabled'}")
    
    def _initialize_monitors(self):
        """Initialize quote monitors for each symbol."""
        for symbol in self.symbols:
            try:
                logger.info(f"Initializing quote monitor for {symbol}")
                
                # Create the quote monitor
                self.monitors[symbol] = QuoteMonitor(
                    symbol=symbol,
                    max_records=self.max_records,
                    interval_seconds=self.interval_seconds,
                    fast_window=self.fast_window,
                    slow_window=self.slow_window,
                    signal_window=self.signal_window
                )
                
                # Set initial status
                self.monitor_status[symbol] = {
                    'initialized': True,
                    'start_time': datetime.now(),
                    'quotes_collected': 0,
                    'last_update': None,
                    'errors': 0,
                    'has_macd_data': False
                }
                
                logger.info(f"Quote monitor for {symbol} initialized successfully")
                
            except Exception as e:
                logger.error(f"Error initializing quote monitor for {symbol}: {e}")
                self.monitor_status[symbol] = {
                    'initialized': False,
                    'error': str(e)
                }
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received, stopping quote monitor service...")
        self.stop_event.set()
        self.is_running = False
    
    def save_quote_data(self, symbol=None):
        """
        Save the current quote data to CSV files.
        
        Args:
            symbol: Optional symbol to save data for. If None, save all symbols.
        """
        symbols_to_save = [symbol] if symbol else self.symbols
        
        for sym in symbols_to_save:
            if sym in self.monitors and not self.monitors[sym].quotes_df.empty:
                try:
                    # Create a filename with timestamp
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{self.data_dir}/{sym}_quotes_{timestamp}.csv"
                    
                    # Save to CSV
                    self.monitors[sym].quotes_df.to_csv(filename, index=False)
                    logger.info(f"Quote data for {sym} saved to {filename}")
                    
                    # Update status
                    self.monitor_status[sym]['last_save'] = datetime.now()
                    self.monitor_status[sym]['quotes_collected'] = len(self.monitors[sym].quotes_df)
                    
                except Exception as e:
                    logger.error(f"Error saving quote data for {sym}: {e}")
                    self.monitor_status[sym]['errors'] += 1
    
    def update_monitor_status(self):
        """Update the status of all quote monitors."""
        for symbol in self.symbols:
            if symbol in self.monitors:
                monitor = self.monitors[symbol]
                
                # Update status
                self.monitor_status[symbol]['last_update'] = datetime.now()
                self.monitor_status[symbol]['quotes_collected'] = len(monitor.quotes_df)
                
                # Check if we have enough data for MACD calculation
                min_periods = self.slow_window + self.signal_window
                has_macd = len(monitor.quotes_df) >= min_periods
                
                self.monitor_status[symbol]['has_macd_data'] = has_macd
                
                if has_macd and not self.monitor_status[symbol].get('macd_ready_time'):
                    self.monitor_status[symbol]['macd_ready_time'] = datetime.now()
                    logger.info(f"MACD data ready for {symbol} after collecting {len(monitor.quotes_df)} quotes")
    
    def display_status(self):
        """Display the current status of all quote monitors."""
        print("\n" + "=" * 80)
        print(f"Quote Monitor Service Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        for symbol in self.symbols:
            status = self.monitor_status.get(symbol, {})
            
            if not status.get('initialized', False):
                print(f"{symbol}: Not initialized - {status.get('error', 'Unknown error')}")
                continue
            
            quotes_collected = status.get('quotes_collected', 0)
            has_macd = status.get('has_macd_data', False)
            last_update = status.get('last_update')
            
            print(f"{symbol}: Quotes collected: {quotes_collected}, MACD data ready: {has_macd}")
            
            if last_update:
                time_diff = (datetime.now() - last_update).total_seconds()
                print(f"  Last update: {last_update.strftime('%H:%M:%S')} ({time_diff:.1f} seconds ago)")
            
            # If we have a monitor, display the latest quote
            if symbol in self.monitors and not self.monitors[symbol].quotes_df.empty:
                latest = self.monitors[symbol].quotes_df.iloc[-1]
                print(f"  Latest quote: Bid: ${latest.get('bid', 0):.2f}, Ask: ${latest.get('ask', 0):.2f}")
                
                # If MACD data is available, show it
                if has_macd:
                    macd_signal = self.monitors[symbol].get_macd_signal()
                    signal_type = "BUY" if macd_signal.get('signal', 0) > 0 else "SELL" if macd_signal.get('signal', 0) < 0 else "HOLD"
                    print(f"  MACD signal: {signal_type}, MACD: {macd_signal.get('macd_value', 0):.4f}, Signal: {macd_signal.get('signal_value', 0):.4f}")
            
            print("-" * 80)
    
    def get_monitor(self, symbol):
        """
        Get the quote monitor for a specific symbol.
        
        Args:
            symbol: Symbol to get the monitor for
            
        Returns:
            QuoteMonitor instance or None if not found
        """
        return self.monitors.get(symbol)
    
    def is_data_ready(self, symbol):
        """
        Check if the quote data for a symbol is ready for trading.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            bool: True if data is ready, False otherwise
        """
        status = self.monitor_status.get(symbol, {})
        return status.get('has_macd_data', False)
    
    def run(self):
        """
        Run the quote monitor service.
        
        This method will run indefinitely until stopped, continuously
        collecting quote data for all configured symbols.
        """
        logger.info("Starting Quote Monitor Service")
        self.is_running = True
        
        try:
            # Main service loop
            while self.is_running and not self.stop_event.is_set():
                try:
                    # Update monitor status
                    self.update_monitor_status()
                    
                    # Display status periodically
                    self.display_status()
                    
                    # Save data periodically
                    if (datetime.now() - self.last_save_time).total_seconds() >= self.save_interval:
                        self.save_quote_data()
                        self.last_save_time = datetime.now()
                    
                    # Sleep for a bit
                    time.sleep(self.interval_seconds)
                    
                except Exception as e:
                    logger.error(f"Error in main service loop: {e}")
                    time.sleep(5)  # Wait a bit before retrying
            
        except KeyboardInterrupt:
            logger.info("Quote Monitor Service stopped by user")
            
        finally:
            # Save final data
            self.save_quote_data()
            
            # Close all monitors
            for symbol, monitor in self.monitors.items():
                try:
                    logger.info(f"Closing quote monitor for {symbol}")
                    monitor.close()
                except Exception as e:
                    logger.error(f"Error closing quote monitor for {symbol}: {e}")
            
            logger.info("Quote Monitor Service stopped")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Quote Monitor Service")
    
    parser.add_argument(
        "--symbols", 
        type=str,
        nargs='+',
        default=["SPY"],
        help="Symbols to monitor (space-separated, default: SPY)"
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        default=5,
        help="Data collection interval in seconds (default: 5)"
    )
    
    parser.add_argument(
        "--max-records", 
        type=int, 
        default=500,
        help="Maximum number of records to keep in memory (default: 500)"
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
        "--no-extended-hours",
        action="store_true",
        help="Disable extended hours data collection"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default="quote_data",
        help="Directory to store quote data (default: quote_data)"
    )
    
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a daemon process in the background"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # If daemon mode is requested, fork the process
    if args.daemon:
        try:
            # First fork
            pid = os.fork()
            if pid > 0:
                # Exit first parent
                sys.exit(0)
        except OSError as e:
            logger.error(f"Fork #1 failed: {e}")
            sys.exit(1)
            
        # Decouple from parent environment
        os.chdir('/')
        os.setsid()
        os.umask(0)
        
        try:
            # Second fork
            pid = os.fork()
            if pid > 0:
                # Exit second parent
                sys.exit(0)
        except OSError as e:
            logger.error(f"Fork #2 failed: {e}")
            sys.exit(1)
            
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = open(os.devnull, 'r')
        so = open(os.devnull, 'a+')
        se = open(os.devnull, 'a+')
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
        
        # Write PID file
        pid = str(os.getpid())
        with open('quote_monitor.pid', 'w') as f:
            f.write(pid)
        
        logger.info(f"Daemon started with PID {pid}")
    
    # Create and run the quote monitor service
    service = QuoteMonitorService(
        symbols=args.symbols,
        interval_seconds=args.interval,
        max_records=args.max_records,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        signal_window=args.signal_window,
        include_extended_hours=not args.no_extended_hours,
        data_dir=args.data_dir
    )
    
    # Run the service
    service.run()
