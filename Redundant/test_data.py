#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script to verify Alpaca historical data retrieval.
"""

import os
import logging
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables (force reload)
load_dotenv(override=True)

def test_historical_data():
    """Test Alpaca historical data retrieval."""
    # Get API credentials from environment variables
    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET")
    
    # Log first few characters of API key for verification
    if api_key:
        logger.info(f"API Key found, starts with: {api_key[:4]}...")
    else:
        logger.error("No API Key found in environment variables")
        return False
    
    # Get API URLs from environment variables
    data_url = os.getenv("PAPER_DATA_URL")
    logger.info(f"Data URL: {data_url}")
    
    try:
        # Initialize the data client
        logger.info("Initializing Data Client...")
        data_client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=api_secret
        )
        
        # Test symbols
        symbols = ["AAPL", "MSFT", "AMZN"]
        
        # Try different methods to get data
        
        # 1. Try getting latest quotes
        logger.info("Testing latest quotes...")
        try:
            quote_request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = data_client.get_stock_latest_quote(quote_request)
            if quotes:
                logger.info(f"Successfully retrieved latest quotes for {len(quotes)} symbols")
                for symbol, quote in quotes.items():
                    logger.info(f"{symbol}: Ask ${quote.ask_price}, Bid ${quote.bid_price}")
        except Exception as e:
            logger.error(f"Error getting latest quotes: {e}")
        
        # 2. Try getting historical data with different timeframes
        timeframes = [TimeFrame.Day, TimeFrame.Hour, TimeFrame.Minute]
        
        for timeframe in timeframes:
            logger.info(f"Testing {timeframe} data...")
            
            # Calculate start and end dates - try a shorter period
            end = datetime.now()
            start = end - timedelta(days=7)  # Just 7 days of data
            
            try:
                request_params = StockBarsRequest(
                    symbol_or_symbols=symbols,
                    timeframe=timeframe,
                    start=start,
                    end=end
                )
                
                logger.info(f"Requesting data from {start.date()} to {end.date()}")
                bars = data_client.get_stock_bars(request_params)
                
                if bars:
                    for symbol in symbols:
                        if symbol in bars and len(bars[symbol]) > 0:
                            logger.info(f"Retrieved {len(bars[symbol])} {timeframe} bars for {symbol}")
                        else:
                            logger.warning(f"No {timeframe} data found for {symbol}")
                else:
                    logger.warning(f"No {timeframe} data returned for any symbols")
            except Exception as e:
                logger.error(f"Error retrieving {timeframe} data: {e}")
        
        logger.info("Historical data test completed")
        return True
        
    except Exception as e:
        logger.error(f"Error in test: {e}")
        return False

if __name__ == "__main__":
    test_historical_data()
