#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Console Display for MACD Options Trading System

This module provides a simple console-based display for the MACD Options Trading System
when the curses-based real-time display is turned off.
"""

import os
import sys
import time
import logging
from datetime import datetime
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConsoleDisplay:
    """Simple console-based display for the MACD Options Trading System."""
    
    def __init__(self, update_interval=5):
        """
        Initialize the console display.
        
        Args:
            update_interval: Update interval in seconds
        """
        self.update_interval = update_interval
        self.is_running = False
        self.traders = {}
        self.symbols = []
        self.stats = {}
        self.last_update = datetime.now()
        
    def register_trader(self, symbol, trader):
        """
        Register a trader for a symbol.
        
        Args:
            symbol: Symbol to register
            trader: Trader instance
        """
        self.traders[symbol] = trader
        if symbol not in self.symbols:
            self.symbols.append(symbol)
            
    def register_stats(self, stats):
        """
        Register statistics.
        
        Args:
            stats: Statistics dictionary
        """
        self.stats = stats
        
    def update(self):
        """Update the console display."""
        # Clear the terminal
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Print header with bold text and color
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("\033[1;36m" + "="*80 + "\033[0m")
        print("\033[1;36m" + f" MACD OPTIONS TRADING SYSTEM - CONSOLE MODE - {current_time} " + "\033[0m")
        print("\033[1;36m" + "="*80 + "\033[0m")
        
        # Print system status with color coding
        uptime = (datetime.now() - self.stats.get('start_time', datetime.now())).total_seconds() / 3600
        market_status = "\033[1;32mOPEN\033[0m" if self._is_market_open() else "\033[1;31mCLOSED\033[0m"
        print(f"\033[1m System Status:\033[0m Running | \033[1mUptime:\033[0m {uptime:.1f} hours | \033[1mMarket:\033[0m {market_status}")
        print(f"\033[1m Trades:\033[0m {self.stats.get('total_trades', 0)} | \033[1mErrors:\033[0m {self.stats.get('errors', 0)} | \033[1mRestarts:\033[0m {self.stats.get('restarts', 0)}")
        print("\033[1;36m" + "-"*80 + "\033[0m")
        
        # Print symbols being monitored
        print(f"\033[1m Monitoring {len(self.symbols)} symbols:\033[0m {', '.join(self.symbols)}")
        print("\033[1;36m" + "-"*80 + "\033[0m")
        
        # Print data collection status for each symbol
        print("\033[1;33m DATA COLLECTION STATUS \033[0m")
        for symbol, trader in self.traders.items():
            if hasattr(trader, 'quote_monitor') and hasattr(trader.quote_monitor, 'quotes_df'):
                quotes_count = len(trader.quote_monitor.quotes_df)
                last_update = trader.quote_monitor.last_update.strftime("%H:%M:%S") if hasattr(trader.quote_monitor, 'last_update') else "N/A"
                print(f"\033[1m {symbol}:\033[0m {quotes_count} quotes collected | Last update: {last_update}")
                
                # Print latest quote if available
                if quotes_count > 0:
                    try:
                        latest_quote = trader.quote_monitor.quotes_df.iloc[-1]
                        print(f"   Latest: Bid=\033[1;34m${latest_quote.get('bid', 0):.2f}\033[0m, Ask=\033[1;34m${latest_quote.get('ask', 0):.2f}\033[0m, Mid=\033[1;34m${latest_quote.get('mid', 0):.2f}\033[0m")
                        
                        # Print MACD information with color coding
                        if 'MACD' in latest_quote and 'Signal' in latest_quote:
                            macd = latest_quote.get('MACD', 0)
                            signal = latest_quote.get('Signal', 0)
                            hist = latest_quote.get('Histogram', 0)
                            
                            # Color code based on values
                            macd_color = "\033[1;32m" if macd > 0 else "\033[1;31m"
                            hist_color = "\033[1;32m" if hist > 0 else "\033[1;31m"
                            
                            print(f"   MACD: {macd_color}{macd:.4f}\033[0m, Signal: \033[1;34m{signal:.4f}\033[0m, Hist: {hist_color}{hist:.4f}\033[0m")
                            
                            # Add position indicator
                            if 'MACD_position' in latest_quote:
                                position = latest_quote.get('MACD_position')
                                position_color = "\033[1;32m" if position == "ABOVE" else "\033[1;31m"
                                print(f"   Position: {position_color}{position}\033[0m")
                    except Exception as e:
                        print(f"   \033[1;31mError retrieving latest quote: {e}\033[0m")
        print("\033[1;36m" + "-"*80 + "\033[0m")
        
        # Print command help with better formatting
        print("\033[1;33m AVAILABLE COMMANDS \033[0m")
        print("  \033[1mpython toggle_display.py --on\033[0m     : Turn real-time display ON")
        print("  \033[1mpython toggle_display.py --off\033[0m    : Turn real-time display OFF")
        print("  \033[1mpython toggle_display.py --status\033[0m : Show display status")
        print("  \033[1mCtrl+C\033[0m                            : Exit program")
        print("\033[1;36m" + "="*80 + "\033[0m")
        print()
        
        # Update last update time
        self.last_update = datetime.now()
        
    def _is_market_open(self):
        """Check if the market is open."""
        # Try to get market status from any trader
        for symbol, trader in self.traders.items():
            if hasattr(trader, 'is_market_open'):
                return trader.is_market_open()
        return False
        
    def start(self):
        """Start the console display."""
        self.is_running = True
        logger.info("Console display started")
        
        while self.is_running:
            try:
                # Update the display
                self.update()
                
                # Sleep for the update interval
                time.sleep(self.update_interval)
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt. Stopping console display...")
                self.is_running = False
                
            except Exception as e:
                logger.error(f"Error in console display: {e}")
                time.sleep(1)  # Prevent CPU hogging on error
                
        logger.info("Console display stopped")
        
    def stop(self):
        """Stop the console display."""
        self.is_running = False
        logger.info("Console display stopped")

# For standalone testing
if __name__ == "__main__":
    display = ConsoleDisplay(update_interval=1)
    display.symbols = ["AAPL", "MSFT", "GOOGL"]
    display.stats = {
        'start_time': datetime.now(),
        'total_trades': 10,
        'errors': 2,
        'restarts': 1
    }
    display.start()
