#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Real-Time Display for MACD Options Trading System

This module provides real-time visualization of quote data, recent entries,
and trade decisions for the MACD options trading system.
"""

import os
import sys
import time
import json
import logging
import threading
import curses
from datetime import datetime
import pandas as pd
from tabulate import tabulate
import numpy as np

# Import our safe display utilities
from safe_display import safe_display

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RealTimeDisplay:
    """
    Real-time display for the MACD options trading system.
    
    This class provides a curses-based terminal interface to display:
    1. Latest quote data (bid, ask, timestamp)
    2. Recent data entries (last 100 records)
    3. Trade decisions and actions
    """
    
    def __init__(self, update_interval=0.5, max_history=100, max_messages=100):
        """
        Initialize the real-time display.
        
        Args:
            update_interval: Interval between display updates in seconds
            max_history: Maximum number of historical records to display
            max_messages: Maximum number of system messages to store
        """
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
        self.is_paused = False
        self.display_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.screen = None
        self.current_view = "quotes"  # "quotes", "history", "trades", "messages"
        self.selected_symbol = None
        
        # Scrolling state
        self.message_scroll_position = 0
        self.max_visible_messages = 10  # Default, will be adjusted based on screen size
        
        # State persistence
        self.state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "display_state.json")
        
        # Locks for thread safety
        self.data_lock = threading.Lock()
        
        logger.info("Real-time display initialized")
    
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
                
                # Set the first registered symbol as the selected symbol
                if self.selected_symbol is None:
                    self.selected_symbol = symbol
    
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
            
            # Add to history if it's a new quote
            if isinstance(quote_data, dict):
                # Check if this is a new quote by comparing timestamp
                is_new_quote = True
                
                if not self.quote_history[symbol].empty and 'timestamp' in quote_data:
                    last_timestamp = self.quote_history[symbol]['timestamp'].iloc[-1]
                    current_timestamp = quote_data['timestamp']
                    
                    # Convert to datetime objects if they aren't already
                    if not isinstance(last_timestamp, datetime):
                        try:
                            last_timestamp = pd.to_datetime(last_timestamp)
                        except:
                            pass
                            
                    if not isinstance(current_timestamp, datetime):
                        try:
                            current_timestamp = pd.to_datetime(current_timestamp)
                        except:
                            pass
                    
                    # Check if timestamps are the same
                    if isinstance(last_timestamp, datetime) and isinstance(current_timestamp, datetime):
                        is_new_quote = last_timestamp != current_timestamp
                
                # Only add to history if it's a new quote
                if is_new_quote:
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
            
            # Trim history to max_history
            if len(self.trade_history) > self.max_history:
                self.trade_history = self.trade_history[-self.max_history:]
            
            # Add system message
            action = trade_data.get('action', 'UNKNOWN')
            symbol = trade_data.get('symbol', 'UNKNOWN')
            quantity = trade_data.get('quantity', 0)
            price = trade_data.get('price', 0.0)
            
            message = f"TRADE: {action} {quantity} {symbol} @ ${price:.2f}"
            self.add_system_message(message)
    
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
            signal_type = signal_data.get('signal', 0)
            position = signal_data.get('position', 'UNKNOWN')
            crossover = signal_data.get('crossover', False)
            crossunder = signal_data.get('crossunder', False)
            
            # Create message based on signal
            if crossover:
                message = f"SIGNAL: {symbol} BULLISH CROSSOVER - MACD crossed ABOVE signal line"
            elif crossunder:
                message = f"SIGNAL: {symbol} BEARISH CROSSUNDER - MACD crossed BELOW signal line"
            elif signal_type > 0:
                message = f"SIGNAL: {symbol} BULLISH - MACD ABOVE signal line"
            elif signal_type < 0:
                message = f"SIGNAL: {symbol} BEARISH - MACD BELOW signal line"
            else:
                message = f"SIGNAL: {symbol} NEUTRAL - No clear direction"
            
            # Add system message
            self.add_system_message(message)
    
    def _init_curses(self):
        """Initialize the curses interface."""
        # Initialize curses
        self.screen = curses.initscr()
        
        # Set up colors
        curses.start_color()
        curses.use_default_colors()
        
        # Define color pairs
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # Green for positive/buy
        curses.init_pair(2, curses.COLOR_RED, -1)    # Red for negative/sell
        curses.init_pair(3, curses.COLOR_YELLOW, -1) # Yellow for warnings
        curses.init_pair(4, curses.COLOR_BLUE, -1)   # Blue for info
        curses.init_pair(5, curses.COLOR_CYAN, -1)   # Cyan for headers
        
        # Set up terminal settings
        curses.noecho()        # Don't echo keypresses
        curses.cbreak()        # React to keys instantly
        self.screen.keypad(1)  # Enable special keys
        curses.curs_set(0)     # Hide cursor
        
        # Get screen dimensions
        self.height, self.width = self.screen.getmaxyx()
        
        # Check if terminal is too small
        min_height, min_width = 24, 80
        if self.height < min_height or self.width < min_width:
            self._cleanup_curses()
            print(f"\033[1;31mError: Terminal window too small. Minimum size: {min_width}x{min_height}\033[0m")
            print(f"Current size: {self.width}x{self.height}")
            print("Please resize your terminal window and try again.")
            sys.exit(1)
    
    def _cleanup_curses(self):
        """Clean up the curses interface."""
        if self.screen:
            # Restore terminal settings
            self.screen.keypad(0)
            curses.echo()
            curses.nocbreak()
            curses.endwin()
            self.screen = None
            
    def safe_addstr(self, y, x, text, attr=0):
        """
        Safely add a string to the screen, handling boundary errors.
        
        Args:
            y: Y coordinate (row)
            x: X coordinate (column)
            text: Text to display
            attr: Text attributes (color, bold, etc.)
        """
        safe_display.safe_addstr(self.screen, y, x, text, attr)

    def safe_addch(self, y, x, ch, attr=0):
        """
        Safely add a character to the screen, handling boundary errors.
        
        Args:
            y: Y coordinate (row)
            x: X coordinate (column)
            ch: Character to display
            attr: Text attributes (color, bold, etc.)
        """
        safe_display.safe_addch(self.screen, y, x, ch, attr)

    def draw_box(self, y, x, height, width, title=None, title_attr=0):
        """
        Safely draw a box on the screen.
        
        Args:
            y: Top-left Y coordinate
            x: Top-left X coordinate
            height: Box height
            width: Box width
            title: Optional box title
            title_attr: Title text attributes
        """
        safe_display.draw_box(self.screen, y, x, height, width, title, title_attr)
    
    def _handle_input(self):
        """Handle user input."""
        # Set screen to non-blocking input
        self.screen.nodelay(1)
        
        try:
            # Check for keypress (non-blocking)
            key = self.screen.getch()
            
            # Skip if no key was pressed
            if key == -1:
                return
                
            # Handle key
            if key == ord('q'):
                # Quit
                self.stop_event.set()
                self.is_running = False
                return
            elif key == ord('p'):
                # Pause/Resume display
                self.toggle_pause()
                return
            elif key == ord('s'):
                # Save state
                self.save_state()
                self.add_system_message("Display state saved")
                return
                
            # View switching (lightweight operations)
            elif key == ord('1'):
                # Switch to quotes view
                self.current_view = "quotes"
                self.message_scroll_position = 0  # Reset scroll position
            elif key == ord('2'):
                # Switch to history view
                self.current_view = "history"
                self.message_scroll_position = 0  # Reset scroll position
            elif key == ord('3'):
                # Switch to trades view
                self.current_view = "trades"
                self.message_scroll_position = 0  # Reset scroll position
            elif key == ord('4'):
                # Switch to messages view
                self.current_view = "messages"
                self.message_scroll_position = 0  # Reset scroll position
            elif key == ord('\t'):
                # Cycle through symbols (use a separate lock to avoid deadlocks)
                if len(self.symbols) > 0:
                    current_index = self.symbols.index(self.selected_symbol) if self.selected_symbol in self.symbols else 0
                    next_index = (current_index + 1) % len(self.symbols)
                    self.selected_symbol = self.symbols[next_index]
            
            # Scrolling controls (optimize to avoid unnecessary calculations)
            elif key == curses.KEY_UP or key == ord('k'):
                # Scroll up
                if self.message_scroll_position > 0:
                    self.message_scroll_position -= 1
            elif key == curses.KEY_DOWN or key == ord('j'):
                # Scroll down
                max_scroll = max(0, len(self.system_messages) - self.max_visible_messages)
                if self.message_scroll_position < max_scroll:
                    self.message_scroll_position += 1
            elif key == curses.KEY_PPAGE:  # Page Up
                # Scroll up one page
                self.message_scroll_position = max(0, self.message_scroll_position - self.max_visible_messages)
            elif key == curses.KEY_NPAGE:  # Page Down
                # Scroll down one page
                max_scroll = max(0, len(self.system_messages) - self.max_visible_messages)
                self.message_scroll_position = min(max_scroll, self.message_scroll_position + self.max_visible_messages)
            elif key == curses.KEY_HOME:
                # Scroll to top
                self.message_scroll_position = 0
            elif key == curses.KEY_END:
                # Scroll to bottom
                max_scroll = max(0, len(self.system_messages) - self.max_visible_messages)
                self.message_scroll_position = max_scroll
            elif key == ord('c'):
                # Clear system messages
                with self.data_lock:
                    self.system_messages = []
                    self.add_system_message("System messages cleared")
                    self.message_scroll_position = 0
        
        except Exception as e:
            # Log input errors but continue
            logger.debug(f"Input handling error: {e}")
            pass
    
    def _display_header(self):
        """Display the header section."""
        # Clear screen
        self.screen.clear()
            
        # Display header
        header = f"MACD Options Trading System - {self.selected_symbol if self.selected_symbol else 'No Symbol'}"
        self.safe_addstr(0, 0, header, curses.A_BOLD)
            
        # Display current time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.safe_addstr(0, len(header) + 5, current_time)
        
        # Display navigation menu
        menu = "[1] Latest Quotes | [2] Quote History | [3] Trade History | [4] System Messages | [↑/↓] Scroll | [Tab] Switch Symbol | [p] Pause/Resume | [s] Save | [q] Quit"
        if len(menu) > self.width - 2:
            menu = "[1] Quotes | [2] History | [3] Trades | [4] Messages | [↑/↓] Scroll | [Tab] Symbol | [p] Pause | [s] Save | [q] Quit"
        
        self.safe_addstr(1, max(0, (self.width - len(menu)) // 2), menu)
        
        # Highlight current view
        menu_x = max(0, (self.width - len(menu)) // 2)
        if self.current_view == "quotes":
            self.safe_addstr(1, menu_x + menu.find("[1]"), "[1]", curses.A_REVERSE)
        elif self.current_view == "history":
            self.safe_addstr(1, menu_x + menu.find("[2]"), "[2]", curses.A_REVERSE)
        elif self.current_view == "trades":
            self.safe_addstr(1, menu_x + menu.find("[3]"), "[3]", curses.A_REVERSE)
        elif self.current_view == "messages":
            self.safe_addstr(1, menu_x + menu.find("[4]"), "[4]", curses.A_REVERSE)
        
        # Highlight pause if paused
        if self.is_paused:
            self.safe_addstr(1, menu_x + menu.find("[p]"), "[p]", curses.A_REVERSE | curses.color_pair(2))
        
        # Display selected symbol
        if self.selected_symbol:
            symbol_str = f"Selected Symbol: {self.selected_symbol}"
            self.safe_addstr(2, (self.width - len(symbol_str)) // 2, symbol_str, curses.A_BOLD)
        
        # Draw separator
        self.safe_addstr(3, 0, "=" * (self.width - 1))
    
    def _display_quotes_view(self):
        """Display the latest quotes view."""
        with self.data_lock:
            if not self.selected_symbol or self.selected_symbol not in self.latest_quotes:
                self.safe_addstr(5, 2, "No symbol selected or no data available.")
                return
            
            quote_data = self.latest_quotes[self.selected_symbol]
            if not quote_data:
                self.safe_addstr(5, 2, f"No quote data available for {self.selected_symbol}.")
                return
            
            # Display section title
            self.safe_addstr(4, 2, "LATEST QUOTE DATA", curses.color_pair(5) | curses.A_BOLD)
            
            # Display quote data
            row = 6
            if isinstance(quote_data, dict):
                # Format timestamp
                timestamp = quote_data.get('timestamp', 'Unknown')
                if isinstance(timestamp, datetime):
                    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    timestamp_str = str(timestamp)
                
                # Display basic quote information
                self.safe_addstr(row, 2, f"Timestamp: {timestamp_str}")
                row += 1
                
                # Display bid/ask
                bid = quote_data.get('bid', 'N/A')
                ask = quote_data.get('ask', 'N/A')
                if bid != 'N/A' and ask != 'N/A':
                    self.safe_addstr(row, 2, f"Bid: ${bid:.2f}", curses.color_pair(1))
                    self.safe_addstr(row, 20, f"Ask: ${ask:.2f}", curses.color_pair(2))
                    self.safe_addstr(row, 38, f"Spread: ${ask - bid:.4f} ({(ask - bid) / bid * 100:.2f}%)")
                else:
                    self.safe_addstr(row, 2, f"Bid: {bid}")
                    self.safe_addstr(row, 20, f"Ask: {ask}")
                row += 2
                
                # Display MACD information if available
                macd = quote_data.get('MACD', None)
                signal = quote_data.get('signal', None)
                histogram = quote_data.get('histogram', None)
                position = quote_data.get('MACD_position', None)
                
                # Create a box for MACD indicators
                try:
                    # Draw the box
                    box_width = 70
                    box_height = 6
                    box_top = row
                    box_left = 2
                    
                    # Use our safe box drawing method
                    self.draw_box(box_top, box_left, box_height + 1, box_width, 
                                  "[ MACD INDICATORS ]", curses.color_pair(5) | curses.A_BOLD)
                    
                    # MACD values
                    if macd is not None and signal is not None:
                        # Display MACD values
                        macd_color = curses.color_pair(1) if macd > signal else curses.color_pair(2)
                        signal_color = curses.color_pair(0)  # Default color
                        hist_color = curses.color_pair(1) if histogram > 0 else curses.color_pair(2)
                        
                        self.safe_addstr(box_top + 2, box_left + 4, f"MACD:      {macd:.6f}", macd_color | curses.A_BOLD)
                        self.safe_addstr(box_top + 2, box_left + 30, f"Signal:    {signal:.6f}", signal_color)
                        self.safe_addstr(box_top + 2, box_left + 56, f"Histogram: {histogram:.6f}", hist_color)
                        
                        # Display current position
                        position_text = f"Current Position: MACD is {position} signal line"
                        position_color = curses.color_pair(1) if position == "ABOVE" else curses.color_pair(2)
                        self.safe_addstr(box_top + 4, box_left + 4, position_text, position_color | curses.A_BOLD)
                        
                        # Display trade signal
                        crossover = quote_data.get('crossover', False)
                        crossunder = quote_data.get('crossunder', False)
                        
                        signal_text = ""
                        signal_color = curses.color_pair(0)
                        
                        if crossover:
                            signal_text = "BULLISH SIGNAL: BUY"
                            signal_color = curses.color_pair(1)
                        elif crossunder:
                            signal_text = "BEARISH SIGNAL: SELL"
                            signal_color = curses.color_pair(2)
                        elif position == "ABOVE":
                            signal_text = "CURRENT SIGNAL: HOLD LONG"
                            signal_color = curses.color_pair(1)
                        elif position == "BELOW":
                            signal_text = "CURRENT SIGNAL: HOLD SHORT"
                            signal_color = curses.color_pair(2)
                        else:
                            signal_text = "CURRENT SIGNAL: NEUTRAL"
                        
                        if signal_text:
                            self.safe_addstr(box_top + 4, box_left + 40, signal_text, signal_color | curses.A_BOLD)
                except Exception as e:
                    self.safe_addstr(row + 1, box_left, f"Error drawing MACD box: {e}", curses.color_pair(2))
                
                # Update row position after the box
                row += box_height + 1
            else:
                self.safe_addstr(row, 2, f"Quote data format not recognized: {type(quote_data)}")
            
            # Display a small section of recent system messages
            row += 3
            self.safe_addstr(row, 2, "RECENT SYSTEM MESSAGES: (Press '4' for full message view)", curses.color_pair(5) | curses.A_BOLD)
            row += 1
            
            # Calculate available space for messages
            available_rows = self.height - row - 2  # Leave 2 rows at bottom
            max_messages = min(5, available_rows)  # Show at most 5 messages in this view
            
            # Display last few messages in reverse order (newest first)
            for i, message in enumerate(reversed(self.system_messages[-max_messages:])):
                if row + i < self.height - 1:
                    # Truncate message if too long
                    max_width = self.width - 4  # Leave 2 chars on each side
                    if len(message) > max_width:
                        display_msg = message[:max_width-3] + "..."
                    else:
                        display_msg = message
                    
                    # Color code messages
                    if "BULLISH" in message or "BUY" in message:
                        self.safe_addstr(row + i, 2, display_msg, curses.color_pair(1))
                    elif "BEARISH" in message or "SELL" in message:
                        self.safe_addstr(row + i, 2, display_msg, curses.color_pair(2))
                    elif "TRADE" in message:
                        self.safe_addstr(row + i, 2, display_msg, curses.color_pair(4) | curses.A_BOLD)
                    else:
                        self.safe_addstr(row + i, 2, display_msg)
    
    def _display_history_view(self):
        """Display the quote history view."""
        # Use a local copy of data to minimize lock time
        selected_symbol = self.selected_symbol
        
        if not selected_symbol:
            self.safe_addstr(5, 2, "No symbol selected.")
            return
        
        # Get a copy of the history data with minimal lock time
        with self.data_lock:
            if selected_symbol not in self.quote_history:
                self.safe_addstr(5, 2, f"No history available for {selected_symbol}.")
                return
                
            # Make a copy of the tail to work with outside the lock
            try:
                history = self.quote_history[selected_symbol]
                if history.empty:
                    self.safe_addstr(5, 2, f"No history data available for {selected_symbol}.")
                    return
                    
                # Only take the last 20 records to improve performance
                display_df = history.tail(20).copy()
            except Exception as e:
                self.safe_addstr(5, 2, f"Error accessing history: {str(e)[:50]}")
                return
                
        try:
            # Display section title with cyan color
            self.safe_addstr(4, 2, f"QUOTE HISTORY - {selected_symbol} - Last {len(display_df)} Records", 
                           curses.color_pair(5) | curses.A_BOLD)
            
            # Pre-process data outside the rendering loop for better performance
            formatted_data = []
            display_cols = ['time', 'bid', 'ask', 'mid']
            
            # Add MACD columns if available
            if 'MACD' in display_df.columns:
                display_cols.extend(['MACD', 'signal', 'histogram'])
            if 'MACD_position' in display_df.columns:
                display_cols.append('MACD_position')
                
            # Format timestamp column first
            if 'timestamp' in display_df.columns:
                display_df['time'] = display_df['timestamp'].apply(
                    lambda x: x.strftime('%H:%M:%S') if isinstance(x, datetime) else str(x)
                )
            
            # Pre-format all data rows
            for _, row_data in display_df.iloc[::-1].iterrows():
                formatted_row = {}
                
                for col in display_cols:
                    if col in row_data:
                        value = row_data[col]
                        # Format numeric values
                        if isinstance(value, (int, float)) and col not in ['time', 'MACD_position']:
                            formatted_row[col] = f"{value:.4f}"
                        else:
                            formatted_row[col] = str(value)
                    else:
                        formatted_row[col] = ""
                        
                formatted_data.append(formatted_row)
            
            # Display the table
            row = 6
            col_width = min(15, (self.width - 4) // len(display_cols))
            
            # Display column headers
            for i, col in enumerate(display_cols):
                header_text = col.upper()[:col_width-1]
                self.safe_addstr(row, 2 + i * col_width, header_text, curses.A_BOLD)
            
            # Display data rows (limited by screen height)
            max_rows = min(len(formatted_data), self.height - row - 2)
            
            for i in range(max_rows):
                data_row = formatted_data[i]
                
                for j, col in enumerate(display_cols):
                    value = data_row.get(col, '')[:col_width-1]
                    pos_x = 2 + j * col_width
                    pos_y = row + i + 1
                    
                    # Skip if position is outside screen bounds
                    if pos_y >= self.height - 1 or pos_x >= self.width - 1:
                        continue
                    
                    # Apply color based on column and value
                    if col == 'MACD_position':
                        if value == 'ABOVE':
                            self.safe_addstr(pos_y, pos_x, value, curses.color_pair(1))
                        elif value == 'BELOW':
                            self.safe_addstr(pos_y, pos_x, value, curses.color_pair(2))
                        else:
                            self.safe_addstr(pos_y, pos_x, value)
                    else:
                        self.safe_addstr(pos_y, pos_x, value)
                        
        except Exception as e:
            # Log the error and show a message
            logger.error(f"Error in history view: {e}")
            self.safe_addstr(self.height-2, 2, f"Display error: {str(e)[:50]}", curses.color_pair(2))
    
    def _display_trades_view(self):
        """Display the trade history view."""
        with self.data_lock:
            if not self.trade_history:
                self.safe_addstr(5, 2, "No trade history available.")
                return
            
            # Display section title
            self.safe_addstr(4, 2, "TRADE HISTORY - All Symbols", curses.color_pair(5) | curses.A_BOLD)
            
            # Display trades
            row = 6
            self.safe_addstr(row, 2, "TIMESTAMP", curses.A_BOLD)
            self.safe_addstr(row, 22, "SYMBOL", curses.A_BOLD)
            self.safe_addstr(row, 32, "ACTION", curses.A_BOLD)
            self.safe_addstr(row, 45, "QUANTITY", curses.A_BOLD)
            self.safe_addstr(row, 55, "PRICE", curses.A_BOLD)
            self.safe_addstr(row, 65, "STRATEGY", curses.A_BOLD)
            
            # Display trade rows
            for i, trade in enumerate(reversed(self.trade_history)):
                if row + i + 1 >= self.height - 1:
                    break
                
                # Format timestamp
                timestamp = trade.get('timestamp', 'Unknown')
                if isinstance(timestamp, datetime):
                    timestamp_str = timestamp.strftime('%H:%M:%S')
                else:
                    timestamp_str = str(timestamp)
                
                # Get trade data
                symbol = trade.get('symbol', 'UNKNOWN')
                action = trade.get('action', 'UNKNOWN')
                quantity = trade.get('quantity', 0)
                price = trade.get('price', 0.0)
                strategy = trade.get('strategy', 'UNKNOWN')
                
                # Display with color based on action
                self.safe_addstr(row + i + 1, 2, timestamp_str)
                self.safe_addstr(row + i + 1, 22, symbol)
                
                if 'BUY' in action.upper():
                    self.safe_addstr(row + i + 1, 32, action, curses.color_pair(1) | curses.A_BOLD)
                elif 'SELL' in action.upper():
                    self.safe_addstr(row + i + 1, 32, action, curses.color_pair(2) | curses.A_BOLD)
                else:
                    self.safe_addstr(row + i + 1, 32, action)
                
                self.safe_addstr(row + i + 1, 45, str(quantity))
                self.safe_addstr(row + i + 1, 55, f"${price:.2f}")
                self.safe_addstr(row + i + 1, 65, strategy)
    
    def _display_messages_view(self):
        """Display the system messages view with scrolling."""
        with self.data_lock:
            # Display section title
            self.safe_addstr(4, 2, "SYSTEM MESSAGES", curses.color_pair(5) | curses.A_BOLD)
            
            # Calculate available space for messages
            available_rows = self.height - 7  # Leave space for header and footer
            self.max_visible_messages = available_rows
            
            # Calculate total pages and current page
            total_messages = len(self.system_messages)
            if total_messages == 0:
                self.safe_addstr(6, 2, "No system messages available.")
                return
                
            max_scroll = max(0, total_messages - self.max_visible_messages)
            
            # Ensure scroll position is valid
            if self.message_scroll_position > max_scroll:
                self.message_scroll_position = max_scroll
            
            # Display scrolling information
            current_page = (self.message_scroll_position // self.max_visible_messages) + 1
            total_pages = (total_messages + self.max_visible_messages - 1) // self.max_visible_messages
            self.safe_addstr(5, 2, f"Showing messages {self.message_scroll_position+1}-{min(self.message_scroll_position+self.max_visible_messages, total_messages)} of {total_messages} (Page {current_page}/{total_pages})")
            self.safe_addstr(5, self.width - 40, "[↑/↓] Scroll | [PgUp/PgDn] Page | [Home/End] Top/Bottom | [c] Clear")
            
            # Display messages with scrolling
            start_idx = max(0, total_messages - self.max_visible_messages - self.message_scroll_position)
            end_idx = total_messages - self.message_scroll_position
            
            # Get visible messages
            visible_messages = self.system_messages[start_idx:end_idx]
            
            # Display messages
            for i, message in enumerate(reversed(visible_messages)):
                row = 6 + i
                if row < self.height - 1:
                    # Truncate message if too long
                    max_width = self.width - 4  # Leave 2 chars on each side
                    if len(message) > max_width:
                        display_msg = message[:max_width-3] + "..."
                    else:
                        display_msg = message
                    
                    # Color code messages
                    if "BULLISH" in message or "BUY" in message:
                        self.safe_addstr(row, 2, display_msg, curses.color_pair(1))
                    elif "BEARISH" in message or "SELL" in message:
                        self.safe_addstr(row, 2, display_msg, curses.color_pair(2))
                    elif "TRADE" in message:
                        self.safe_addstr(row, 2, display_msg, curses.color_pair(4) | curses.A_BOLD)
                    else:
                        self.safe_addstr(row, 2, display_msg)
    
    def _display_loop(self):
        """Main display loop."""
        try:
            # Initialize curses
            self._init_curses()
            
            # Track last update time for performance monitoring
            last_update_time = time.time()
            frame_times = []
            
            # Main display loop
            while self.is_running and not self.stop_event.is_set():
                try:
                    # Calculate time since last frame
                    current_time = time.time()
                    frame_time = current_time - last_update_time
                    last_update_time = current_time
                    
                    # Track frame times for performance monitoring
                    frame_times.append(frame_time)
                    if len(frame_times) > 100:
                        frame_times.pop(0)
                    
                    # Handle user input (non-blocking)
                    self._handle_input()
                    
                    # Only redraw the screen at the specified update interval
                    # This prevents excessive CPU usage
                    if not self.is_paused:
                        # Clear screen
                        self.screen.erase()
                        
                        # Update screen dimensions
                        self.height, self.width = self.screen.getmaxyx()
                        
                        # Display header
                        self._display_header()
                        
                        # Display current view
                        if self.current_view == "quotes":
                            self._display_quotes_view()
                        elif self.current_view == "history":
                            self._display_history_view()
                        elif self.current_view == "trades":
                            self._display_trades_view()
                        elif self.current_view == "messages":
                            self._display_messages_view()
                        
                        # Display performance info in debug mode
                        if frame_times:
                            avg_frame_time = sum(frame_times) / len(frame_times)
                            fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
                            if fps < 5:  # If performance is poor, log it
                                logger.debug(f"Display performance: {fps:.1f} FPS")
                    
                    # Display pause status if paused
                    if self.is_paused:
                        pause_msg = "DISPLAY PAUSED - Press 'p' to resume"
                        msg_pos = max(0, (self.width - len(pause_msg)) // 2)
                        self.screen.addstr(self.height - 2, msg_pos, pause_msg, curses.color_pair(4) | curses.A_BOLD)
                    
                    # Refresh screen
                    self.screen.refresh()
                    
                    # Calculate sleep time to maintain target frame rate
                    elapsed = time.time() - current_time
                    sleep_time = max(0.01, self.update_interval - elapsed)  # Ensure minimum sleep
                    time.sleep(sleep_time)
                    
                except Exception as e:
                    # Log error and continue
                    logger.error(f"Error in display loop: {e}")
                    time.sleep(0.5)  # Reduced sleep time on error
            
        except Exception as e:
            logger.error(f"Error in display thread: {e}")
            
        finally:
            # Clean up curses
            self._cleanup_curses()
    
    def toggle_pause(self):
        """Toggle pause/resume of the display."""
        if self.is_paused:
            # Resume
            self.is_paused = False
            self.pause_event.set()
            self.add_system_message("Display resumed")
            logger.info("Display resumed")
        else:
            # Pause
            self.is_paused = True
            self.add_system_message("Display paused")
            logger.info("Display paused")
    
    def save_state(self):
        """Save the current display state to a file."""
        try:
            with self.data_lock:
                # Create state dictionary
                state = {
                    'timestamp': datetime.now().isoformat(),
                    'symbols': self.symbols,
                    'selected_symbol': self.selected_symbol,
                    'current_view': self.current_view,
                    'system_messages': self.system_messages[-100:],  # Save last 100 messages
                    'trade_history': self.trade_history[-100:],  # Save last 100 trades
                }
                
                # Save latest quotes (convert to serializable format)
                latest_quotes = {}
                for symbol, quote in self.latest_quotes.items():
                    if quote:
                        # Convert timestamp to string if it's a datetime
                        if 'timestamp' in quote and isinstance(quote['timestamp'], datetime):
                            quote_copy = quote.copy()
                            quote_copy['timestamp'] = quote_copy['timestamp'].isoformat()
                            latest_quotes[symbol] = quote_copy
                        else:
                            latest_quotes[symbol] = quote
                
                state['latest_quotes'] = latest_quotes
                
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
                    
                    self.selected_symbol = state.get('selected_symbol')
                    self.current_view = state.get('current_view', 'quotes')
                    
                    # Restore messages and trades
                    self.system_messages = state.get('system_messages', [])
                    self.trade_history = state.get('trade_history', [])
                    
                    # Restore latest quotes
                    for symbol, quote in state.get('latest_quotes', {}).items():
                        if symbol in self.symbols:
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
        """Start the real-time display."""
        if self.is_running:
            logger.warning("Display is already running")
            return
        
        # Set running flag
        self.is_running = True
        self.stop_event.clear()
        self.pause_event.clear()
        
        # Try to load saved state
        self.load_state()
        
        # Start display thread
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()
        
        logger.info("Real-time display started")
    
    def stop(self):
        """Stop the real-time display."""
        if not self.is_running:
            logger.warning("Display is not running")
            return
        
        # Save state before stopping
        self.save_state()
        
        # Set stop flag
        self.stop_event.set()
        self.is_running = False
        
        # If paused, unpause to allow thread to exit
        if self.is_paused:
            self.is_paused = False
            self.pause_event.set()
        
        # Wait for display thread to terminate
        if self.display_thread and self.display_thread.is_alive():
            self.display_thread.join(timeout=2)
        
        # Clean up curses (in case the display thread didn't)
        self._cleanup_curses()
        
        logger.info("Real-time display stopped")


if __name__ == "__main__":
    # Simple test
    display = RealTimeDisplay()
    
    # Register a symbol
    display.register_symbol("SPY")
    
    # Start the display
    display.start()
    
    try:
        # Generate some test data
        for i in range(100):
            # Create a quote
            timestamp = datetime.now()
            bid = 100.0 + np.sin(i / 10) * 2
            ask = bid + 0.05
            mid = (bid + ask) / 2
            
            # MACD values
            macd = np.sin(i / 15) * 0.5
            signal = np.sin((i - 5) / 15) * 0.5
            histogram = macd - signal
            
            # Determine position
            position = "ABOVE" if macd > signal else "BELOW"
            
            # Determine crossover/crossunder
            crossover = macd > signal and i > 0 and np.sin((i - 1) / 15) * 0.5 <= np.sin((i - 6) / 15) * 0.5
            crossunder = macd < signal and i > 0 and np.sin((i - 1) / 15) * 0.5 >= np.sin((i - 6) / 15) * 0.5
            
            # Create quote data
            quote_data = {
                'timestamp': timestamp,
                'bid': bid,
                'ask': ask,
                'mid': mid,
                'MACD': macd,
                'signal': signal,
                'histogram': histogram,
                'MACD_position': position,
                'crossover': crossover,
                'crossunder': crossunder
            }
            
            # Update quote
            display.update_quote("SPY", quote_data)
            
            # Add system message occasionally
            if i % 10 == 0:
                display.add_system_message(f"Test message {i}")
            
            # Add signal occasionally
            if crossover or crossunder:
                signal_data = {
                    'signal': 1 if crossover else -1,
                    'position': position,
                    'crossover': crossover,
                    'crossunder': crossunder
                }
                display.add_signal("SPY", signal_data)
            
            # Add trade occasionally
            if i % 20 == 0:
                trade_data = {
                    'timestamp': timestamp,
                    'symbol': "SPY",
                    'action': "BUY" if i % 40 == 0 else "SELL",
                    'quantity': 10,
                    'price': mid,
                    'strategy': "MACD_TEST"
                }
                display.add_trade(trade_data)
            
            # Sleep
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        pass
    
    finally:
        # Stop the display
        display.stop()
