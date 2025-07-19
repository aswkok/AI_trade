#!/usr/bin/env python3
"""
Script to run the continuous options trader service with market status forced to OPEN.
This is a temporary solution for testing purposes.
"""

import sys
import os
import subprocess
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Run the continuous options trader service with market status forced to OPEN."""
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
    logger.info("Market status will be forced to OPEN for testing purposes")
    
    # Create a modified environment with FORCE_MARKET_OPEN=1
    env = os.environ.copy()
    env['FORCE_MARKET_OPEN'] = '1'
    
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
    main()
