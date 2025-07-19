#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Toggle Display Service for MACD Options Trading System

This script provides a way to toggle the real-time display on and off
without affecting the continuous options trader service.
"""

import os
import sys
import time
import json
import socket
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DISPLAY_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "display_status.json")
SOCKET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "display_socket")

def get_current_status():
    """Get the current display status."""
    if os.path.exists(DISPLAY_STATUS_FILE):
        try:
            with open(DISPLAY_STATUS_FILE, 'r') as f:
                status = json.load(f)
                return status.get('enabled', False)
        except Exception as e:
            logger.error(f"Error reading display status: {e}")
    return False

def set_status(enabled):
    """Set the display status."""
    try:
        with open(DISPLAY_STATUS_FILE, 'w') as f:
            json.dump({'enabled': enabled}, f)
        return True
    except Exception as e:
        logger.error(f"Error writing display status: {e}")
        return False

def send_toggle_command(enabled):
    """Send a toggle command to the running service."""
    try:
        # Create a Unix domain socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        
        # Connect to the socket
        sock.connect(SOCKET_PATH)
        
        # Send the command
        command = "ENABLE_DISPLAY" if enabled else "DISABLE_DISPLAY"
        sock.sendall(command.encode('utf-8'))
        
        # Wait for response
        response = sock.recv(1024).decode('utf-8')
        
        # Close the socket
        sock.close()
        
        return response == "OK"
    except Exception as e:
        logger.error(f"Error sending toggle command: {e}")
        return False

def toggle_display():
    """Toggle the display on or off."""
    # Get current status
    current_status = get_current_status()
    
    # Toggle status
    new_status = not current_status
    
    # Set new status
    if set_status(new_status):
        logger.info(f"Display status set to {'enabled' if new_status else 'disabled'}")
    else:
        logger.error("Failed to set display status")
        return False
    
    # Send toggle command
    if send_toggle_command(new_status):
        logger.info(f"Display toggle command sent successfully")
        return True
    else:
        logger.warning("Failed to send toggle command, but status file was updated")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Toggle Display Service for MACD Options Trading System")
    parser.add_argument("--enable", action="store_true", help="Enable the display")
    parser.add_argument("--disable", action="store_true", help="Disable the display")
    parser.add_argument("--status", action="store_true", help="Show current display status")
    
    args = parser.parse_args()
    
    # Check if any arguments were provided
    if not (args.enable or args.disable or args.status):
        # No arguments, toggle the display
        toggle_display()
        return
    
    # Get current status
    current_status = get_current_status()
    
    if args.status:
        print(f"Display is currently {'enabled' if current_status else 'disabled'}")
        return
    
    if args.enable and args.disable:
        print("Error: Cannot both enable and disable the display")
        return
    
    if args.enable and not current_status:
        if set_status(True) and send_toggle_command(True):
            print("Display enabled")
        else:
            print("Failed to enable display")
    elif args.disable and current_status:
        if set_status(False) and send_toggle_command(False):
            print("Display disabled")
        else:
            print("Failed to disable display")
    else:
        print(f"Display is already {'enabled' if current_status else 'disabled'}")

if __name__ == "__main__":
    main()
