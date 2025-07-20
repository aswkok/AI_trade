#!/usr/bin/env python3
"""
Test script to verify market hours detection logic.
"""

import logging
import pytz
from datetime import datetime, time

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_market_open():
    """
    Check if the market is currently open using Eastern Time.
    
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
        
        # Debug log the current time in Eastern timezone
        logger.info(f"Current time in ET: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"Market hours: {market_open} to {market_close}")
        logger.info(f"Is regular market hours: {market_open <= current_time <= market_close}")
        
        # Check if it's a weekday
        if now.weekday() < 5:  # Monday=0, Friday=4
            # Regular market hours
            if market_open <= current_time <= market_close:
                logger.info("Regular market is open")
                return True
            # Extended hours
            elif pre_market_start <= current_time < market_open:
                logger.info("Pre-market is open")
                return True
            elif market_close < current_time <= after_hours_end:
                logger.info("After-hours is open")
                return True
            else:
                logger.info("Market is closed (outside trading hours)")
        else:
            logger.info("Market is closed (weekend)")
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking market status: {e}")
        return False

if __name__ == "__main__":
    logger.info("Testing market hours detection")
    
    # Test with current time
    is_open = is_market_open()
    logger.info(f"Market is currently {'OPEN' if is_open else 'CLOSED'}")
    
    # Define market hours for testing specific times
    market_open = time(9, 30)  # 9:30 AM ET
    market_close = time(16, 0)  # 4:00 PM ET
    
    # Test with specific times
    test_times = [
        ("9:00 AM ET", time(9, 0)),
        ("9:30 AM ET", time(9, 30)),
        ("12:00 PM ET", time(12, 0)),
        ("4:00 PM ET", time(16, 0)),
        ("4:30 PM ET", time(16, 30))
    ]
    
    for label, test_time in test_times:
        logger.info(f"\nTesting time: {label}")
        # Create a datetime with today's date and the test time
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(pytz.UTC).astimezone(eastern)
        test_datetime = eastern.localize(datetime.combine(now.date(), test_time))
        
        # Check if this time would be during market hours
        is_market_time = market_open <= test_time <= market_close
        logger.info(f"Is during market hours: {is_market_time}")
