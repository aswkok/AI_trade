#!/usr/bin/env python3
"""
Run the continuous options trader service with the market status forced to OPEN.
This script is useful for testing the trading system during market hours.
"""

import os
import sys
import subprocess
import argparse
import warnings

# Suppress specific warnings for cleaner display
warnings.filterwarnings("ignore", category=RuntimeWarning)

def clear_terminal():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Print a nice header for the script."""
    clear_terminal()
    print("\033[1;36m" + "="*80 + "\033[0m")
    print("\033[1;36m║\033[0m" + "\033[1;37m MACD OPTIONS TRADING SYSTEM - FORCED MARKET OPEN MODE \033[0m".center(78) + "\033[1;36m║\033[0m")
    print("\033[1;36m" + "="*80 + "\033[0m")
    print()

def main():
    """Run the continuous options trader service with the market status forced to OPEN."""
    print_header()
    
    parser = argparse.ArgumentParser(description='Run the continuous options trader service with market status forced to OPEN')
    
    # Symbols to trade
    parser.add_argument('symbols', nargs='+', help='Symbols to trade (e.g., NVDA AAPL MSFT)')
    
    # Logging options
    parser.add_argument('--log-level', default='WARNING', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level')
    
    # Trading parameters
    parser.add_argument('--interval', '--update-interval', type=int, default=60, 
                        help='Update interval in seconds (how often to check for signals)')
    parser.add_argument('--warmup', '--warmup-minutes', type=int, default=30, 
                        help='Warmup period in minutes before trading begins')
    parser.add_argument('--risk', '--risk-per-trade', type=float, default=0.02, 
                        help='Risk per trade as a fraction of account value (0.02 = 2%%)')
    parser.add_argument('--extended-hours', action='store_true', 
                        help='Enable trading during extended hours')
    
    # MACD parameters
    parser.add_argument('--fast-window', type=int, default=13, 
                        help='MACD fast EMA window')
    parser.add_argument('--slow-window', type=int, default=21, 
                        help='MACD slow EMA window')
    parser.add_argument('--signal-window', type=int, default=9, 
                        help='MACD signal line window')
    
    # Display options
    parser.add_argument('--no-display', action='store_true', 
                        help='Disable real-time display')
    parser.add_argument('--display-interval', type=float, default=0.5, 
                        help='Display update interval in seconds')
    
    args = parser.parse_args()
    
    # Build the command
    cmd = [
        'python', 'continuous_options_trader_service.py',
        *args.symbols,
        '--log-level', args.log_level,
        '--interval', str(args.interval),
        '--warmup', str(args.warmup),
        '--risk', str(args.risk),
        '--fast-window', str(args.fast_window),
        '--slow-window', str(args.slow_window),
        '--signal-window', str(args.signal_window),
        '--force-market-open'  # Force market status to OPEN
    ]
    
    # Add optional flags
    if args.no_display:
        cmd.append('--no-display')
    
    if args.extended_hours:
        cmd.append('--extended-hours')
        
    if hasattr(args, 'display_interval'):
        cmd.extend(['--display-interval', str(args.display_interval)])
    
    # Print the command with nice formatting
    print("\033[1;33m┌─ Running Command " + "─"*62 + "┐\033[0m")
    print(f"\033[1;33m│\033[0m {' '.join(cmd)}")
    print("\033[1;33m└" + "─"*77 + "┘\033[0m")
    print()
    
    # Print helpful message
    print("\033[1;32m>> Starting trading system with market status forced to OPEN...\033[0m")
    print("\033[1;32m>> Press Ctrl+C to exit\033[0m")
    print()
    
    # Run the command
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\033[1;31m>> Trading system stopped by user\033[0m")
    except Exception as e:
        print(f"\n\033[1;31m>> Error running trading system: {e}\033[0m")

if __name__ == '__main__':
    main()
