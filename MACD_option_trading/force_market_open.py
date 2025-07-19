#!/usr/bin/env python3
"""
Simple script to force the market status to OPEN in the continuous_options_trader_service.py file.
This is a temporary solution for testing purposes.
"""

import os
import sys
import re

def force_market_open():
    """Force the market status to OPEN in the continuous_options_trader_service.py file."""
    # Path to the continuous_options_trader_service.py file
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                            'continuous_options_trader_service.py')
    
    # Read the file content
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the _print_console_status method and modify the market status
    pattern = r'(market_status = "OPEN" if .* else "CLOSED")'
    replacement = 'market_status = "OPEN"  # Forced OPEN for testing'
    
    # Replace the pattern
    new_content = re.sub(pattern, replacement, content)
    
    # Write the modified content back to the file
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    print("Market status forced to OPEN in continuous_options_trader_service.py")
    print("This is a temporary modification for testing purposes.")
    print("To revert this change, edit the file manually or run:")
    print("  git checkout continuous_options_trader_service.py")

def restore_market_check():
    """Restore the original market status check in the continuous_options_trader_service.py file."""
    # Path to the continuous_options_trader_service.py file
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                            'continuous_options_trader_service.py')
    
    # Read the file content
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the modified market status and restore the original check
    pattern = r'market_status = "OPEN"  # Forced OPEN for testing'
    replacement = 'market_status = "OPEN" if is_weekday and is_market_hours else "CLOSED"'
    
    # Replace the pattern
    new_content = re.sub(pattern, replacement, content)
    
    # Write the modified content back to the file
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    print("Original market status check restored in continuous_options_trader_service.py")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--restore":
        restore_market_check()
    else:
        force_market_open()
