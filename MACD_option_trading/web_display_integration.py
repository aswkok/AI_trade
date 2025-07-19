#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Web Display Integration for MACD Options Trading System

This module integrates the web display with the continuous options trader service.
It allows the continuous options trader to update the web display with real-time data.
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime

# Import the web display
from web_display import WebDisplay
from continuous_options_trader_service import ContinuousOptionsTrader

# Configure logging
logger = logging.getLogger(__name__)

class WebDisplayIntegration:
    """
    Integrates the web display with the continuous options trader service.
    """
    
    def __init__(self, trader, host='localhost', port=8080, update_interval=1.0):
        """
        Initialize the web display integration.
        
        Args:
            trader: ContinuousOptionsTrader instance
            host: Host to run the web server on
            port: Port to run the web server on
            update_interval: Interval between data updates in seconds
        """
        self.trader = trader
        self.host = host
        self.port = port
        self.update_interval = update_interval
        
        # Create web display
        self.display = WebDisplay(
            host=host,
            port=port,
            update_interval=update_interval
        )
        
        # Register symbols
        for symbol in self.trader.symbols:
            self.display.register_symbol(symbol)
        
        # Display state
        self.is_running = False
        self.update_thread = None
        self.stop_event = threading.Event()
        
        logger.info("Web display integration initialized")
    
    def start(self):
        """Start the web display integration."""
        if self.is_running:
            logger.warning("Web display integration is already running")
            return
        
        # Set running flag
        self.is_running = True
        self.stop_event.clear()
        
        # Start web display
        url = self.display.start()
        
        # Start update thread
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        logger.info(f"Web display integration started at {url}")
        
        return url
    
    def stop(self):
        """Stop the web display integration."""
        if not self.is_running:
            logger.warning("Web display integration is not running")
            return
        
        # Set stop flag
        self.stop_event.set()
        self.is_running = False
        
        # Wait for update thread to terminate
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2)
        
        # Stop web display
        self.display.stop()
        
        logger.info("Web display integration stopped")
    
    def _update_loop(self):
        """Update loop to sync data from trader to web display."""
        logger.info("Web display update loop started")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                # Update quotes
                for symbol, trader_instance in self.trader.traders.items():
                    if hasattr(trader_instance, 'quote_monitor') and hasattr(trader_instance.quote_monitor, 'quotes_df'):
                        quotes_df = trader_instance.quote_monitor.quotes_df
                        
                        if not quotes_df.empty:
                            # Get the latest quote
                            latest_quote = quotes_df.iloc[-1].to_dict()
                            
                            # Update the display
                            self.display.update_quote(symbol, latest_quote)
                            
                            # Check for MACD signals
                            if hasattr(trader_instance.quote_monitor, 'get_macd_signal'):
                                macd_signal = trader_instance.quote_monitor.get_macd_signal()
                                if macd_signal:
                                    # Check for crossovers/crossunders
                                    if macd_signal.get('crossover', False) or macd_signal.get('crossunder', False):
                                        self.display.add_signal(symbol, macd_signal)
                
                # Update trades
                for symbol, trader_instance in self.trader.traders.items():
                    if hasattr(trader_instance, 'current_positions') and trader_instance.current_positions:
                        # Get the latest position
                        latest_position = trader_instance.current_positions[-1]
                        
                        # Check if this is a new position (not already in web display)
                        if not self._is_position_in_display(latest_position):
                            # Create trade data
                            trade_data = {
                                'timestamp': datetime.now(),
                                'symbol': symbol,
                                'action': latest_position.get('type', 'UNKNOWN'),
                                'quantity': latest_position.get('contracts', 0),
                                'price': latest_position.get('entry_price', 0.0),
                                'strategy': latest_position.get('strategy', 'MACD_STRATEGY')
                            }
                            
                            # Add trade to display
                            self.display.add_trade(trade_data)
                
                # Sleep for update interval
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in web display update loop: {e}")
                time.sleep(5)  # Wait before retrying
    
    def _is_position_in_display(self, position):
        """Check if a position is already in the web display."""
        # This is a simple check to avoid duplicate trades
        # In a real implementation, you would need a more robust way to track this
        for trade in self.display.trade_history:
            if (trade.get('symbol') == position.get('symbol') and
                trade.get('action') == position.get('type') and
                trade.get('quantity') == position.get('contracts') and
                trade.get('price') == position.get('entry_price')):
                return True
        return False


def main():
    """Run the web display integration as a standalone service."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Web Display Integration for MACD Options Trading System")
    parser.add_argument("--host", default="localhost", help="Host to run the web server on")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the web server on")
    parser.add_argument("--update-interval", type=float, default=1.0, help="Interval between data updates in seconds")
    parser.add_argument("--symbols", nargs="+", default=["SPY"], help="Symbols to monitor")
    
    # Add logging options
    parser.add_argument(
        "--log-file",
        default="logs/web_display.log",
        help="Log file path (default: logs/web_display.log)"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level (default: INFO)"
    )
    
    parser.add_argument(
        "--quiet-console",
        action="store_true",
        help="Only show warnings and above in console"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = getattr(logging, args.log_level)
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatters
    detailed_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    if args.quiet_console:
        console_handler.setLevel(logging.WARNING)  # Only show warnings and above in console
    else:
        console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Set up file handler if log file is specified
    if args.log_file:
        log_dir = os.path.dirname(args.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        file_handler = logging.handlers.RotatingFileHandler(
            args.log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
        # Log startup message
        logging.info(f"Logging to file: {args.log_file}")
    
    # Create continuous options trader
    trader = ContinuousOptionsTrader(
        symbols=args.symbols,
        enable_display=False  # Disable terminal display since we're using web display
    )
    
    # Create web display integration
    integration = WebDisplayIntegration(
        trader=trader,
        host=args.host,
        port=args.port,
        update_interval=args.update_interval
    )
    
    # Start integration
    url = integration.start()
    
    print(f"Web display integration started at {url}")
    print("Press Ctrl+C to stop")
    
    try:
        # Start the trader
        trader.run()
    except KeyboardInterrupt:
        print("Stopping web display integration...")
    finally:
        integration.stop()
        trader.is_running = False


if __name__ == "__main__":
    main()
