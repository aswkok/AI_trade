#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script for the safe display functionality.

This script tests the safe display functionality to ensure that it properly handles
boundary conditions and prevents "addwstr() returned ERR" errors.
"""

import os
import sys
import time
import curses
import logging
import random
from datetime import datetime

# Import our modules
from real_time_display import RealTimeDisplay
from safe_display import safe_display

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='test_safe_display.log',  # Log to file to avoid interference with curses
)
logger = logging.getLogger(__name__)

def test_boundary_conditions(stdscr):
    """
    Test boundary conditions for the safe display functionality.
    
    Args:
        stdscr: Curses standard screen
    """
    # Initialize colors
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)  # Green text
    curses.init_pair(2, curses.COLOR_RED, -1)    # Red text
    curses.init_pair(3, curses.COLOR_YELLOW, -1) # Yellow text
    curses.init_pair(4, curses.COLOR_BLUE, -1)   # Blue text
    curses.init_pair(5, curses.COLOR_CYAN, -1)   # Cyan text
    
    # Get screen dimensions
    height, width = stdscr.getmaxyx()
    
    # Clear screen
    stdscr.clear()
    
    # Test 1: Display text at screen boundaries
    safe_display.safe_addstr(stdscr, 0, 0, "Top-left corner")
    safe_display.safe_addstr(stdscr, 0, width-1, "X")  # Should be safely handled
    safe_display.safe_addstr(stdscr, height-1, 0, "Bottom-left corner")
    safe_display.safe_addstr(stdscr, height-1, width-1, "X")  # Should be safely handled
    
    # Test 2: Display text beyond screen boundaries
    safe_display.safe_addstr(stdscr, height, 0, "Beyond bottom")  # Should be safely handled
    safe_display.safe_addstr(stdscr, 0, width, "Beyond right")    # Should be safely handled
    safe_display.safe_addstr(stdscr, height, width, "Beyond both") # Should be safely handled
    
    # Test 3: Display very long text
    long_text = "This is a very long text that would normally cause an error if it extends beyond the screen width " + "X" * 200
    safe_display.safe_addstr(stdscr, 2, 0, long_text)  # Should be truncated safely
    
    # Test 4: Draw box at screen boundaries
    safe_display.draw_box(stdscr, 4, 0, 3, 20, "Box at left edge")
    safe_display.draw_box(stdscr, 4, width-10, 3, 20, "Box at right")  # Should be adjusted safely
    safe_display.draw_box(stdscr, height-5, 0, 10, 20, "Box at bottom")  # Should be adjusted safely
    
    # Test 5: Draw box beyond screen boundaries
    safe_display.draw_box(stdscr, height, 0, 3, 20, "Beyond bottom")  # Should be safely handled
    safe_display.draw_box(stdscr, 0, width, 3, 20, "Beyond right")    # Should be safely handled
    
    # Test 6: Draw box with very long title
    long_title = "Very long box title " + "X" * 100
    safe_display.draw_box(stdscr, 8, 10, 3, 20, long_title)  # Title should be truncated safely
    
    # Test 7: Display status bar
    safe_display.display_status_bar(stdscr, "Press any key to continue...", height-1, curses.A_BOLD)
    
    # Refresh screen
    stdscr.refresh()
    
    # Wait for user input
    stdscr.getch()

def test_real_time_display():
    """Test the real-time display with boundary conditions."""
    logger.info("Starting real-time display test...")
    
    # Create a real-time display instance
    display = RealTimeDisplay(update_interval=0.5, max_history=100)
    
    # Register a symbol
    display.register_symbol("SPY")
    
    # Add some test system messages with boundary conditions
    for i in range(20):
        # Create some very long messages to test boundary conditions
        long_message = f"TEST LONG MESSAGE {i}: " + "X" * 200
        display.add_system_message(long_message)
        
        # Add some test messages with different colors
        if i % 3 == 0:
            display.add_system_message(f"BULLISH SIGNAL {i}: Testing BUY message display")
        elif i % 3 == 1:
            display.add_system_message(f"BEARISH SIGNAL {i}: Testing SELL message display")
        else:
            display.add_system_message(f"TRADE EXECUTED {i}: Testing trade message display")
    
    # Start the display
    display.start()
    
    # Add some test quotes with boundary conditions
    for i in range(10):
        # Create a quote with very long values
        quote_data = {
            'timestamp': datetime.now(),
            'bid': 100.0 + i,
            'ask': 100.1 + i,
            'mid': 100.05 + i,
            'MACD': 0.5 + i / 10,
            'signal': 0.4 + i / 10,
            'histogram': 0.1 + i / 10,
            'MACD_position': "ABOVE" if i % 2 == 0 else "BELOW",
            'crossover': i % 5 == 0,
            'crossunder': i % 5 == 1,
            'very_long_field': "X" * 200,  # Very long field to test boundary conditions
        }
        
        # Update the quote
        display.update_quote("SPY", quote_data)
        
        # Add a trade if it's a crossover or crossunder
        if quote_data['crossover'] or quote_data['crossunder']:
            trade_data = {
                'timestamp': datetime.now(),
                'symbol': "SPY",
                'action': "BUY" if quote_data['crossover'] else "SELL",
                'quantity': random.randint(1, 10),
                'price': quote_data['mid'],
                'strategy': "MACD_TEST_" + "X" * 50  # Very long strategy name
            }
            display.add_trade(trade_data)
        
        # Sleep for a bit
        time.sleep(1)
    
    # Wait for user to exit
    try:
        print("Press Ctrl+C to exit the test")
        while display.is_running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        # Stop the display
        display.stop()
        logger.info("Real-time display test completed")

def main():
    """Run the safe display tests."""
    logger.info("Starting safe display tests...")
    
    # First test the basic boundary conditions with curses
    curses.wrapper(test_boundary_conditions)
    
    # Then test the real-time display
    test_real_time_display()
    
    logger.info("All tests completed successfully")

if __name__ == "__main__":
    main()
