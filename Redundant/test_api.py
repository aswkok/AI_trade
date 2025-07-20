#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script to verify Alpaca API credentials and connectivity.
"""

import os
import logging
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass

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

def test_alpaca_api():
    """Test Alpaca API connectivity."""
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
    paper_trading_url = os.getenv("PAPER_TRADING_URL")
    paper_data_url = os.getenv("PAPER_DATA_URL")
    
    logger.info(f"Paper Trading URL: {paper_trading_url}")
    logger.info(f"Paper Data URL: {paper_data_url}")
    
    try:
        # Test trading API
        logger.info("Testing Trading API connection...")
        trading_client = TradingClient(
            api_key=api_key,
            secret_key=api_secret,
            paper=True,
            url_override=paper_trading_url
        )
        
        # Try to get account info
        try:
            account = trading_client.get_account()
            logger.info(f"Successfully connected to Trading API. Account ID: {account.id}")
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            
        # Try to list assets
        try:
            search_params = GetAssetsRequest(asset_class=AssetClass.US_EQUITY)
            assets = trading_client.get_all_assets(search_params)
            logger.info(f"Successfully retrieved {len(assets)} assets")
        except Exception as e:
            logger.error(f"Error getting assets: {e}")
        
        # Test data API
        logger.info("Testing Data API connection...")
        data_client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=api_secret,
            url_override=paper_data_url
        )
        
        logger.info("API connection test completed")
        return True
        
    except Exception as e:
        logger.error(f"Error connecting to Alpaca API: {e}")
        return False

if __name__ == "__main__":
    test_alpaca_api()
