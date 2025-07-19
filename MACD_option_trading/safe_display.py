#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Safe Display Utilities for MACD Options Trading System

This module provides safe display utilities for the curses-based terminal interface
to prevent "addwstr() returned ERR" errors and other display issues.
"""

import curses
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SafeDisplay:
    """
    Safe display utilities for curses-based terminal interfaces.
    
    This class provides methods for safely displaying text and drawing UI elements
    in a curses-based terminal interface, handling boundary conditions and other
    display issues that might cause "addwstr() returned ERR" errors.
    """
    
    @staticmethod
    def safe_addstr(screen, y, x, text, attr=0):
        """
        Safely add a string to the screen, handling boundary errors.
        
        Args:
            screen: Curses screen object
            y: Y coordinate (row)
            x: X coordinate (column)
            text: Text to display
            attr: Text attributes (color, bold, etc.)
        """
        if screen is None:
            return
            
        try:
            height, width = screen.getmaxyx()
            if y >= height or x >= width:
                return
            
            # Truncate text if it would go beyond screen width
            max_len = width - x - 1
            if max_len <= 0:
                return
            
            display_text = str(text)[:max_len]
            screen.addstr(y, x, display_text, attr)
        except curses.error:
            # Catch and ignore curses errors
            pass
        except Exception as e:
            logger.error(f"Error in safe_addstr: {e}")
    
    @staticmethod
    def safe_addch(screen, y, x, ch, attr=0):
        """
        Safely add a character to the screen, handling boundary errors.
        
        Args:
            screen: Curses screen object
            y: Y coordinate (row)
            x: X coordinate (column)
            ch: Character to display
            attr: Text attributes (color, bold, etc.)
        """
        if screen is None:
            return
            
        try:
            height, width = screen.getmaxyx()
            if y >= height or x >= width:
                return
            
            screen.addch(y, x, ch, attr)
        except curses.error:
            # Catch and ignore curses errors
            pass
        except Exception as e:
            logger.error(f"Error in safe_addch: {e}")
    
    @staticmethod
    def draw_box(screen, y, x, height, width, title=None, title_attr=0):
        """
        Safely draw a box on the screen.
        
        Args:
            screen: Curses screen object
            y: Top-left Y coordinate
            x: Top-left X coordinate
            height: Box height
            width: Box width
            title: Optional box title
            title_attr: Title text attributes
        """
        if screen is None:
            return
            
        try:
            max_y, max_x = screen.getmaxyx()
            
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
            SafeDisplay.safe_addch(screen, y, x, '┌')
            SafeDisplay.safe_addch(screen, y, x + width - 1, '┐')
            SafeDisplay.safe_addch(screen, y + height - 1, x, '└')
            SafeDisplay.safe_addch(screen, y + height - 1, x + width - 1, '┘')
            
            # Draw horizontal borders
            for i in range(1, width - 1):
                SafeDisplay.safe_addch(screen, y, x + i, '─')
                SafeDisplay.safe_addch(screen, y + height - 1, x + i, '─')
            
            # Draw vertical borders
            for i in range(1, height - 1):
                SafeDisplay.safe_addch(screen, y + i, x, '│')
                SafeDisplay.safe_addch(screen, y + i, x + width - 1, '│')
            
            # Add title if provided
            if title and len(title) < width - 4:
                SafeDisplay.safe_addstr(screen, y, x + 2, title, title_attr)
        except Exception as e:
            logger.error(f"Error in draw_box: {e}")
    
    @staticmethod
    def draw_table(screen, start_y, start_x, headers, data, col_widths=None, max_rows=None):
        """
        Safely draw a table on the screen.
        
        Args:
            screen: Curses screen object
            start_y: Starting Y coordinate for the table
            start_x: Starting X coordinate for the table
            headers: List of column headers
            data: List of data rows (each row is a list of values)
            col_widths: List of column widths (if None, calculated automatically)
            max_rows: Maximum number of rows to display (if None, display all)
        """
        if screen is None or not headers or not data:
            return
            
        try:
            height, width = screen.getmaxyx()
            
            # Calculate column widths if not provided
            if col_widths is None:
                # Default to equal widths
                available_width = width - start_x - 2
                col_widths = [available_width // len(headers)] * len(headers)
            
            # Limit number of rows if needed
            if max_rows is None:
                max_rows = height - start_y - 2
            
            display_rows = min(len(data), max_rows)
            
            # Draw headers
            for i, header in enumerate(headers):
                if i < len(col_widths):
                    col_x = start_x + sum(col_widths[:i])
                    SafeDisplay.safe_addstr(screen, start_y, col_x, header[:col_widths[i]-1], curses.A_BOLD)
            
            # Draw data rows
            for row_idx in range(display_rows):
                row = data[row_idx]
                row_y = start_y + row_idx + 1
                
                # Skip if row is outside screen bounds
                if row_y >= height - 1:
                    break
                
                # Draw each cell in the row
                for col_idx, cell in enumerate(row):
                    if col_idx < len(col_widths):
                        col_x = start_x + sum(col_widths[:col_idx])
                        cell_text = str(cell)[:col_widths[col_idx]-1]
                        SafeDisplay.safe_addstr(screen, row_y, col_x, cell_text)
        except Exception as e:
            logger.error(f"Error in draw_table: {e}")
    
    @staticmethod
    def display_status_bar(screen, text, y=None, attr=0):
        """
        Display a status bar at the bottom of the screen.
        
        Args:
            screen: Curses screen object
            text: Status text to display
            y: Y coordinate (if None, use last line of screen)
            attr: Text attributes
        """
        if screen is None:
            return
            
        try:
            height, width = screen.getmaxyx()
            
            # Use last line if y not specified
            if y is None:
                y = height - 1
            
            # Clear the line first
            SafeDisplay.safe_addstr(screen, y, 0, " " * (width - 1))
            
            # Display the status text
            SafeDisplay.safe_addstr(screen, y, 0, text[:width-1], attr)
        except Exception as e:
            logger.error(f"Error in display_status_bar: {e}")

# Singleton instance for easy access
safe_display = SafeDisplay()
