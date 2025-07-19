#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MACD Signal Comparison Tool

This script compares MACD signals generated using two different price sources:
1. Mid-price (bid+ask)/2 from Yahoo Finance
2. Closing price from Yahoo Finance

The goal is to evaluate which approach provides more accurate or consistent
MACD signal generation for trading decisions.
"""

import os
import time
import logging
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dotenv import load_dotenv
from tabulate import tabulate

# Import our custom monitors
from yahoo_quote_monitor import YahooQuoteMonitor
from yahoo_close_monitor import YahooCloseQuoteMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("macd_comparison.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MACDSignalComparator:
    """
    Compares MACD signals from different price sources to evaluate effectiveness.
    """
    
    def __init__(self, symbol, interval_seconds=5, fast_window=13, slow_window=21, signal_window=9,
                max_records=500, duration_minutes=60):
        """
        Initialize the MACD signal comparator.
        
        Args:
            symbol: Stock symbol to analyze
            interval_seconds: Update interval in seconds
            fast_window: Fast EMA window for MACD
            slow_window: Slow EMA window for MACD
            signal_window: Signal line window for MACD
            max_records: Maximum number of records to keep
            duration_minutes: How long to run the comparison
        """
        # Load environment variables
        load_dotenv(override=True)
        
        # Store configuration
        self.symbol = symbol
        self.interval_seconds = interval_seconds
        self.duration_minutes = duration_minutes
        
        # Store MACD parameters
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        
        # Initialize the monitors
        logger.info(f"Initializing MACD signal comparator for {symbol}")
        
        # 1. Mid-price monitor
        self.mid_monitor = YahooQuoteMonitor(
            symbol=symbol,
            max_records=max_records,
            interval_seconds=interval_seconds,
            fast_window=fast_window,
            slow_window=slow_window,
            signal_window=signal_window
        )
        
        # 2. Close price monitor
        self.close_monitor = YahooCloseQuoteMonitor(
            symbol=symbol,
            max_records=max_records,
            interval_seconds=interval_seconds,
            fast_window=fast_window,
            slow_window=slow_window,
            signal_window=signal_window
        )
        
        # Signal tracking
        self.mid_signals = []
        self.close_signals = []
        self.signal_comparison = pd.DataFrame(columns=[
            'timestamp', 'mid_price', 'close_price', 
            'mid_macd', 'close_macd', 
            'mid_signal', 'close_signal',
            'mid_histogram', 'close_histogram',
            'mid_position', 'close_position',
            'mid_crossover', 'close_crossover',
            'mid_crossunder', 'close_crossunder',
            'divergence'  # True when signals disagree
        ])
        
        logger.info(f"MACD Signal Comparator initialized for {symbol}")
        logger.info(f"MACD Parameters: Fast={fast_window}, Slow={slow_window}, Signal={signal_window}")
        logger.info(f"Update Interval: {interval_seconds} seconds")
        logger.info(f"Duration: {duration_minutes} minutes")
    
    def update_comparison(self):
        """
        Update the comparison dataframe with the latest signals from both monitors.
        """
        # Get the latest MACD signals
        mid_signal = self.mid_monitor.get_macd_signal()
        close_signal = self.close_monitor.get_macd_signal()
        
        # If either monitor doesn't have a valid signal yet, do nothing
        if mid_signal['macd_position'] is None or close_signal['macd_position'] is None:
            logger.info("Not enough data for MACD comparison yet")
            return
        
        # Get the latest timestamps
        mid_timestamp = mid_signal.get('timestamp', datetime.now())
        close_timestamp = close_signal.get('timestamp', datetime.now())
        
        # Use the most recent timestamp
        timestamp = max(mid_timestamp, close_timestamp)
        
        # Get the latest prices
        mid_price = mid_signal.get('mid_price', 0.0)
        close_price = close_signal.get('mid_price', 0.0)  # The close monitor still has 'mid_price' in its signal dict
        
        # Check if the signals diverge
        divergence = mid_signal['macd_position'] != close_signal['macd_position']
        
        # Create a new row for the comparison dataframe
        new_row = pd.DataFrame({
            'timestamp': [timestamp],
            'mid_price': [mid_price],
            'close_price': [close_price],
            'mid_macd': [mid_signal['macd_value']],
            'close_macd': [close_signal['macd_value']],
            'mid_signal': [mid_signal['signal_value']],
            'close_signal': [close_signal['signal_value']],
            'mid_histogram': [mid_signal['histogram']],
            'close_histogram': [close_signal['histogram']],
            'mid_position': [mid_signal['macd_position']],
            'close_position': [close_signal['macd_position']],
            'mid_crossover': [mid_signal['crossover']],
            'close_crossover': [close_signal['crossover']],
            'mid_crossunder': [mid_signal['crossunder']],
            'close_crossunder': [close_signal['crossunder']],
            'divergence': [divergence]
        })
        
        # Append to dataframe
        self.signal_comparison = pd.concat([self.signal_comparison, new_row], ignore_index=True)
        
        # Log signal comparison
        if divergence:
            logger.warning(f"SIGNAL DIVERGENCE DETECTED: Mid={mid_signal['macd_position']}, Close={close_signal['macd_position']}")
        
        # Log crossovers and crossunders
        if mid_signal['crossover'] and close_signal['crossover']:
            logger.info(f"BOTH MONITORS: BULLISH CROSSOVER at {timestamp}")
        elif mid_signal['crossover']:
            logger.info(f"MID PRICE ONLY: BULLISH CROSSOVER at {timestamp}")
        elif close_signal['crossover']:
            logger.info(f"CLOSE PRICE ONLY: BULLISH CROSSOVER at {timestamp}")
            
        if mid_signal['crossunder'] and close_signal['crossunder']:
            logger.info(f"BOTH MONITORS: BEARISH CROSSUNDER at {timestamp}")
        elif mid_signal['crossunder']:
            logger.info(f"MID PRICE ONLY: BEARISH CROSSUNDER at {timestamp}")
        elif close_signal['crossunder']:
            logger.info(f"CLOSE PRICE ONLY: BEARISH CROSSUNDER at {timestamp}")
    
    def display_comparison(self):
        """
        Display the current comparison between mid-price and close-price MACD signals.
        """
        if self.signal_comparison.empty:
            print("No comparison data available yet.")
            return
        
        # Get the latest comparison
        latest = self.signal_comparison.iloc[-1]
        
        # Display the comparison
        print("\n" + "=" * 100)
        print(f"MACD Signal Comparison for {self.symbol}")
        print("=" * 100)
        
        # Format the timestamp
        timestamp_str = latest['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        
        # Display the prices
        print(f"Time: {timestamp_str}")
        print(f"Mid Price: ${latest['mid_price']:.2f} | Close Price: ${latest['close_price']:.2f}")
        
        # Display MACD information
        print("\nMACD Information:")
        print(f"Mid-Price MACD: {latest['mid_macd']:.4f} | Close-Price MACD: {latest['close_macd']:.4f}")
        print(f"Mid-Price Signal: {latest['mid_signal']:.4f} | Close-Price Signal: {latest['close_signal']:.4f}")
        print(f"Mid-Price Histogram: {latest['mid_histogram']:.4f} | Close-Price Histogram: {latest['close_histogram']:.4f}")
        print(f"Mid-Price Position: {latest['mid_position']} | Close-Price Position: {latest['close_position']}")
        
        # Display signal events
        mid_event = ""
        if latest['mid_crossover']:
            mid_event = "BULLISH CROSSOVER"
        elif latest['mid_crossunder']:
            mid_event = "BEARISH CROSSUNDER"
            
        close_event = ""
        if latest['close_crossover']:
            close_event = "BULLISH CROSSOVER"
        elif latest['close_crossunder']:
            close_event = "BEARISH CROSSUNDER"
        
        if mid_event or close_event:
            print("\nSignal Events:")
            if mid_event:
                print(f"Mid-Price: {mid_event}")
            if close_event:
                print(f"Close-Price: {close_event}")
        
        # Display divergence warning
        if latest['divergence']:
            print("\n⚠️ SIGNAL DIVERGENCE DETECTED ⚠️")
            print(f"Mid-Price Position: {latest['mid_position']} | Close-Price Position: {latest['close_position']}")
        
        # Display statistics
        if len(self.signal_comparison) > 1:
            # Calculate divergence percentage
            divergence_count = self.signal_comparison['divergence'].sum()
            divergence_pct = (divergence_count / len(self.signal_comparison)) * 100
            
            # Count crossovers and crossunders
            mid_crossovers = self.signal_comparison['mid_crossover'].sum()
            close_crossovers = self.signal_comparison['close_crossover'].sum()
            mid_crossunders = self.signal_comparison['mid_crossunder'].sum()
            close_crossunders = self.signal_comparison['close_crossunder'].sum()
            
            print("\nStatistics:")
            print(f"Total Comparisons: {len(self.signal_comparison)}")
            print(f"Divergence Count: {divergence_count} ({divergence_pct:.2f}%)")
            print(f"Mid-Price Crossovers: {mid_crossovers} | Close-Price Crossovers: {close_crossovers}")
            print(f"Mid-Price Crossunders: {mid_crossunders} | Close-Price Crossunders: {close_crossunders}")
        
        # Display recent comparisons in a table
        print("\nRecent Comparisons:")
        
        # Get the last few rows
        num_rows = min(10, len(self.signal_comparison))
        recent = self.signal_comparison.tail(num_rows).copy()
        
        # Format the timestamps
        recent['time'] = recent['timestamp'].dt.strftime('%H:%M:%S')
        
        # Select and format columns for display
        display_df = recent[['time', 'mid_position', 'close_position', 'divergence']].copy()
        
        # Display the table
        print(tabulate(display_df, headers='keys', tablefmt='pretty', showindex=False))
    
    def save_to_csv(self, filename=None):
        """
        Save the comparison data to a CSV file.
        
        Args:
            filename: Optional filename, defaults to symbol_macd_comparison_YYYYMMDD.csv
        """
        if self.signal_comparison.empty:
            logger.info("No comparison data to save.")
            return
        
        if filename is None:
            today = datetime.now().strftime('%Y%m%d')
            filename = f"{self.symbol}_macd_comparison_{today}.csv"
        
        try:
            self.signal_comparison.to_csv(filename, index=False)
            logger.info(f"Comparison data saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving comparison data to CSV: {e}")
    
    def generate_report(self):
        """
        Generate a comprehensive report of the MACD signal comparison.
        """
        if self.signal_comparison.empty:
            logger.info("No comparison data for report generation.")
            return
        
        # Calculate statistics
        total_comparisons = len(self.signal_comparison)
        divergence_count = self.signal_comparison['divergence'].sum()
        divergence_pct = (divergence_count / total_comparisons) * 100
        
        # Count crossovers and crossunders
        mid_crossovers = self.signal_comparison['mid_crossover'].sum()
        close_crossovers = self.signal_comparison['close_crossover'].sum()
        mid_crossunders = self.signal_comparison['mid_crossunder'].sum()
        close_crossunders = self.signal_comparison['close_crossunder'].sum()
        
        # Find periods of divergence
        divergence_periods = []
        current_period = None
        
        for idx, row in self.signal_comparison.iterrows():
            if row['divergence']:
                if current_period is None:
                    current_period = {'start': row['timestamp'], 'mid': row['mid_position'], 'close': row['close_position']}
            else:
                if current_period is not None:
                    current_period['end'] = row['timestamp']
                    divergence_periods.append(current_period)
                    current_period = None
        
        # Add the last period if it's still open
        if current_period is not None:
            current_period['end'] = self.signal_comparison.iloc[-1]['timestamp']
            divergence_periods.append(current_period)
        
        # Generate the report
        report_filename = f"{self.symbol}_macd_comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_filename, 'w') as f:
            f.write(f"MACD Signal Comparison Report for {self.symbol}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Symbol: {self.symbol}\n")
            f.write(f"MACD Parameters: Fast={self.fast_window}, Slow={self.slow_window}, Signal={self.signal_window}\n")
            f.write(f"Comparison Period: {self.signal_comparison.iloc[0]['timestamp']} to {self.signal_comparison.iloc[-1]['timestamp']}\n\n")
            
            f.write("Summary Statistics:\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Comparisons: {total_comparisons}\n")
            f.write(f"Divergence Count: {divergence_count} ({divergence_pct:.2f}%)\n")
            f.write(f"Mid-Price Crossovers: {mid_crossovers} | Close-Price Crossovers: {close_crossovers}\n")
            f.write(f"Mid-Price Crossunders: {mid_crossunders} | Close-Price Crossunders: {close_crossunders}\n\n")
            
            f.write("Divergence Periods:\n")
            f.write("-" * 40 + "\n")
            
            if divergence_periods:
                for i, period in enumerate(divergence_periods):
                    duration = (period['end'] - period['start']).total_seconds() / 60  # in minutes
                    f.write(f"Period {i+1}: {period['start']} to {period['end']} ({duration:.1f} minutes)\n")
                    f.write(f"  Mid-Price Position: {period['mid']} | Close-Price Position: {period['close']}\n\n")
            else:
                f.write("No divergence periods detected.\n\n")
            
            f.write("Conclusion:\n")
            f.write("-" * 40 + "\n")
            
            if divergence_pct < 5:
                f.write("The mid-price and close-price MACD signals are highly consistent with minimal divergence.\n")
                f.write("Either approach should provide reliable trading signals.\n")
            elif divergence_pct < 15:
                f.write("The mid-price and close-price MACD signals show moderate divergence.\n")
                f.write("Consider using the close-price approach for more stability, especially for longer-term trading.\n")
            else:
                f.write("The mid-price and close-price MACD signals show significant divergence.\n")
                f.write("Close-price MACD signals may be more reliable for traditional MACD strategy implementation,\n")
                f.write("as they align better with historical backtesting that typically uses closing prices.\n")
            
            f.write("\nRecommendation:\n")
            if close_crossovers + close_crossunders < mid_crossovers + mid_crossunders:
                f.write("The close-price approach generates fewer signals, which may reduce false positives\n")
                f.write("and provide more reliable trading opportunities with less noise.\n")
            else:
                f.write("The mid-price approach may be more responsive to price changes,\n")
                f.write("potentially providing earlier signals at the cost of occasional false positives.\n")
        
        logger.info(f"Comparison report generated: {report_filename}")
        return report_filename
    
    def plot_comparison(self):
        """
        Plot the MACD comparison between mid-price and close-price.
        """
        if self.signal_comparison.empty or len(self.signal_comparison) < 10:
            logger.info("Not enough comparison data for plotting.")
            return
        
        # Create a figure with subplots
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        
        # Plot prices
        ax1.plot(self.signal_comparison['timestamp'], self.signal_comparison['mid_price'], label='Mid Price', color='blue')
        ax1.plot(self.signal_comparison['timestamp'], self.signal_comparison['close_price'], label='Close Price', color='green')
        ax1.set_title(f'{self.symbol} Price Comparison')
        ax1.set_ylabel('Price ($)')
        ax1.legend()
        ax1.grid(True)
        
        # Plot MACD lines
        ax2.plot(self.signal_comparison['timestamp'], self.signal_comparison['mid_macd'], label='Mid MACD', color='blue')
        ax2.plot(self.signal_comparison['timestamp'], self.signal_comparison['mid_signal'], label='Mid Signal', color='red')
        ax2.plot(self.signal_comparison['timestamp'], self.signal_comparison['close_macd'], label='Close MACD', color='green')
        ax2.plot(self.signal_comparison['timestamp'], self.signal_comparison['close_signal'], label='Close Signal', color='orange')
        ax2.set_title('MACD Comparison')
        ax2.set_ylabel('MACD Value')
        ax2.legend()
        ax2.grid(True)
        
        # Plot histograms
        ax3.bar(self.signal_comparison['timestamp'], self.signal_comparison['mid_histogram'], label='Mid Histogram', color='blue', alpha=0.5, width=0.01)
        ax3.bar(self.signal_comparison['timestamp'], self.signal_comparison['close_histogram'], label='Close Histogram', color='green', alpha=0.5, width=0.01)
        ax3.set_title('MACD Histogram Comparison')
        ax3.set_xlabel('Time')
        ax3.set_ylabel('Histogram Value')
        ax3.legend()
        ax3.grid(True)
        
        # Highlight divergence periods
        for idx, row in self.signal_comparison.iterrows():
            if row['divergence']:
                for ax in [ax1, ax2, ax3]:
                    ax.axvline(x=row['timestamp'], color='red', linestyle='--', alpha=0.3)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save the plot
        plot_filename = f"{self.symbol}_macd_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(plot_filename)
        logger.info(f"Comparison plot saved: {plot_filename}")
        
        # Show the plot if in interactive mode
        plt.close()
        
        return plot_filename
    
    def run(self):
        """Run the MACD signal comparison."""
        logger.info(f"Starting MACD signal comparison for {self.symbol}")
        logger.info(f"Duration: {self.duration_minutes} minutes")
        logger.info(f"Press Ctrl+C to stop comparison")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=self.duration_minutes)
        
        try:
            while datetime.now() < end_time:
                # Update the comparison
                self.update_comparison()
                
                # Display the current comparison
                self.display_comparison()
                
                # Wait for the next update
                logger.info(f"Waiting {self.interval_seconds} seconds until next update...")
                logger.info("\n" + "-" * 80 + "\n")
                time.sleep(self.interval_seconds)
            
            # Generate final report and plot
            logger.info("Comparison complete. Generating report and plot...")
            self.generate_report()
            self.plot_comparison()
            
            # Save the comparison data
            self.save_to_csv()
            
            logger.info("MACD signal comparison completed successfully")
            
        except KeyboardInterrupt:
            logger.info("MACD signal comparison stopped by user")
            
            # Generate report and plot if we have enough data
            if len(self.signal_comparison) > 10:
                logger.info("Generating report and plot...")
                self.generate_report()
                self.plot_comparison()
            
            # Save the comparison data
            self.save_to_csv()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="MACD Signal Comparison Tool")
    
    parser.add_argument(
        "--symbol", 
        type=str, 
        default="AAPL",
        help="Stock symbol to analyze (default: AAPL)"
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        default=5,
        help="Update interval in seconds (default: 5)"
    )
    
    parser.add_argument(
        "--duration", 
        type=int, 
        default=60,
        help="Duration in minutes (default: 60)"
    )
    
    parser.add_argument(
        "--fast-window", 
        type=int, 
        default=13,
        help="Fast EMA window for MACD (default: 13)"
    )
    
    parser.add_argument(
        "--slow-window", 
        type=int, 
        default=21,
        help="Slow EMA window for MACD (default: 21)"
    )
    
    parser.add_argument(
        "--signal-window", 
        type=int, 
        default=9,
        help="Signal line window for MACD (default: 9)"
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Create and run the MACD signal comparator
    comparator = MACDSignalComparator(
        symbol=args.symbol,
        interval_seconds=args.interval,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        signal_window=args.signal_window,
        duration_minutes=args.duration
    )
    
    # Run the comparator
    comparator.run()
