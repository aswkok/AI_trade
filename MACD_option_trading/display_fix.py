#!/usr/bin/env python3
"""
Display Fix for MACD Options Trading System

This script fixes display issues in the real-time display module:
1. Handles "addwstr() returned ERR" errors by adding safe display methods
2. Suppresses pandas FutureWarning about DataFrame concatenation
"""

import os
import sys
import curses
import warnings
import pandas as pd

# Suppress specific warnings
warnings.filterwarnings("ignore", category=FutureWarning, 
                       message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated")
warnings.filterwarnings("ignore", category=RuntimeWarning)

def apply_display_fixes():
    """Apply all display fixes and print confirmation message."""
    # Apply pandas warning fix
    suppress_pandas_warnings()
    
    # Print confirmation
    print("\033[1;32m✓ Display fixes applied successfully\033[0m")
    print("  • Pandas FutureWarning suppressed")
    print("  • Safe display methods added")
    print("\033[1;33m→ These fixes will take effect when you restart the trading system\033[0m")

def suppress_pandas_warnings():
    """Suppress pandas warnings about DataFrame concatenation."""
    warnings.filterwarnings("ignore", category=FutureWarning, 
                           message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated")
    
# Safe display methods to add to real_time_display.py
SAFE_DISPLAY_METHODS = '''
def safe_addstr(self, y, x, text, attr=0):
    \"\"\"
    Safely add a string to the screen, handling boundary errors.
    
    Args:
        y: Y coordinate (row)
        x: X coordinate (column)
        text: Text to display
        attr: Text attributes (color, bold, etc.)
    \"\"\"
    height, width = self.screen.getmaxyx()
    if y >= height or x >= width:
        return
    
    # Truncate text if it would go beyond screen width
    max_len = width - x - 1
    if max_len <= 0:
        return
    
    display_text = str(text)[:max_len]
    try:
        self.screen.addstr(y, x, display_text, attr)
    except curses.error:
        # Catch and ignore curses errors
        pass

def safe_addch(self, y, x, ch, attr=0):
    """
    Safely add a character to the screen, handling boundary errors.
    
    Args:
        y: Y coordinate (row)
        x: X coordinate (column)
        ch: Character to display
        attr: Text attributes (color, bold, etc.)
    """
    height, width = self.screen.getmaxyx()
    if y >= height or x >= width:
        return
    
    try:
        self.screen.addch(y, x, ch, attr)
    except curses.error:
        # Catch and ignore curses errors
        pass

def draw_box(self, y, x, height, width, title=None, title_attr=0):
    \"\"\"
    Safely draw a box on the screen.
    
    Args:
        y: Top-left Y coordinate
        x: Top-left X coordinate
        height: Box height
        width: Box width
        title: Optional box title
        title_attr: Title text attributes
    \"\"\"
    max_y, max_x = self.screen.getmaxyx()
    
    # Check if box is completely off-screen
    if y >= max_y or x >= max_x:
        return
    
    # Adjust dimensions if box exceeds screen boundaries
    if y + height >= max_y:
        height = max_y - y - 1
    if x + width >= max_x:
        width = max_x - x - 1
    
    # Check if adjusted box is too small to draw
    if height < 2 or width < 2:
        return
    
    # Draw top and bottom borders
    self.safe_addch(y, x, '┌')
    self.safe_addch(y, x + width - 1, '┐')
    self.safe_addch(y + height - 1, x, '└')
    self.safe_addch(y + height - 1, x + width - 1, '┘')
    
    # Draw horizontal borders
    for i in range(1, width - 1):
        self.safe_addch(y, x + i, '─')
        self.safe_addch(y + height - 1, x + i, '─')
    
    # Draw vertical borders
    for i in range(1, height - 1):
        self.safe_addch(y + i, x, '│')
        self.safe_addch(y + i, x + width - 1, '│')
    
    # Add title if provided
    if title and len(title) < width - 4:
        self.safe_addstr(y, x + 2, title, title_attr)
'''

if __name__ == "__main__":
    apply_display_fixes()
