#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Quote Monitor Service Client

This module provides a client interface to connect to the Quote Monitor Service.
It allows trading systems to retrieve quote data and MACD signals from an
independently running quote monitor service.
"""

import os
import time
import logging
import socket
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class QuoteMonitorClient:
    """
    Client interface for connecting to the Quote Monitor Service.
    
    This class provides methods to retrieve quote data and MACD signals
    from an independently running quote monitor service.
    """
    
    def __init__(self, symbol, service_host='localhost', service_port=None, data_dir="quote_data"):
        """
        Initialize the quote monitor client.
        
        Args:
            symbol: Symbol to monitor
            service_host: Host where the quote monitor service is running
            service_port: Port for the service (if None, use direct file access)
            data_dir: Directory where quote data is stored
        """
        # Load environment variables
        load_dotenv()
        
        # Store configuration
        self.symbol = symbol.upper()
        self.service_host = service_host
        self.service_port = service_port
        self.data_dir = data_dir
        
        # Data storage
        self.quotes_df = pd.DataFrame()
        self.last_update_time = None
        self.connected = False
        self.status = "Initializing"
        
        # MACD state
        self.last_macd_signal = None
        
        # If we're using direct file access, make sure the directory exists
        if not service_port:
            if not os.path.exists(data_dir):
                logger.warning(f"Data directory {data_dir} does not exist, creating it")
                os.makedirs(data_dir, exist_ok=True)
        
        # Try to connect to the service
        self._connect()
        
        logger.info(f"Quote Monitor Client initialized for {symbol}")
    
    def _connect(self):
        """
        Connect to the quote monitor service.
        
        If service_port is None, use direct file access instead of socket connection.
        """
        if self.service_port:
            try:
                # In a real implementation, this would establish a socket connection
                # For this example, we'll simulate a successful connection
                logger.info(f"Connecting to quote monitor service at {self.service_host}:{self.service_port}")
                self.connected = True
                self.status = "Connected to service"
            except Exception as e:
                logger.error(f"Error connecting to quote monitor service: {e}")
                self.connected = False
                self.status = f"Connection error: {e}"
        else:
            # Using direct file access
            logger.info(f"Using direct file access mode for quote data in {self.data_dir}")
            self.connected = True
            self.status = "Using direct file access"
            
            # Try to load the latest data file
            self._load_latest_data_file()
    
    def _load_latest_data_file(self):
        """
        Load the latest quote data file for the symbol.
        
        This is used when operating in direct file access mode.
        """
        try:
            # Find all data files for this symbol
            files = []
            for filename in os.listdir(self.data_dir):
                if filename.startswith(f"{self.symbol}_quotes_") and filename.endswith(".csv"):
                    files.append(os.path.join(self.data_dir, filename))
            
            if not files:
                logger.warning(f"No quote data files found for {self.symbol}")
                return False
            
            # Sort by modification time (newest first)
            files.sort(key=os.path.getmtime, reverse=True)
            
            # Load the newest file
            latest_file = files[0]
            self.quotes_df = pd.read_csv(latest_file)
            
            logger.info(f"Loaded {len(self.quotes_df)} quotes from {latest_file}")
            self.last_update_time = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading quote data file: {e}")
            return False
    
    def update(self):
        """
        Update the quote data from the service.
        
        Returns:
            bool: True if new data was retrieved, False otherwise
        """
        if not self.connected:
            logger.warning("Not connected to quote monitor service")
            self._connect()  # Try to reconnect
            return False
        
        try:
            if self.service_port:
                # In a real implementation, this would fetch data from the socket connection
                # For this example, we'll simulate fetching data
                
                # Simulate some delay
                time.sleep(0.1)
                
                # For this simulation, we'll just say we got new data
                self.last_update_time = datetime.now()
                self.status = f"Updated at {self.last_update_time.strftime('%H:%M:%S')}"
                
                return True
                
            else:
                # Using direct file access
                return self._load_latest_data_file()
                
        except Exception as e:
            logger.error(f"Error updating quote data: {e}")
            self.status = f"Update error: {e}"
            return False
    
    def get_current_price(self):
        """
        Get the current price of the symbol.
        
        Returns:
            float: Current price or None if not available
        """
        if self.quotes_df.empty:
            return None
        
        # Get the latest row
        latest = self.quotes_df.iloc[-1]
        
        # Calculate mid price from bid and ask
        if 'bid' in latest and 'ask' in latest:
            return (latest['bid'] + latest['ask']) / 2
        elif 'mid' in latest:
            return latest['mid']
        else:
            return None
    
    def get_macd_signal(self):
        """
        Get the current MACD signal.
        
        Returns:
            dict: MACD signal information or None if not available
        """
        if self.quotes_df.empty:
            return None
        
        # Check if we have MACD columns in the dataframe
        required_columns = ['MACD', 'signal', 'histogram', 'MACD_position']
        if not all(col in self.quotes_df.columns for col in required_columns):
            logger.warning("MACD data not available in quotes dataframe")
            return None
        
        # Get the latest row
        latest = self.quotes_df.iloc[-1]
        
        # Check for crossovers in the last few rows
        crossover = False
        crossunder = False
        
        if len(self.quotes_df) >= 2:
            prev = self.quotes_df.iloc[-2]
            
            # Check for crossover (MACD crosses above signal)
            if latest['MACD'] > latest['signal'] and prev['MACD'] <= prev['signal']:
                crossover = True
            
            # Check for crossunder (MACD crosses below signal)
            if latest['MACD'] < latest['signal'] and prev['MACD'] >= prev['signal']:
                crossunder = True
        
        # Determine the signal
        signal_value = 0.0  # Default to hold
        
        if crossover:
            signal_value = 1.0  # Buy signal
        elif crossunder:
            signal_value = -1.0  # Sell signal
        
        # Create the signal dictionary
        macd_signal = {
            'signal': signal_value,
            'position': latest['MACD_position'],
            'macd_value': latest['MACD'],
            'signal_value': latest['signal'],
            'histogram': latest['histogram'],
            'crossover': crossover,
            'crossunder': crossunder,
            'timestamp': latest.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        }
        
        # Store the signal
        self.last_macd_signal = macd_signal
        
        return macd_signal
    
    def is_data_ready(self):
        """
        Check if the quote data is ready for trading.
        
        Returns:
            bool: True if data is ready, False otherwise
        """
        if self.quotes_df.empty:
            return False
        
        # Check if we have MACD columns in the dataframe
        required_columns = ['MACD', 'signal', 'histogram', 'MACD_position']
        if not all(col in self.quotes_df.columns for col in required_columns):
            return False
        
        # Check if we have enough data
        return len(self.quotes_df) >= 30  # Arbitrary minimum
    
    def get_status(self):
        """
        Get the current status of the client.
        
        Returns:
            str: Status message
        """
        if self.quotes_df.empty:
            return f"{self.status} - No data available"
        
        return f"{self.status} - {len(self.quotes_df)} quotes available"
    
    def close(self):
        """Close the connection to the quote monitor service."""
        if self.service_port and self.connected:
            # In a real implementation, this would close the socket connection
            logger.info("Closing connection to quote monitor service")
        
        self.connected = False
        self.status = "Disconnected"


if __name__ == "__main__":
    # Simple test
    import argparse
    
    parser = argparse.ArgumentParser(description="Quote Monitor Service Client")
    parser.add_argument("--symbol", type=str, default="SPY", help="Symbol to monitor")
    parser.add_argument("--data-dir", type=str, default="quote_data", help="Data directory")
    args = parser.parse_args()
    
    # Create the client
    client = QuoteMonitorClient(args.symbol, data_dir=args.data_dir)
    
    # Update and show status
    if client.update():
        print(f"Current price: ${client.get_current_price():.2f}")
        
        macd_signal = client.get_macd_signal()
        if macd_signal:
            print(f"MACD signal: {macd_signal['signal']}")
            print(f"MACD position: {macd_signal['position']}")
            print(f"MACD value: {macd_signal['macd_value']:.4f}")
            print(f"Signal value: {macd_signal['signal_value']:.4f}")
            print(f"Histogram: {macd_signal['histogram']:.4f}")
        else:
            print("MACD data not available")
    else:
        print("Failed to update quote data")
    
    print(f"Status: {client.get_status()}")
    
    # Close the client
    client.close()
