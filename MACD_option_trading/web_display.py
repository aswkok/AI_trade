#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Web Display for MACD Options Trading System

This module provides a web-based visualization of quote data, recent entries,
and trade decisions for the MACD options trading system.
"""

import os
import sys
import time
import json
import logging
import threading
from datetime import datetime
from collections import deque
import pandas as pd
from flask import Flask, render_template, jsonify, request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebDisplay:
    """
    Web-based display for the MACD options trading system.
    
    This class provides a Flask web server to display:
    1. Latest quote data (bid, ask, timestamp)
    2. Recent data entries (last 100 records)
    3. Trade decisions and actions
    4. System messages with filtering and pagination
    """
    
    def __init__(self, host='localhost', port=8080, update_interval=1.0, max_history=100, max_messages=500):
        """
        Initialize the web display.
        
        Args:
            host: Host to run the web server on
            port: Port to run the web server on
            update_interval: Interval between data updates in seconds
            max_history: Maximum number of historical records to display
            max_messages: Maximum number of system messages to store
        """
        self.host = host
        self.port = port
        self.update_interval = update_interval
        self.max_history = max_history
        self.max_messages = max_messages
        
        # Data storage
        self.symbols = []
        self.latest_quotes = {}
        self.quote_history = {}
        self.trade_history = []
        self.system_messages = []
        
        # Display state
        self.is_running = False
        self.server_thread = None
        self.stop_event = threading.Event()
        
        # State persistence
        self.state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_display_state.json")
        
        # Create Flask app
        self.app = Flask(__name__, 
                         template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
                         static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"))
        
        # Set up routes
        self._setup_routes()
        
        # Locks for thread safety
        self.data_lock = threading.Lock()
        
        logger.info("Web display initialized")
    
    def _setup_routes(self):
        """Set up Flask routes."""
        # Main page
        @self.app.route('/')
        def index():
            return render_template('index.html', symbols=self.symbols)
        
        # API endpoints for data
        @self.app.route('/api/data')
        def get_data():
            with self.data_lock:
                data = {
                    'symbols': self.symbols,
                    'latest_quotes': self._serialize_quotes(),
                    'trade_history': self._serialize_trades(limit=10),
                    'system_messages': self._serialize_messages(limit=10)
                }
                return jsonify(data)
        
        @self.app.route('/api/quotes/<symbol>')
        def get_quotes(symbol):
            with self.data_lock:
                if symbol in self.latest_quotes:
                    return jsonify(self._serialize_quote(symbol))
                return jsonify({'error': f'Symbol {symbol} not found'})
        
        @self.app.route('/api/history/<symbol>')
        def get_history(symbol):
            limit = request.args.get('limit', 100, type=int)
            with self.data_lock:
                if symbol in self.quote_history and not self.quote_history[symbol].empty:
                    df = self.quote_history[symbol].tail(limit)
                    return jsonify(df.to_dict(orient='records'))
                return jsonify([])
        
        @self.app.route('/api/trades')
        def get_trades():
            limit = request.args.get('limit', 50, type=int)
            with self.data_lock:
                return jsonify(self._serialize_trades(limit=limit))
        
        @self.app.route('/api/messages')
        def get_messages():
            limit = request.args.get('limit', 100, type=int)
            filter_text = request.args.get('filter', '')
            with self.data_lock:
                return jsonify(self._serialize_messages(limit=limit, filter_text=filter_text))
        
        @self.app.route('/api/clear_messages', methods=['POST'])
        def clear_messages():
            with self.data_lock:
                self.system_messages = []
                self.add_system_message("System messages cleared")
                return jsonify({'status': 'success'})
    
    def _serialize_quotes(self):
        """Serialize latest quotes for JSON response."""
        result = {}
        for symbol, quote in self.latest_quotes.items():
            if quote:
                result[symbol] = self._serialize_quote(symbol)
        return result
    
    def _serialize_quote(self, symbol):
        """Serialize a single quote for JSON response."""
        quote = self.latest_quotes.get(symbol)
        if not quote:
            return None
        
        # Convert timestamp to string if it's a datetime
        if 'timestamp' in quote and isinstance(quote['timestamp'], datetime):
            quote_copy = quote.copy()
            quote_copy['timestamp'] = quote_copy['timestamp'].isoformat()
            return quote_copy
        return quote
    
    def _serialize_trades(self, limit=50):
        """Serialize trade history for JSON response."""
        trades = []
        for trade in self.trade_history[-limit:]:
            trade_copy = trade.copy()
            # Convert timestamp to string if it's a datetime
            if 'timestamp' in trade_copy and isinstance(trade_copy['timestamp'], datetime):
                trade_copy['timestamp'] = trade_copy['timestamp'].isoformat()
            trades.append(trade_copy)
        return trades
    
    def _serialize_messages(self, limit=100, filter_text=''):
        """Serialize system messages for JSON response."""
        if filter_text:
            filtered_messages = [msg for msg in self.system_messages if filter_text.lower() in msg.lower()]
        else:
            filtered_messages = self.system_messages
        
        return filtered_messages[-limit:]
    
    def register_symbol(self, symbol):
        """
        Register a symbol for monitoring.
        
        Args:
            symbol: Symbol to monitor
        """
        with self.data_lock:
            if symbol not in self.symbols:
                self.symbols.append(symbol)
                self.latest_quotes[symbol] = None
                self.quote_history[symbol] = pd.DataFrame()
                logger.info(f"Registered symbol {symbol} for monitoring")
    
    def update_quote(self, symbol, quote_data):
        """
        Update the latest quote for a symbol.
        
        Args:
            symbol: Symbol to update
            quote_data: Quote data dictionary with timestamp, bid, ask, etc.
        """
        with self.data_lock:
            if symbol not in self.symbols:
                self.register_symbol(symbol)
            
            # Update latest quote
            self.latest_quotes[symbol] = quote_data
            
            # Add to history
            if isinstance(quote_data, dict):
                # Convert to DataFrame row
                quote_df = pd.DataFrame([quote_data])
                
                # Append to history
                if self.quote_history[symbol].empty:
                    self.quote_history[symbol] = quote_df
                else:
                    self.quote_history[symbol] = pd.concat([self.quote_history[symbol], quote_df], ignore_index=True)
                    
                # Trim history to max_history
                if len(self.quote_history[symbol]) > self.max_history:
                    self.quote_history[symbol] = self.quote_history[symbol].tail(self.max_history)
    
    def add_trade(self, trade_data):
        """
        Add a trade to the trade history.
        
        Args:
            trade_data: Trade data dictionary with symbol, action, quantity, etc.
        """
        with self.data_lock:
            # Add timestamp if not present
            if 'timestamp' not in trade_data:
                trade_data['timestamp'] = datetime.now()
            
            # Add to trade history
            self.trade_history.append(trade_data)
            
            # Trim history if needed
            if len(self.trade_history) > self.max_history:
                self.trade_history = self.trade_history[-self.max_history:]
            
            # Add system message for the trade
            symbol = trade_data.get('symbol', 'UNKNOWN')
            action = trade_data.get('action', 'UNKNOWN')
            quantity = trade_data.get('quantity', 0)
            price = trade_data.get('price', 0.0)
            
            self.add_system_message(f"TRADE: {action} {quantity} {symbol} @ ${price:.2f}")
    
    def add_system_message(self, message):
        """
        Add a system message to the message history.
        
        Args:
            message: Message to add
        """
        with self.data_lock:
            # Create message with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            timestamped_message = f"{timestamp} - {message}"
            
            # Add to history
            self.system_messages.append(timestamped_message)
            
            # Trim history if needed
            if len(self.system_messages) > self.max_messages:
                self.system_messages = self.system_messages[-self.max_messages:]
    
    def add_signal(self, symbol, signal_data):
        """
        Add a trading signal to the system.
        
        Args:
            symbol: Symbol the signal is for
            signal_data: Signal data dictionary with signal type, strength, etc.
        """
        with self.data_lock:
            # Extract signal information
            signal_type = 1 if signal_data.get('crossover', False) else -1 if signal_data.get('crossunder', False) else 0
            position = signal_data.get('position', 'UNKNOWN')
            
            # Create message based on signal type
            if signal_type == 1:
                message = f"BULLISH SIGNAL: MACD crossed ABOVE signal line for {symbol}"
                if position == "ABOVE":
                    message += " (Confirmation)"
            elif signal_type == -1:
                message = f"BEARISH SIGNAL: MACD crossed BELOW signal line for {symbol}"
                if position == "BELOW":
                    message += " (Confirmation)"
            else:
                message = f"MACD position: {position} signal line for {symbol}"
            
            # Add to system messages
            self.add_system_message(message)
    
    def save_state(self):
        """Save the current display state to a file."""
        try:
            with self.data_lock:
                # Create state dictionary
                state = {
                    'timestamp': datetime.now().isoformat(),
                    'symbols': self.symbols,
                    'system_messages': self.system_messages[-100:],  # Save last 100 messages
                    'trade_history': self._serialize_trades(limit=100),  # Save last 100 trades
                }
                
                # Save latest quotes (convert to serializable format)
                state['latest_quotes'] = self._serialize_quotes()
                
                # Save to file
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
                
                logger.info(f"Display state saved to {self.state_file}")
                return True
        except Exception as e:
            logger.error(f"Error saving display state: {e}")
            return False
    
    def load_state(self):
        """Load the display state from a file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                with self.data_lock:
                    # Restore symbols and selection
                    for symbol in state.get('symbols', []):
                        if symbol not in self.symbols:
                            self.register_symbol(symbol)
                    
                    # Restore messages and trades
                    self.system_messages = state.get('system_messages', [])
                    self.trade_history = state.get('trade_history', [])
                    
                    # Restore latest quotes
                    for symbol, quote in state.get('latest_quotes', {}).items():
                        if symbol in self.symbols and quote:
                            # Convert timestamp back to datetime if it's a string
                            if 'timestamp' in quote and isinstance(quote['timestamp'], str):
                                try:
                                    quote_copy = quote.copy()
                                    quote_copy['timestamp'] = datetime.fromisoformat(quote_copy['timestamp'])
                                    self.latest_quotes[symbol] = quote_copy
                                except ValueError:
                                    # If timestamp can't be parsed, use as is
                                    self.latest_quotes[symbol] = quote
                            else:
                                self.latest_quotes[symbol] = quote
                
                self.add_system_message("Display state loaded")
                logger.info(f"Display state loaded from {self.state_file}")
                return True
        except Exception as e:
            logger.error(f"Error loading display state: {e}")
            return False
        
        return False
    
    def start(self):
        """Start the web display server."""
        if self.is_running:
            logger.warning("Web display is already running")
            return
        
        # Set running flag
        self.is_running = True
        self.stop_event.clear()
        
        # Try to load saved state
        self.load_state()
        
        # Add system message
        self.add_system_message("Web display started")
        
        # Start web server in a separate thread
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        logger.info(f"Web display started at http://{self.host}:{self.port}")
        
        return f"http://{self.host}:{self.port}"
    
    def _run_server(self):
        """Run the Flask web server."""
        try:
            self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
        except Exception as e:
            logger.error(f"Error running web server: {e}")
            self.is_running = False
    
    def stop(self):
        """Stop the web display server."""
        if not self.is_running:
            logger.warning("Web display is not running")
            return
        
        # Save state before stopping
        self.save_state()
        
        # Set stop flag
        self.stop_event.set()
        self.is_running = False
        
        # Add system message
        self.add_system_message("Web display stopped")
        
        logger.info("Web display stopped")


def main():
    """Run the web display as a standalone server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Web Display for MACD Options Trading System")
    parser.add_argument("--host", default="localhost", help="Host to run the web server on")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the web server on")
    parser.add_argument("--update-interval", type=float, default=1.0, help="Interval between data updates in seconds")
    parser.add_argument("--symbols", nargs="+", default=["SPY"], help="Symbols to monitor")
    
    args = parser.parse_args()
    
    # Create web display
    display = WebDisplay(
        host=args.host,
        port=args.port,
        update_interval=args.update_interval
    )
    
    # Register symbols
    for symbol in args.symbols:
        display.register_symbol(symbol)
    
    # Start display
    url = display.start()
    
    print(f"Web display started at {url}")
    print("Press Ctrl+C to stop")
    
    try:
        # Keep main thread alive
        while display.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping web display...")
    finally:
        display.stop()


if __name__ == "__main__":
    main()
