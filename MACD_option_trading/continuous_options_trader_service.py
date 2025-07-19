#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Continuous MACD Options Trading Service

This module implements a background service that continuously monitors market data,
generates MACD signals, and automatically executes options trades based on those signals.
It's designed to run indefinitely with proper error handling and recovery.
"""

import os
import sys
import time
import json
import signal
import socket
import logging
import argparse
import threading
import warnings
from datetime import datetime, timedelta
import pytz
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Suppress specific warnings for cleaner display
warnings.filterwarnings("ignore", category=RuntimeWarning, message="divide by zero encountered")
warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered")

# Import the trading components
from macd_options_trader import MACDOptionsTrader
from quote_monitor_selector import QuoteMonitor

# Import the display modules
from real_time_display import RealTimeDisplay
from console_display import ConsoleDisplay

# Configure logging with rotation to prevent huge log files
import logging.handlers

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)
logger = logging.getLogger(__name__)

# Constants for display
DISPLAY_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "display_status.json")
DISPLAY_COMMAND_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "display_command.json")
DISPLAY_COMMAND_PROCESSED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "display_command_processed.json")

class ContinuousOptionsTrader:
    """
    Service that runs a MACD options trading strategy continuously in the background.
    
    This class handles:
    - Continuous monitoring and trading based on MACD signals
    - Market hours detection and scheduling
    - Error recovery and resilience
    - Trade state persistence
    - System health monitoring
    """
    
    def __init__(self, symbols, trade_style='directional', risk_per_trade=0.02, 
                 update_interval=60, extended_hours=False, warmup_minutes=30,
                 fast_window=13, slow_window=21, signal_window=9, always_collect_data=True,
                 enable_display=True, display_update_interval=0.5, force_market_open=False):
        """
        Initialize the continuous trading service.
        
        Args:
            symbols: List of symbols to trade
            trade_style: Trading style (directional, income, combined)
            risk_per_trade: Risk percentage per trade
            update_interval: Update interval in seconds
            extended_hours: Whether to trade during extended hours
            warmup_minutes: Warmup period in minutes
            fast_window: MACD fast EMA window
            slow_window: MACD slow EMA window
            signal_window: MACD signal line window
            always_collect_data: Whether to always collect data regardless of market hours
            enable_display: Whether to enable the real-time display
            display_update_interval: Update interval for the real-time display in seconds
            force_market_open: Force market status to be OPEN (for testing purposes)
        """
        # Load environment variables
        load_dotenv(override=True)
        
        # Store parameters
        self.symbols = symbols if isinstance(symbols, list) else [symbols]
        self.trade_style = trade_style
        self.risk_per_trade = risk_per_trade
        self.update_interval = update_interval
        self.extended_hours = extended_hours
        self.warmup_minutes = warmup_minutes
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.always_collect_data = always_collect_data
        self.display_update_interval = display_update_interval
        self.force_market_open = force_market_open
        
        # Debug logging for force_market_open flag
        logger.info(f"Force market open flag: {self.force_market_open}")
        if self.force_market_open:
            logger.info("Market will be forced OPEN for testing purposes")
        
        # Initialize state
        self.is_running = False
        self.traders = {}
        self.display = None
        self.display_thread = None
        self.socket_server = None
        self.socket_thread = None
        self.display_enabled = enable_display
        self.console_display = None
        
        # Statistics tracking - store the actual session start time
        self.session_start_time = datetime.now()
        self.stats = {
            'trades': 0,
            'total_trades': 0,  # Added to fix 'total_trades' key error
            'successful_trades': 0,  # Added to fix success rate calculation
            'signals': 0,
            'errors': 0,
            'start_time': self.session_start_time,  # This will be the current session start
            'last_update': datetime.now(),
            'market_open_count': 0,
            'market_close_count': 0,
            'restarts': 0  # Ensure restarts is initialized
        }
        
        # Health check tracking
        self.last_health_check = datetime.now()
        self.health_check_interval = 300  # 5 minutes in seconds
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        # Initialize the display status file
        self._init_display_status()
        
        # Initialize the real-time display if enabled
        if self.display_enabled:
            self._start_display()
        
        # Initialize the command files for display toggle commands
        self._init_command_files()
        
        # Initialize traders
        self._initialize_traders()
        
        # Load saved state if available
        self.load_state()
        
        logger.info(f"Initialized continuous options trading service for {self.symbols}")
        
    def _init_display_status(self):
        """Initialize the display status file."""
        try:
            # Create the status file if it doesn't exist
            if not os.path.exists(DISPLAY_STATUS_FILE):
                with open(DISPLAY_STATUS_FILE, 'w') as f:
                    json.dump({'enabled': self.display_enabled}, f)
            else:
                # Read the current status
                with open(DISPLAY_STATUS_FILE, 'r') as f:
                    status = json.load(f)
                    self.display_enabled = status.get('enabled', self.display_enabled)
        except Exception as e:
            logger.error(f"Error initializing display status: {e}")
            
    def _start_display(self):
        """Start the curses-based display."""
        try:
            # Create a new curses-based display instance
            self.display = RealTimeDisplay(update_interval=self.display_update_interval)
            
            # Register symbols
            for symbol in self.symbols:
                self.display.register_symbol(symbol)
            
            # Start the display
            self.display.start()
            logger.info("Real-time display started")
        except Exception as e:
            logger.error(f"Error starting display: {e}")
            self.display = None
            
    def _stop_display(self):
        """Stop the display based on the current mode."""
        # Stop the curses-based display if it's running
        if self.display and hasattr(self.display, 'is_running') and self.display.is_running:
            try:
                self.display.stop()
                self.display = None
                logger.info("Real-time display stopped")
            except Exception as e:
                logger.error(f"Error stopping display: {e}")
                
        # Stop the console display if it's running
        if hasattr(self, 'console_display') and self.console_display and hasattr(self.console_display, 'is_running') and self.console_display.is_running:
            try:
                self.console_display.stop()
                self.console_display = None
                logger.info("Console display stopped")
            except Exception as e:
                logger.error(f"Error stopping console display: {e}")
                
        # Start the console display if the display is disabled
        if not self.display_enabled and not hasattr(self, 'console_display') or not self.console_display:
            self._start_console_display()
                
    def _start_console_display(self):
        """Start the console display in a separate thread."""
        try:
            # Create a new console-based display instance
            self.console_display = ConsoleDisplay(update_interval=30)  # Update every 30 seconds
            
            # Register traders and symbols
            for symbol, trader in self.traders.items():
                self.console_display.register_trader(symbol, trader)
            
            # Register stats
            self.console_display.register_stats(self.stats)
            
            # Start the console display in a separate thread
            import threading
            self.console_thread = threading.Thread(target=self.console_display.start, daemon=True)
            self.console_thread.start()
            logger.info("Console display started")
        except Exception as e:
            logger.error(f"Error starting console display: {e}")
            self.console_display = None
    
    def _print_console_status(self):
        """Print organized status information to the terminal when display is off."""
        # Clear the terminal
        print("\033c", end="")
        
        # Print header with colored text
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("\033[1;36m" + "="*80 + "\033[0m")  # Cyan color
        print("\033[1;36m║\033[0m" + "\033[1;37m MACD OPTIONS TRADING SYSTEM - CONSOLE MODE \033[0m".center(78) + "\033[1;36m║\033[0m")
        print("\033[1;36m║\033[0m" + f"\033[1;37m {current_time} \033[0m".center(78) + "\033[1;36m║\033[0m")
        print("\033[1;36m" + "="*80 + "\033[0m")  # Cyan color
        
        # Print system status - use session start time for uptime calculation
        uptime = (datetime.now() - self.session_start_time).total_seconds() / 3600
        uptime_days = int(uptime // 24)
        uptime_hours = int(uptime % 24)
        uptime_str = f"{uptime_days}d {uptime_hours}h" if uptime_days > 0 else f"{uptime_hours:.1f}h"
        
        # Check if market open is being forced via environment variable or command line flag
        force_market_open_env = os.environ.get('FORCE_MARKET_OPEN', '0').strip() == '1'
        logger.info(f"Checking force_market_open - env: {force_market_open_env}, flag: {self.force_market_open}")
        
        if force_market_open_env or self.force_market_open:
            logger.info("Market is OPEN (forced for testing purposes)")
            market_status = "\033[1;32mOPEN\033[0m"  # Green color
        else:
            # Use Eastern Time for accurate market hours detection
            eastern_tz = pytz.timezone('US/Eastern')
            now_et = datetime.now(pytz.UTC).astimezone(eastern_tz)
            current_hour = now_et.hour
            current_minute = now_et.minute
            weekday = now_et.weekday()
            
            # Check if it's a weekday and during market hours (9:30 AM - 4:00 PM ET)
            is_weekday = weekday < 5  # Monday=0, Friday=4
            # Check if it's during regular trading hours
            if current_hour == 9:
                # 9:30 AM - 9:59 AM ET
                is_market_hours = current_minute >= 30
            elif 10 <= current_hour <= 15:
                # 10:00 AM - 3:59 PM ET (any minute)
                is_market_hours = True
            elif current_hour == 16:
                # 4:00 PM ET exactly (market closes)
                is_market_hours = current_minute == 0
            else:
                # Before 9:30 AM or after 4:00 PM ET
                is_market_hours = False
            
            # Determine market status based on Eastern Time
            if is_weekday and is_market_hours:
                logger.info(f"Market is OPEN (Eastern Time: {now_et.strftime('%H:%M:%S')})")
                market_status = "\033[1;32mOPEN\033[0m"  # Green color
            else:
                logger.info(f"Market is CLOSED (Eastern Time: {now_et.strftime('%H:%M:%S')})")
                market_status = "\033[1;31mCLOSED\033[0m"  # Red color
        
        # System status section
        print("\033[1;33m┌─ System Status " + "─"*62 + "┐\033[0m")
        print(f"\033[1;33m│\033[0m Status: \033[1;32mRunning\033[0m | Uptime: {uptime_str} | Market: {market_status}")
        
        # Trading statistics
        total_trades = self.stats.get('total_trades', 0)
        successful_trades = self.stats.get('successful_trades', 0)
        success_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
        
        print(f"\033[1;33m│\033[0m Trades: {total_trades} | Success Rate: {success_rate:.1f}% | Errors: {self.stats.get('errors', 0)} | Restarts: {self.stats.get('restarts', 0)}")
        print("\033[1;33m└" + "─"*77 + "┘\033[0m")
        
        # Symbols section
        print("\033[1;33m┌─ Monitored Symbols " + "─"*58 + "┐\033[0m")
        symbols_str = ", ".join([f"\033[1;37m{s}\033[0m" for s in self.symbols])
        print(f"\033[1;33m│\033[0m {symbols_str}")
        print("\033[1;33m└" + "─"*77 + "┘\033[0m")
        
        # Data collection status
        print("\033[1;33m┌─ Data Collection Status " + "─"*54 + "┐\033[0m")
        for symbol, trader in self.traders.items():
            if hasattr(trader, 'quote_monitor') and hasattr(trader.quote_monitor, 'quotes_df'):
                quotes_count = len(trader.quote_monitor.quotes_df)
                last_update = trader.quote_monitor.last_update.strftime("%H:%M:%S") if hasattr(trader.quote_monitor, 'last_update') else "N/A"
                print(f"\033[1;33m│\033[0m \033[1;37m{symbol}\033[0m: {quotes_count} quotes collected | Last update: {last_update}")
        print("\033[1;33m└" + "─"*77 + "┘\033[0m")
        
        # Commands section
        print("\033[1;33m┌─ Available Commands " + "─"*57 + "┐\033[0m")
        print("\033[1;33m│\033[0m  python toggle_display.py --on    : Turn display ON")
        print("\033[1;33m│\033[0m  python toggle_display.py --status : Show display status")
        print("\033[1;33m│\033[0m  Ctrl+C                           : Exit program")
        print("\033[1;33m└" + "─"*77 + "┘\033[0m")
        print()
                
    def _init_command_files(self):
        """Initialize the command files for display toggle commands."""
        # Create the command file if it doesn't exist
        if not os.path.exists(DISPLAY_COMMAND_FILE):
            try:
                with open(DISPLAY_COMMAND_FILE, 'w') as f:
                    json.dump({'command': 'NONE', 'timestamp': datetime.now().isoformat()}, f)
                logger.info(f"Created command file at {DISPLAY_COMMAND_FILE}")
            except Exception as e:
                logger.error(f"Error creating command file: {e}")
        
        # Create the processed command file if it doesn't exist
        if not os.path.exists(DISPLAY_COMMAND_PROCESSED_FILE):
            try:
                with open(DISPLAY_COMMAND_PROCESSED_FILE, 'w') as f:
                    json.dump({'command': 'NONE', 'timestamp': datetime.now().isoformat(), 'status': 'OK'}, f)
                logger.info(f"Created processed command file at {DISPLAY_COMMAND_PROCESSED_FILE}")
            except Exception as e:
                logger.error(f"Error creating processed command file: {e}")
        
        # Start the command checking thread
        self.command_thread = threading.Thread(target=self._check_commands_loop)
        self.command_thread.daemon = True
        self.command_thread.start()
        
        logger.info("Command checking thread started")
        
    def _start_command_checking(self):
        """Start the command checking thread if not already running."""
        if not hasattr(self, 'command_thread') or not self.command_thread.is_alive():
            self.command_thread = threading.Thread(target=self._check_commands_loop)
            self.command_thread.daemon = True
            self.command_thread.start()
            logger.info("Command checking thread started")
        
    def _check_commands_loop(self):
        """Loop to check for display toggle commands in the command file."""
        logger.info("Command checking loop started")
        
        while self.is_running:
            try:
                # Check if the command file exists
                if not os.path.exists(DISPLAY_COMMAND_FILE):
                    # Create the command file if it doesn't exist
                    with open(DISPLAY_COMMAND_FILE, 'w') as f:
                        json.dump({'command': 'NONE', 'timestamp': datetime.now().isoformat()}, f)
                    logger.info(f"Created command file at {DISPLAY_COMMAND_FILE}")
                    time.sleep(1)  # Wait a bit before continuing
                    continue
                
                # Read the command file
                try:
                    with open(DISPLAY_COMMAND_FILE, 'r') as f:
                        command_data = json.load(f)
                except Exception as e:
                    logger.error(f"Error reading command file: {e}")
                    time.sleep(1)  # Wait a bit before continuing
                    continue
                
                # Get the command and timestamp
                command = command_data.get('command', 'NONE')
                timestamp = command_data.get('timestamp', datetime.now().isoformat())
                
                # Check if we've already processed this command
                processed = False
                if os.path.exists(DISPLAY_COMMAND_PROCESSED_FILE):
                    try:
                        with open(DISPLAY_COMMAND_PROCESSED_FILE, 'r') as f:
                            processed_data = json.load(f)
                            processed_command = processed_data.get('command', 'NONE')
                            processed_timestamp = processed_data.get('timestamp', '')
                            
                            # If the command and timestamp match, we've already processed this command
                            if command == processed_command and timestamp == processed_timestamp:
                                processed = True
                    except Exception as e:
                        logger.error(f"Error reading processed command file: {e}")
                
                # If we've already processed this command, skip it
                if processed or command == 'NONE':
                    time.sleep(1)  # Wait a bit before checking again
                    continue
                
                # Process the command
                status = "OK"
                if command == "ENABLE_DISPLAY":
                    # Use the toggle_display method with enable=True
                    if not self.display_enabled:
                        result = self.toggle_display(enable=True)
                        logger.info(f"Display enabled via command file: {result}")
                    else:
                        status = "ALREADY_ENABLED"
                        logger.info("Display already enabled")
                        
                elif command == "DISABLE_DISPLAY":
                    # Use the toggle_display method with enable=False
                    if self.display_enabled:
                        result = self.toggle_display(enable=False)
                        logger.info(f"Display disabled via command file: {result}")
                    else:
                        status = "ALREADY_DISABLED"
                        logger.info("Display already disabled")
                        
                elif command == "STATUS":
                    # Just update the status in the processed file
                    status = "ENABLED" if self.display_enabled else "DISABLED"
                    logger.info(f"Status request received, current status: {status} (display_enabled={self.display_enabled})")
                    # Also log whether the display is actually running
                    if hasattr(self, 'display') and self.display:
                        logger.info(f"Curses display is running: {hasattr(self.display, 'is_running') and self.display.is_running}")
                    if hasattr(self, 'console_display') and self.console_display:
                        logger.info(f"Console display is running: {hasattr(self.console_display, 'is_running') and self.console_display.is_running}")
                    
                else:
                    status = "UNKNOWN_COMMAND"
                    logger.warning(f"Unknown command received: {command}")
                
                # Mark the command as processed
                try:
                    with open(DISPLAY_COMMAND_PROCESSED_FILE, 'w') as f:
                        json.dump({
                            'command': command,
                            'timestamp': timestamp,
                            'status': status,
                            'processed_at': datetime.now().isoformat()
                        }, f)
                    logger.info(f"Command {command} marked as processed with status {status}")
                except Exception as e:
                    logger.error(f"Error writing processed command file: {e}")
                
            except Exception as e:
                logger.error(f"Error in command checking loop: {e}")
            
            # Wait a bit before checking again
            time.sleep(1)
        
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}. Shutting down...")
        self.is_running = False
        
        # Save the current state
        try:
            self.save_state()
            logger.info("State saved successfully")
        except Exception as e:
            logger.error(f"Error saving state during shutdown: {e}")
        
        # Stop the display
        self._stop_display()
        
        # Update the command files to indicate shutdown
        try:
            with open(DISPLAY_COMMAND_FILE, 'w') as f:
                json.dump({'command': 'SHUTDOWN', 'timestamp': datetime.now().isoformat()}, f)
            with open(DISPLAY_COMMAND_PROCESSED_FILE, 'w') as f:
                json.dump({
                    'command': 'SHUTDOWN',
                    'timestamp': datetime.now().isoformat(),
                    'status': 'OK',
                    'processed_at': datetime.now().isoformat()
                }, f)
            logger.info("Command files updated for shutdown")
        except Exception as e:
            logger.error(f"Error updating command files during shutdown: {e}")
                
        logger.info("Shutdown complete")
        
        # Exit the process
        if signum in (signal.SIGINT, signal.SIGTERM):
            # Use os._exit which cannot be caught or blocked
            os._exit(1)
        else:
            sys.exit(0)
        
    def toggle_display(self, enable=None):
        """Toggle the real-time display on/off without stopping data collection.
        
        Args:
            enable: If provided, set the display to this state (True=on, False=off)
                   If None, toggle the current state
        """
        # Set or toggle the display status
        if enable is not None:
            # Set to specific state
            new_state = enable
        else:
            # Toggle current state
            new_state = not self.display_enabled
            
        # Only take action if the state is changing
        if new_state == self.display_enabled:
            logger.info(f"Display is already {'enabled' if new_state else 'disabled'}")
            return self.display_enabled
            
        # Update the display status
        self.display_enabled = new_state
        
        # Update the status file
        try:
            with open(DISPLAY_STATUS_FILE, 'w') as f:
                json.dump({'enabled': self.display_enabled}, f)
        except Exception as e:
            logger.error(f"Error updating display status file: {e}")
        
        # Start or stop the display based on the new state
        if self.display_enabled:
            # Stop the console display if it's running
            if hasattr(self, 'console_display') and self.console_display:
                try:
                    self.console_display.stop()
                    self.console_display = None
                    logger.info("Console display stopped")
                except Exception as e:
                    logger.error(f"Error stopping console display: {e}")
            
            # Start the curses display
            if not self.display:
                self._start_display()
                logger.info("Display toggled ON")
        else:
            # Stop the curses display if it's running
            if self.display:
                self._stop_display()
                logger.info("Display toggled OFF")
            
            # Start the console display if it's not already running
            if not hasattr(self, 'console_display') or not self.console_display:
                self._start_console_display()
        
        return self.display_enabled
    
    def _initialize_traders(self):
        """Initialize trading instances for each symbol."""
        for symbol in self.symbols:
            try:
                # Create a new trader for this symbol with always_collect_data=True to ensure
                # data collection happens regardless of market hours
                trader = MACDOptionsTrader(
                    symbol=symbol,
                    interval_seconds=self.update_interval,
                    fast_window=self.fast_window,
                    slow_window=self.slow_window,
                    signal_window=self.signal_window,
                    risk_per_trade=self.risk_per_trade,
                    # Removed trade_style parameter as it's not supported by MACDOptionsStrategy
                    extended_hours=True,  # Always enable extended hours for data collection
                    warmup_period_minutes=self.warmup_minutes
                )
                
                # Explicitly set the quote monitor to collect data during extended hours
                if hasattr(trader, 'quote_monitor') and hasattr(trader.quote_monitor, 'include_extended_hours'):
                    trader.quote_monitor.include_extended_hours = True
                
                # Store the trader
                self.traders[symbol] = trader
                logger.info(f"Initialized trader for {symbol} with continuous data collection")
            except Exception as e:
                logger.error(f"Error initializing trader for {symbol}: {e}")
                self.stats['errors'] += 1
                
        
        # Update the status file
        try:
            with open(DISPLAY_STATUS_FILE, 'w') as f:
                json.dump({'enabled': self.display_enabled}, f)
        except Exception as e:
            logger.error(f"Error updating display status file: {e}")
        
        # Start or stop the display
        if self.display_enabled:
            if not self.display:
                self._start_display()
                logger.info("Display toggled ON")
        else:
            if self.display:
                self._stop_display()
                logger.info("Display toggled OFF")
        
        return self.display_enabled
    
    def save_state(self):
        """Save the current trading state to disk."""
        try:
            # Create state directory if it doesn't exist
            state_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state')
            os.makedirs(state_dir, exist_ok=True)
            
            # Save statistics
            stats_file = os.path.join(state_dir, 'trading_stats.json')
            # Ensure datetime is serializable
            stats_copy = self.stats.copy()
            if stats_copy['start_time']:
                if hasattr(stats_copy['start_time'], 'isoformat'):
                    stats_copy['start_time'] = stats_copy['start_time'].isoformat()
            if 'last_update' in stats_copy and stats_copy['last_update']:
                if hasattr(stats_copy['last_update'], 'isoformat'):
                    stats_copy['last_update'] = stats_copy['last_update'].isoformat()
            if hasattr(self, 'last_health_check') and self.last_health_check:
                if hasattr(self.last_health_check, 'isoformat'):
                    stats_copy['last_health_check'] = self.last_health_check.isoformat()
                
            with open(stats_file, 'w') as f:
                json.dump(stats_copy, f, indent=2)
            
            # Save positions for each trader
            for symbol, trader in self.traders.items():
                positions_file = os.path.join(state_dir, f'{symbol}_positions.json')
                
                # Convert positions to serializable format
                serializable_positions = []
                for pos in trader.current_positions:
                    pos_copy = pos.copy()
                    # Convert contract to serializable format
                    contract = pos_copy['contract']
                    pos_copy['contract'] = {
                        'underlying': contract.underlying,
                        'contract_type': contract.contract_type,
                        'strike': float(contract.strike),
                        'expiration': contract.expiration,
                        'premium': float(contract.premium) if contract.premium else None
                    }
                    # Convert entry_date to string
                    pos_copy['entry_date'] = pos_copy['entry_date'].isoformat()
                    serializable_positions.append(pos_copy)
                
                with open(positions_file, 'w') as f:
                    json.dump(serializable_positions, f, indent=2)
            
            logger.info("Trading state saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving trading state: {e}")
    
    def load_state(self):
        """Load the trading state from disk."""
        try:
            # Create state directory if it doesn't exist
            state_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state')
            
            # Load statistics if exists
            stats_file = os.path.join(state_dir, 'trading_stats.json')
            if os.path.exists(stats_file):
                with open(stats_file, 'r') as f:
                    loaded_stats = json.load(f)
                    # Convert start_time back to datetime if it exists but DON'T use it
                    # We want to keep the current session start time
                    if 'start_time' in loaded_stats:
                        del loaded_stats['start_time']  # Remove it so it doesn't overwrite current session
                    # Preserve the current session start time
                    current_start_time = self.stats['start_time']
                    self.stats.update(loaded_stats)
                    self.stats['start_time'] = current_start_time  # Restore current session start time
                    logger.info(f"Loaded trading statistics (keeping current session start time): {self.stats}")
            
            # Load positions for each trader if exists
            for symbol, trader in self.traders.items():
                positions_file = os.path.join(state_dir, f'{symbol}_positions.json')
                if os.path.exists(positions_file):
                    with open(positions_file, 'r') as f:
                        positions = json.load(f)
                        
                    # Convert serialized positions back to usable format
                    for pos in positions:
                        # Convert the contract dictionary back to OptionsContract
                        from options_trader import OptionsContract
                        contract_data = pos['contract']
                        contract = OptionsContract(
                            underlying=contract_data['underlying'],
                            contract_type=contract_data['contract_type'],
                            strike=float(contract_data['strike']),
                            expiration=contract_data['expiration'],
                            premium=float(contract_data['premium']) if contract_data['premium'] else None
                        )
                        pos['contract'] = contract
                        
                        # Convert entry_date back to datetime
                        pos['entry_date'] = datetime.fromisoformat(pos['entry_date'])
                    
                    # Set the positions
                    trader.current_positions = positions
                    logger.info(f"Loaded {len(positions)} positions for {symbol}")
            
            logger.info("Trading state loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading trading state: {e}")
            logger.info("Continuing with fresh state")
    
    def is_market_open(self):
        """
        Check if the market is currently open using Eastern Time.
        
        Returns:
            bool: True if the market is open, False otherwise
        """
        # Check if market open is being forced via command line flag
        if hasattr(self, 'force_market_open') and self.force_market_open:
            logger.info("Market is OPEN (forced via command line flag)")
            return True
            
        # Check if market open is being forced via environment variable
        force_market_open_env = os.environ.get('FORCE_MARKET_OPEN', '0').strip() == '1'
        if force_market_open_env:
            logger.info("Market is OPEN (forced via environment variable)")
            return True
            
        # Use Eastern Time for accurate market hours detection
        eastern_tz = pytz.timezone('US/Eastern')
        now_et = datetime.now(pytz.UTC).astimezone(eastern_tz)
        current_hour = now_et.hour
        current_minute = now_et.minute
        weekday = now_et.weekday()
        
        # Check if it's a weekday and between 9:30 AM and 4:00 PM ET
        is_weekday = weekday < 5  # Monday=0, Friday=4
        
        if is_weekday:
            # Check regular market hours (9:30 AM - 4:00 PM ET)
            if current_hour == 9:
                # 9:30 AM - 9:59 AM ET
                is_market_hours = current_minute >= 30
            elif 10 <= current_hour <= 15:
                # 10:00 AM - 3:59 PM ET
                is_market_hours = True
            elif current_hour == 16:
                # 4:00 PM ET exactly (market closes at 4:00 PM)
                is_market_hours = current_minute == 0
            else:
                is_market_hours = False
            
            if is_market_hours:
                logger.info(f"Market is OPEN (Eastern Time: {now_et.strftime('%H:%M:%S')})")
                return True
        
        # Extended hours if enabled
        if self.extended_hours and is_weekday:
            # Pre-market: 4:00 AM - 9:30 AM ET
            is_pre_market = (current_hour >= 4 and current_hour < 9) or (current_hour == 9 and current_minute < 30)
            # After-hours: 4:00 PM - 8:00 PM ET
            is_after_hours = (current_hour > 16 and current_hour <= 20) or (current_hour == 16 and current_minute > 0)
            
            if is_pre_market:
                logger.info(f"Pre-market is open (Eastern Time: {now_et.strftime('%H:%M:%S')})")
                return True
            elif is_after_hours:
                logger.info(f"After-hours is open (Eastern Time: {now_et.strftime('%H:%M:%S')})")
                return True
        
        logger.info(f"Market is CLOSED (Eastern Time: {now_et.strftime('%H:%M:%S')})")
        return False
    
    def check_system_health(self):
        """
        Check the health of the trading system and recover from errors if needed.
        """
        now = datetime.now()
        
        # Only run health check every 5 minutes
        if (now - self.last_health_check).total_seconds() < self.health_check_interval:
            return
            
        self.last_health_check = now
        logger.info("Running system health check...")
        
        # Check each trader
        for symbol, trader in self.traders.items():
            try:
                # Check if the quote monitor is still receiving data
                if trader.quote_monitor and len(trader.quote_monitor.quotes_df) > 0:
                    last_quote_time = trader.quote_monitor.quotes_df.index[-1]
                    if isinstance(last_quote_time, pd.Timestamp):
                        last_quote_time = last_quote_time.to_pydatetime()
                    
                    # If last quote is too old, restart the quote monitor
                    if (now - last_quote_time).total_seconds() > self.update_interval * 5:
                        logger.warning(f"Quote monitor for {symbol} has stale data. Restarting...")
                        
                        # Reinitialize the quote monitor
                        trader.quote_monitor = QuoteMonitor(
                            symbol=symbol,
                            max_records=max(trader.slow_window * 3, 500),
                            interval_seconds=trader.interval_seconds,
                            fast_window=trader.fast_window,
                            slow_window=trader.slow_window,
                            signal_window=trader.signal_window
                        )
                        
                        # Set the quote monitor for the strategy
                        trader.strategy.set_quote_monitor(trader.quote_monitor)
                        
                        self.stats['restarts'] += 1
                        logger.info(f"Quote monitor for {symbol} restarted successfully")
                
                # Check if trader is still running
                if not trader.is_running:
                    logger.warning(f"Trader for {symbol} is not running. Restarting...")
                    trader.is_running = True
                    trader.start_time = datetime.now()
                    self.stats['restarts'] += 1
                    logger.info(f"Trader for {symbol} restarted successfully")
                
            except Exception as e:
                logger.error(f"Error checking health for trader {symbol}: {e}")
                self.stats['errors'] += 1
        
        # Log current statistics
        uptime = (now - self.stats['start_time']).total_seconds() / 3600 if self.stats['start_time'] else 0
        logger.info(f"System health: Uptime: {uptime:.1f} hours, " +
                    f"Trades: {self.stats['total_trades']}, " +
                    f"Success rate: {self.stats['successful_trades']/max(1, self.stats['total_trades']):.1%}, " +
                    f"Errors: {self.stats['errors']}, " +
                    f"Restarts: {self.stats['restarts']}")
    
    def wait_for_market_open(self, check_interval=60):
        """
        Wait until the market opens.
        Data collection continues in the background while waiting.
        
        Args:
            check_interval: Interval in seconds to check market status
        """
        logger.info("Waiting for market open for trading (data collection continues)...")
        
        while not self.is_market_open() and self.is_running:
            try:
                # Get next market open time
                symbol = next(iter(self.traders))
                trader = self.traders[symbol]
                clock = trader.trading_system.trading_client.get_clock()
                next_open = clock.next_open
                
                # Convert to local time for display
                next_open_local = next_open.replace(tzinfo=None)
                time_until_open = (next_open_local - datetime.now()).total_seconds() / 60
                
                # Display data collection status
                data_status = ""
                for symbol, trader in self.traders.items():
                    if hasattr(trader, 'quote_monitor') and hasattr(trader.quote_monitor, 'quotes_df'):
                        quotes_count = len(trader.quote_monitor.quotes_df)
                        data_status += f"{symbol}: {quotes_count} quotes collected. "
                
                logger.info(f"Market is closed for trading. Next market open: {next_open_local.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"Approximately {time_until_open:.1f} minutes until market open")
                if data_status:
                    logger.info(f"Data collection status: {data_status}")
                
                # Wait for the next check with periodic checks for termination
                for _ in range(int(check_interval)):
                    if not self.is_running:
                        logger.info("Termination signal received while waiting for market open")
                        return
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error while waiting for market open: {e}")
                time.sleep(check_interval)
    
    def update_all_traders(self):
        """Update all traders and process signals for trading."""
        for symbol, trader in self.traders.items():
            try:
                # Update quotes (although this is also happening in the background data collection thread)
                trader.update_quotes()
                
                # Check if we have enough data to make trading decisions
                if hasattr(trader, 'quote_monitor') and hasattr(trader.quote_monitor, 'quotes_df'):
                    # Explicitly check if the DataFrame is empty to avoid ambiguous truth value error
                    if isinstance(trader.quote_monitor.quotes_df, pd.DataFrame) and len(trader.quote_monitor.quotes_df) > 0:
                        quotes_count = len(trader.quote_monitor.quotes_df)
                        min_required = max(trader.slow_window * 2, 30)  # Minimum required for good MACD signals
                        
                        if quotes_count < min_required:
                            logger.info(f"Not enough data for {symbol} yet. Have {quotes_count} quotes, need at least {min_required}")
                            if self.display:
                                self.display.add_system_message(f"Not enough data for {symbol} yet. Have {quotes_count} quotes, need at least {min_required}")
                            continue
                        
                        # Process MACD signal and execute trades
                        try:
                            trade_executed = trader.process_macd_signal()
                        except Exception as e:
                            logger.error(f"Error processing MACD signal for {symbol}: {e}")
                            if self.display:
                                self.display.add_system_message(f"Error processing MACD signal for {symbol}: {e}")
                            continue
                    else:
                        logger.info(f"No data available for {symbol} yet (empty DataFrame)")
                        if self.display:
                            self.display.add_system_message(f"No data available for {symbol} yet (empty DataFrame)")
                        continue
                    
                    if trade_executed:
                        logger.info(f"Trade executed for {symbol}")
                        self.stats['total_trades'] += 1
                        self.stats['successful_trades'] += 1
                        
                        # Update the display with trade information
                        if self.display and hasattr(trader, 'current_positions') and trader.current_positions:
                            # Get the latest position
                            latest_position = trader.current_positions[-1]
                            
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
                else:
                    logger.warning(f"No data available for {symbol}")
                    if self.display:
                        self.display.add_system_message(f"No data available for {symbol}")
                
            except Exception as e:
                logger.error(f"Error updating trader for {symbol}: {e}")
                self.stats['errors'] += 1
                if self.display:
                    self.display.add_system_message(f"Error updating trader for {symbol}: {e}")
    
    def collect_data(self):
        """
        Continuously collect market data regardless of market hours.
        This ensures we have sufficient data for when trading begins.
        """
        logger.info("Starting continuous data collection...")
        
        while self.is_running:
            try:
                # Update all quote monitors to collect data
                for symbol, trader in self.traders.items():
                    if hasattr(trader, 'quote_monitor'):
                        # Force the quote monitor to update
                        trader.update_quotes()
                        logger.debug(f"Updated quotes for {symbol}")
                        
                        # Update the real-time display with the latest quote data
                        if self.display and hasattr(trader.quote_monitor, 'quotes_df') and not trader.quote_monitor.quotes_df.empty:
                            # Get the latest quote
                            latest_quote = trader.quote_monitor.quotes_df.iloc[-1].to_dict()
                            
                            # Update the display
                            self.display.update_quote(symbol, latest_quote)
                            
                            # Check for MACD signals
                            if hasattr(trader.quote_monitor, 'get_macd_signal'):
                                macd_signal = trader.quote_monitor.get_macd_signal()
                                if macd_signal:
                                    # Check for crossovers/crossunders
                                    if macd_signal.get('crossover', False) or macd_signal.get('crossunder', False):
                                        self.display.add_signal(symbol, macd_signal)
                
                # Sleep for a shorter interval to ensure frequent data collection
                collection_interval = min(30, self.update_interval)  # At most 30 seconds
                time.sleep(collection_interval)
                
            except Exception as e:
                logger.error(f"Error in data collection loop: {e}")
                time.sleep(5)  # Short delay before retrying

    def run(self):
        """
        Main method to run the continuous trading service.
        This will run indefinitely until stopped.
        """
        logger.info("Starting continuous options trading service...")
        self.is_running = True
        self.stats['start_time'] = datetime.now()
        
        # Load previous state if available
        self.load_state()
        
        # Start the appropriate display based on the display_enabled flag
        if self.display_enabled:
            if self.display:
                self.display.start()
        else:
            # Start the console display if the real-time display is disabled
            self._start_console_display()
        
        # Log appropriate message based on display type
        if self.display_enabled and self.display:
            logger.info("Real-time display started - press 'q' to quit, '1/2/3' to switch views, 'Tab' to switch symbols")
        
        # Start the command checking for display toggle commands
        self._start_command_checking()
        logger.info("Command checking started for display toggle commands")
        
        # Start data collection in a separate thread to ensure continuous data gathering
        # regardless of market hours
        import threading
        data_thread = threading.Thread(target=self.collect_data, daemon=True)
        data_thread.start()
        logger.info("Data collection thread started - collecting data continuously")
        
        # Initialize last status update time
        last_status_update = datetime.now()
        status_update_interval = 60  # Update console status every 60 seconds when display is off
        
        try:
            while self.is_running:
                # Check system health
                self.check_system_health()
                
                # Update console status if display is disabled
                if not self.display_enabled and (datetime.now() - last_status_update).total_seconds() >= status_update_interval:
                    self._print_console_status()
                    last_status_update = datetime.now()
                
                # Check if market is open for trading (not just data collection)
                # We'll only execute trades during market hours based on the extended_hours setting
                if self.is_market_open():
                    # Market is open, update all traders and execute trades
                    logger.info("Market is open for trading - processing signals and executing trades")
                    self.update_all_traders()
                    
                    # Save state periodically
                    try:
                        self.save_state()
                    except Exception as e:
                        logger.error(f"Error saving state: {e}")
                    
                    # Wait for next trading update with periodic checks for termination
                    for i in range(int(self.update_interval)):
                        if not self.is_running:
                            break
                        
                        # Update console status if needed during the wait
                        if not self.display_enabled and (datetime.now() - last_status_update).total_seconds() >= status_update_interval:
                            self._print_console_status()
                            last_status_update = datetime.now()
                            
                        time.sleep(1)
                    
                else:
                    # Market is closed for trading, but data collection continues in background
                    logger.info("Market is closed for trading - data collection continues in background")
                    self.wait_for_market_open()
        
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt. Shutting down...")
            self.is_running = False
            
        except Exception as e:
            logger.critical(f"Critical error in main loop: {e}")
            self.stats['errors'] += 1
            self.is_running = False  # Ensure we exit the loop
            
        finally:
            # Save final state
            try:
                self.save_state()
            except Exception as e:
                logger.error(f"Error saving final state: {e}")
            
            # Stop the display if it's running
            if self.display and hasattr(self.display, 'is_running') and self.display.is_running:
                try:
                    self.display.stop()
                    logger.info("Real-time display stopped")
                except Exception as e:
                    logger.error(f"Error stopping display: {e}")
                    
            # Clean up socket server
            if hasattr(self, 'socket_server') and self.socket_server:
                try:
                    self.socket_server.close()
                    logger.info("Socket server closed")
                    # Remove socket file
                    if os.path.exists(SOCKET_PATH):
                        os.unlink(SOCKET_PATH)
                except Exception as e:
                    logger.error(f"Error closing socket server: {e}")
                
            logger.info("Continuous trading service stopped")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Continuous MACD Options Trading Service')
    
    parser.add_argument(
        "symbols", 
        nargs="+",
        help="Symbols to trade"
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        default=60,
        help="Update interval in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--risk", 
        type=float, 
        default=0.02,
        help="Risk percentage per trade (default: 0.02 = 2%)"
    )
    
    parser.add_argument(
        "--style", 
        type=str, 
        choices=['directional', 'income', 'combined'],
        default='directional',
        help="Trading style (default: directional)"
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
        "--extended-hours",
        action="store_true",
        help="Enable trading during extended hours"
    )
    
    parser.add_argument(
        "--warmup",
        type=int,
        default=30,
        help="Warm-up period in minutes before trading begins (default: 30)"
    )
    
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a daemon process in the background"
    )
    
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Disable the real-time display"
    )
    
    parser.add_argument(
        "--display-interval",
        type=float,
        default=0.5,
        help="Update interval for the real-time display in seconds (default: 0.5)"
    )
    
    parser.add_argument(
        "--toggle-display",
        action="store_true",
        help="Toggle the real-time display on/off during execution (press 'd')"
    )
    
    # Add logging options
    parser.add_argument(
        "--log-file",
        default="logs/continuous_trading.log",
        help="Log file path (default: logs/continuous_trading.log)"
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
    
    parser.add_argument(
        "--force-market-open",
        action="store_true",
        help="Force market status to be OPEN (for testing purposes)"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
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
        with open('trader.pid', 'w') as f:
            f.write(pid)
        
        logger.info(f"Daemon started with PID {pid}")
    
    # Create and run the continuous trading service
    trader = ContinuousOptionsTrader(
        symbols=args.symbols,
        trade_style=args.style,
        risk_per_trade=args.risk,
        update_interval=args.interval,
        extended_hours=args.extended_hours,
        warmup_minutes=args.warmup,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        signal_window=args.signal_window,
        always_collect_data=True,  # Always enable continuous data collection
        enable_display=not args.no_display and not args.daemon,  # Disable display in daemon mode
        display_update_interval=args.display_interval,
        force_market_open=args.force_market_open  # Pass the force_market_open flag
    )
    
    # Run the trader
    trader.run()