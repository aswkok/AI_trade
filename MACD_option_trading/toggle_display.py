#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Toggle Display Script for MACD Options Trading System

This script allows toggling the real-time display on/off without restarting
the continuous options trader service. It connects to a running service
and sends a command to toggle the display.
"""

import os
import sys
import time
import logging
import json
import socket
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DISPLAY_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "display_status.json")
DISPLAY_COMMAND_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "display_command.json")
DISPLAY_COMMAND_PROCESSED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "display_command_processed.json")

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

def send_toggle_command(enable=None):
    """Send a toggle command to the running service via command file."""
    # Determine the command based on the enable parameter
    if enable is None:
        # Toggle based on current status
        current_status = get_current_status()
        command = "DISABLE_DISPLAY" if current_status else "ENABLE_DISPLAY"
        action_str = "disabling" if current_status else "enabling"
    else:
        # Set to specific state
        command = "ENABLE_DISPLAY" if enable else "DISABLE_DISPLAY"
        action_str = "enabling" if enable else "disabling"
    
    print(f"Sending command to {action_str} display...")
    
    # Check if the service is running by checking if the processed file exists and was updated recently
    if not os.path.exists(DISPLAY_COMMAND_PROCESSED_FILE):
        logger.error(f"Command processed file not found at {DISPLAY_COMMAND_PROCESSED_FILE}")
        print(f"\033[1;31mError: Command processed file not found\033[0m")
        print("Make sure the continuous options trader service is running.")
        return False
    
    try:
        # Read the processed file to check when it was last updated
        with open(DISPLAY_COMMAND_PROCESSED_FILE, 'r') as f:
            processed_data = json.load(f)
            processed_at = processed_data.get('processed_at', '')
            
            # Check if the processed file was updated in the last 5 minutes
            if processed_at:
                try:
                    processed_time = datetime.fromisoformat(processed_at)
                    now = datetime.now()
                    if (now - processed_time).total_seconds() > 300:  # 5 minutes
                        logger.warning("Command processed file is stale (older than 5 minutes)")
                        print("\033[1;33mWarning: Command processed file is stale\033[0m")
                        print("The service might not be running. Proceeding anyway...")
                except Exception as e:
                    logger.error(f"Error parsing processed time: {e}")
    except Exception as e:
        logger.error(f"Error reading processed file: {e}")
        print(f"\033[1;31mError reading processed file: {e}\033[0m")
        print("Proceeding anyway...")
    
    # Write the command to the command file
    try:
        with open(DISPLAY_COMMAND_FILE, 'w') as f:
            json.dump({
                'command': command,
                'timestamp': datetime.now().isoformat()
            }, f)
        logger.info(f"Command {command} written to command file")
        
        # Wait for the command to be processed (up to 5 seconds)
        max_wait_time = 5  # seconds
        wait_interval = 0.5  # seconds
        attempts = int(max_wait_time / wait_interval)
        
        for attempt in range(attempts):
            time.sleep(wait_interval)
            
            # Check if the command has been processed
            try:
                with open(DISPLAY_COMMAND_PROCESSED_FILE, 'r') as f:
                    processed_data = json.load(f)
                    processed_command = processed_data.get('command', '')
                    processed_timestamp = processed_data.get('timestamp', '')
                    status = processed_data.get('status', '')
                    
                    # Check if our command has been processed
                    command_timestamp = datetime.now().isoformat()
                    with open(DISPLAY_COMMAND_FILE, 'r') as cmd_file:
                        command_data = json.load(cmd_file)
                        command_timestamp = command_data.get('timestamp', '')
                    
                    if processed_command == command and processed_timestamp == command_timestamp:
                        logger.info(f"Command {command} processed with status {status}")
                        
                        if status == "OK":
                            logger.info(f"Display {'enabled' if 'ENABLE' in command else 'disabled'} successfully")
                            print(f"\033[1;32mDisplay {'enabled' if 'ENABLE' in command else 'disabled'} successfully\033[0m")
                            return True
                        elif status == "ALREADY_ENABLED" or status == "ALREADY_DISABLED":
                            logger.info(f"Display is already {'enabled' if 'ENABLE' in command else 'disabled'}")
                            print(f"\033[1;33mDisplay is already {'enabled' if 'ENABLE' in command else 'disabled'}\033[0m")
                            return True
                        else:
                            logger.warning(f"Unexpected status: {status}")
                            print(f"\033[1;33mUnexpected status: {status}\033[0m")
                            return False
            except Exception as e:
                logger.error(f"Error checking if command was processed: {e}")
        
        # If we get here, the command wasn't processed within the timeout
        logger.warning("Command not processed within timeout")
        print("\033[1;33mWarning: Command not processed within timeout\033[0m")
        print("The service might be busy or not running. Try again later.")
        return False
        
    except Exception as e:
        logger.error(f"Error writing command to file: {e}")
        print(f"\033[1;31mError writing command to file: {e}\033[0m")
        return False

def get_display_status():
    """Get the current display status using the command file approach."""
    print("Checking display status...")
    
    # Check if the service is running by checking if the processed file exists
    if not os.path.exists(DISPLAY_COMMAND_PROCESSED_FILE):
        logger.error(f"Command processed file not found at {DISPLAY_COMMAND_PROCESSED_FILE}")
        print(f"\033[1;31mError: Command processed file not found\033[0m")
        print("Make sure the continuous options trader service is running.")
        # Fall back to checking the status file
        status = get_current_status()
        print(f"Display is currently {'enabled' if status else 'disabled'} (from status file)")
        return status
    
    # Write the STATUS command to the command file
    try:
        with open(DISPLAY_COMMAND_FILE, 'w') as f:
            json.dump({
                'command': 'STATUS',
                'timestamp': datetime.now().isoformat()
            }, f)
        logger.info("STATUS command written to command file")
        
        # Wait for the command to be processed (up to 5 seconds)
        max_wait_time = 5  # seconds
        wait_interval = 0.5  # seconds
        attempts = int(max_wait_time / wait_interval)
        
        for attempt in range(attempts):
            time.sleep(wait_interval)
            
            # Check if the command has been processed
            try:
                with open(DISPLAY_COMMAND_PROCESSED_FILE, 'r') as f:
                    processed_data = json.load(f)
                    processed_command = processed_data.get('command', '')
                    processed_timestamp = processed_data.get('timestamp', '')
                    status = processed_data.get('status', '')
                    
                    # Check if our command has been processed
                    command_timestamp = datetime.now().isoformat()
                    with open(DISPLAY_COMMAND_FILE, 'r') as cmd_file:
                        command_data = json.load(cmd_file)
                        command_timestamp = command_data.get('timestamp', '')
                    
                    if processed_command == 'STATUS' and processed_timestamp == command_timestamp:
                        logger.info(f"STATUS command processed with status {status}")
                        
                        if status == "ENABLED":
                            print("\033[1;32mDisplay is currently enabled\033[0m")
                            return True
                        elif status == "DISABLED":
                            print("\033[1;33mDisplay is currently disabled\033[0m")
                            return False
                        else:
                            logger.warning(f"Unexpected status: {status}")
                            # Fall back to checking the status file
                            status_from_file = get_current_status()
                            print(f"Display is currently {'enabled' if status_from_file else 'disabled'} (from status file)")
                            return status_from_file
            except Exception as e:
                logger.error(f"Error checking if command was processed: {e}")
        
        # If we get here, the command wasn't processed within the timeout
        logger.warning("STATUS command not processed within timeout")
        print("\033[1;33mWarning: STATUS command not processed within timeout\033[0m")
        print("The service might be busy or not running.")
        # Fall back to checking the status file
        status = get_current_status()
        print(f"Display is currently {'enabled' if status else 'disabled'} (from status file)")
        return status
        
    except Exception as e:
        logger.error(f"Error writing STATUS command to file: {e}")
        print(f"\033[1;31mError writing STATUS command to file: {e}\033[0m")
        # Fall back to checking the status file
        status = get_current_status()
        print(f"Display is currently {'enabled' if status else 'disabled'} (from status file)")
        return status

def main():
    """Main function to toggle the display."""
    parser = argparse.ArgumentParser(description="Toggle the real-time display for MACD Options Trading System")
    parser.add_argument(
        "--on", 
        action="store_true",
        help="Turn the display on"
    )
    parser.add_argument(
        "--off", 
        action="store_true",
        help="Turn the display off"
    )
    parser.add_argument(
        "--status", 
        action="store_true",
        help="Show the current display status"
    )
    
    args = parser.parse_args()
    
    if args.on:
        send_toggle_command(enable=True)
    elif args.off:
        send_toggle_command(enable=False)
    elif args.status:
        # First try to get status from the service directly
        status = get_display_status()
        if status is not None:
            print(f"\033[1;{'32' if status else '31'}mDisplay is currently {'enabled' if status else 'disabled'}\033[0m")
        else:
            # Fall back to reading the status file
            status = get_current_status()
            print(f"\033[1;{'32' if status else '31'}mDisplay is currently {'enabled' if status else 'disabled'} (from status file)\033[0m")
    else:
        # Toggle the current state
        send_toggle_command()

    # Check for conflicting arguments
    if args.on and args.off:
        logger.error("Cannot specify both --on and --off")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
