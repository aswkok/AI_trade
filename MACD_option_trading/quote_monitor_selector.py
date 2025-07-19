#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Quote Monitor Selector

This module allows switching between different data sources (Alpaca or Yahoo Finance)
for the MACD trading system. It provides a unified interface to both implementations.
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

# Determine which data source to use based on environment variable
DATA_SOURCE = os.getenv("DATA_SOURCE", "ALPACA").upper()

if DATA_SOURCE == "YAHOO":
    logger.info("Using Yahoo Finance as data source")
    try:
        from yahoo_quote_monitor import YahooQuoteMonitor as QuoteMonitor
        logger.info("Successfully imported Yahoo Finance quote monitor")
    except ImportError as e:
        logger.error(f"Failed to import Yahoo Finance quote monitor: {e}")
        logger.warning("Falling back to Alpaca data source")
        from enhanced_quote_monitor import EnhancedQuoteMonitor as QuoteMonitor
else:
    logger.info("Using Alpaca as data source")
    from enhanced_quote_monitor import EnhancedQuoteMonitor as QuoteMonitor

# Export the selected QuoteMonitor class
__all__ = ['QuoteMonitor']
