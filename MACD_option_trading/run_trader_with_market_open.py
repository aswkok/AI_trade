#!/usr/bin/env python3
"""
Simplified script to run the continuous options trader service with correct market hours detection.
This script wraps the original continuous_options_trader_service.py and ensures the market status
is correctly displayed as OPEN during market hours.
"""

import os
import sys
import subprocess
import logging
import time
from datetime import datetime
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_market_open(extended_hours=False):
    """
    Check if the US stock market is currently open based on Eastern Time.
    
    Args:
        extended_hours: Whether to include pre-market and after-hours sessions
        
    Returns:
        bool: True if the market is open, False otherwise
    """
    try:
        # Get the current time in US Eastern time
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(pytz.UTC).astimezone(eastern)
        current_time = now.time()
        
        # Define market hours
        pre_market_start = datetime.strptime("04:00", "%H:%M").time()
        market_open = datetime.strptime("09:30", "%H:%M").time()
        market_close = datetime.strptime("16:00", "%H:%M").time()
        after_hours_end = datetime.strptime("20:00", "%H:%M").time()
        
        # Check if it's a weekday
        if now.weekday() < 5:  # Monday=0, Friday=4
            # Regular market hours
            if market_open <= current_time <= market_close:
                logger.info(f"Regular market is OPEN (Current ET: {now.strftime('%H:%M:%S')})")
                return True
                
            # Extended hours if enabled
            if extended_hours:
                # Pre-market hours
                if pre_market_start <= current_time < market_open:
                    logger.info(f"Pre-market is OPEN (Current ET: {now.strftime('%H:%M:%S')})")
                    return True
                    
                # After-hours
                if market_close < current_time <= after_hours_end:
                    logger.info(f"After-hours is OPEN (Current ET: {now.strftime('%H:%M:%S')})")
                    return True
        
        # Market is closed
        logger.info(f"Market is CLOSED (Current ET: {now.strftime('%H:%M:%S')})")
        return False
        
    except Exception as e:
        logger.error(f"Error checking market status: {e}")
        return False

def run_trader():
    """Run the continuous options trader service with market status forced to OPEN during market hours."""
    # Check if the market is currently open
    extended_hours = '--extended-hours' in ' '.join(sys.argv)
    market_open = is_market_open(extended_hours)
    
    # Get the command line arguments
    args = sys.argv[1:]
    
    # Default to NVDA if no symbol is provided
    if not args:
        args = ['NVDA']
    
    # Add --log-level INFO if not specified
    if '--log-level' not in ' '.join(args):
        args.append('--log-level')
        args.append('INFO')
    
    # Path to the continuous_options_trader_service.py file
    service_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                 'continuous_options_trader_service.py')
    
    # Create the command to run
    cmd = ['python', service_script] + args
    
    # Log the command
    logger.info(f"Running command: {' '.join(cmd)}")
    
    # Create a modified environment with FORCE_MARKET_OPEN=1 if the market is open
    env = os.environ.copy()
    if market_open:
        env['FORCE_MARKET_OPEN'] = '1'
        logger.info("Market is currently OPEN - setting FORCE_MARKET_OPEN=1")
    else:
        logger.info("Market is currently CLOSED")
    
    # Run the command with the modified environment
    process = subprocess.Popen(cmd, env=env)
    
    # Wait for the process to complete
    try:
        process.wait()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, terminating process...")
        process.terminate()
        process.wait()
    
    logger.info("Process terminated")

if __name__ == "__main__":
    run_trader()
