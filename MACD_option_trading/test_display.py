#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script for the real-time display functionality with the continuous options trader service.
"""

import os
import sys
import time
import logging
import threading
import random
import numpy as np
from datetime import datetime, timedelta

# Import the continuous options trader service
from continuous_options_trader_service import ContinuousOptionsTrader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_test_data(display, symbol="SPY", duration=300, interval=1.0):
    """
    Generate test data for the real-time display.
    
    Args:
        display: RealTimeDisplay instance
        symbol: Symbol to generate data for
        duration: Duration in seconds to generate data for
        interval: Interval between data points in seconds
    """
    logger.info(f"Starting test data generation for {symbol}...")
    
    # Initial price
    price = 450.0  # Starting price for SPY
    
    # MACD parameters
    fast_ema = price
    slow_ema = price
    signal_line = price
    
    # Generate data points
    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=duration)
    
    while datetime.now() < end_time and display.is_running:
        # Generate a new price with some random walk
        price += random.uniform(-1.0, 1.0)
        
        # Calculate bid and ask
        bid = price - 0.05
        ask = price + 0.05
        
        # Update EMAs
        fast_alpha = 2.0 / (12 + 1)
        slow_alpha = 2.0 / (26 + 1)
        signal_alpha = 2.0 / (9 + 1)
        
        fast_ema = fast_ema * (1 - fast_alpha) + price * fast_alpha
        slow_ema = slow_ema * (1 - slow_alpha) + price * slow_alpha
        
        # Calculate MACD line
        macd_line = fast_ema - slow_ema
        
        # Update signal line
        signal_line = signal_line * (1 - signal_alpha) + macd_line * signal_alpha
        
        # Calculate histogram
        histogram = macd_line - signal_line
        
        # Determine position
        position = "ABOVE" if macd_line > signal_line else "BELOW"
        
        # Determine crossover/crossunder (randomly for testing)
        crossover = False
        crossunder = False
        
        if random.random() < 0.05:  # 5% chance of signal
            if macd_line > signal_line:
                crossover = True
            else:
                crossunder = True
        
        # Create quote data
        quote_data = {
            'timestamp': datetime.now(),
            'bid': bid,
            'ask': ask,
            'mid': (bid + ask) / 2,
            'MACD': macd_line,
            'signal': signal_line,
            'histogram': histogram,
            'MACD_position': position,
            'crossover': crossover,
            'crossunder': crossunder,
            'volume': random.randint(1000, 10000)
        }
        
        # Update the display
        display.update_quote(symbol, quote_data)
        
        # Add system message occasionally
        if random.random() < 0.1:  # 10% chance
            display.add_system_message(f"Market update for {symbol}: Price {price:.2f}")
        
        # Add signal if crossover/crossunder
        if crossover or crossunder:
            signal_data = {
                'signal': 1 if crossover else -1,
                'position': position,
                'crossover': crossover,
                'crossunder': crossunder,
                'MACD': macd_line,
                'signal_line': signal_line,
                'histogram': histogram
            }
            display.add_signal(symbol, signal_data)
            
            # Add trade for signals
            trade_data = {
                'timestamp': datetime.now(),
                'symbol': symbol,
                'action': "BUY" if crossover else "SELL",
                'quantity': random.randint(1, 10),
                'price': (bid + ask) / 2,
                'strategy': "MACD_STRATEGY"
            }
            display.add_trade(trade_data)
        
        # Sleep for the interval
        time.sleep(interval)
    
    logger.info("Test data generation completed")

def main():
    """Run a test of the real-time display with the continuous options trader service."""
    
    # Import here to avoid circular imports
    from real_time_display import RealTimeDisplay
    
    logger.info("Starting test of real-time display...")
    
    # Create a real-time display instance
    display = RealTimeDisplay(update_interval=0.5, max_history=100)
    
    # Register a symbol
    display.register_symbol("SPY")
    
    # Add some test system messages to verify boundary handling
    for i in range(50):
        # Create some very long messages to test boundary conditions
        if i % 5 == 0:
            long_message = f"TEST LONG MESSAGE {i}: " + "X" * 200
            display.add_system_message(long_message)
        
        # Add some test messages with different colors
        if i % 3 == 0:
            display.add_system_message(f"BULLISH SIGNAL {i}: Testing BUY message display")
        elif i % 3 == 1:
            display.add_system_message(f"BEARISH SIGNAL {i}: Testing SELL message display")
        else:
            display.add_system_message(f"TRADE EXECUTED {i}: Testing trade message display")
    
    try:
        # Start the display
        display.start()
        
        # Generate test data in a separate thread
        data_thread = threading.Thread(
            target=generate_test_data,
            args=(display, "SPY", 300, 0.5),
            daemon=True
        )
        data_thread.start()
        
        # Add some test trades with very long descriptions
        for i in range(10):
            trade_data = {
                'timestamp': datetime.now(),
                'symbol': "SPY",
                'action': "BUY" if i % 2 == 0 else "SELL",
                'quantity': random.randint(1, 10),
                'price': 450.0 + random.uniform(-10.0, 10.0),
                'strategy': "MACD_STRATEGY_" + "X" * 50  # Very long strategy name
            }
            display.add_trade(trade_data)
            time.sleep(1)  # Add a small delay between trades
        
        # Wait for user to press Ctrl+C
        print("Press Ctrl+C to exit the test")
        while display.is_running:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    finally:
        # Stop the display
        if hasattr(display, 'is_running') and display.is_running:
            display.stop()
        logger.info("Test completed")

if __name__ == "__main__":
    main()
