#!/usr/bin/env python3
"""
Market Hours Checker

This script provides a simple way to check if the US stock market is currently open
based on the current time in Eastern Time (ET). It handles regular market hours,
pre-market, and after-hours trading sessions.

Usage:
    python market_hours_checker.py [--extended]

Options:
    --extended    Include pre-market (4:00 AM - 9:30 AM ET) and 
                  after-hours (4:00 PM - 8:00 PM ET) sessions
"""

import argparse
import logging
from datetime import datetime, time
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
        pre_market_start = time(4, 0)  # 4:00 AM ET
        market_open = time(9, 30)  # 9:30 AM ET
        market_close = time(16, 0)  # 4:00 PM ET
        after_hours_end = time(20, 0)  # 8:00 PM ET
        
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

def main():
    """Main function to check market hours."""
    parser = argparse.ArgumentParser(description='Check if the US stock market is currently open.')
    parser.add_argument('--extended', action='store_true', help='Include pre-market and after-hours sessions')
    args = parser.parse_args()
    
    # Print current time in various timezones
    utc_now = datetime.now(pytz.UTC)
    eastern = pytz.timezone('US/Eastern')
    eastern_now = utc_now.astimezone(eastern)
    local_now = datetime.now()
    
    print("\n=== CURRENT TIME ===")
    print(f"UTC:     {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Eastern: {eastern_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Local:   {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if market is open
    print("\n=== MARKET STATUS ===")
    is_open = is_market_open(args.extended)
    
    # Print market hours
    print("\n=== MARKET HOURS (Eastern Time) ===")
    print("Regular Market: 9:30 AM - 4:00 PM ET (Monday-Friday)")
    if args.extended:
        print("Pre-Market:     4:00 AM - 9:30 AM ET (Monday-Friday)")
        print("After-Hours:    4:00 PM - 8:00 PM ET (Monday-Friday)")
    
    # Print final status
    print("\n=== RESULT ===")
    if is_open:
        print("Market is currently OPEN")
    else:
        print("Market is currently CLOSED")

if __name__ == "__main__":
    main()
