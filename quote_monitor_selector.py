#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Quote Monitor Selector

This module allows switching between different data sources (Alpaca, Yahoo Finance with mid-prices,
or Yahoo Finance with close prices) for the MACD trading system. It provides a unified interface
to all implementations.
"""

import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Determine which data source to use based on environment variables
DATA_SOURCE = os.getenv("DATA_SOURCE", "ALPACA").upper()
YAHOO_PRICE_TYPE = os.getenv("YAHOO_PRICE_TYPE", "MID").upper()  # MID or CLOSE

if DATA_SOURCE == "YAHOO":
    if YAHOO_PRICE_TYPE == "CLOSE":
        logger.info("Using Yahoo Finance with CLOSE prices as data source")
        try:
            from yahoo_close_monitor import YahooCloseQuoteMonitor as QuoteMonitor
            logger.info("Successfully imported Yahoo Finance close price monitor")
        except ImportError as e:
            logger.error(f"Failed to import Yahoo Finance close price monitor: {e}")
            logger.warning("Falling back to Yahoo Finance with mid prices")
            try:
                from yahoo_quote_monitor import YahooQuoteMonitor as QuoteMonitor
                logger.info("Successfully imported Yahoo Finance quote monitor with mid prices")
            except ImportError as e:
                logger.error(f"Failed to import Yahoo Finance quote monitor: {e}")
                logger.warning("Falling back to Alpaca data source")
                from enhanced_quote_monitor import EnhancedQuoteMonitor as QuoteMonitor
    else:  # Default to MID prices
        logger.info("Using Yahoo Finance with MID prices as data source")
        try:
            from yahoo_quote_monitor import YahooQuoteMonitor as QuoteMonitor
            logger.info("Successfully imported Yahoo Finance quote monitor with mid prices")
        except ImportError as e:
            logger.error(f"Failed to import Yahoo Finance quote monitor: {e}")
            logger.warning("Falling back to Alpaca data source")
            from enhanced_quote_monitor import EnhancedQuoteMonitor as QuoteMonitor
else:
    logger.info("Using Alpaca as data source")
    from enhanced_quote_monitor import EnhancedQuoteMonitor as QuoteMonitor

# Export the selected QuoteMonitor class
__all__ = ['QuoteMonitor']
