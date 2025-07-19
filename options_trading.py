#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Options trading module for the Alpaca-based quantitative trading system.
This script handles options data retrieval, analysis, and trading operations.
"""

import os
import logging
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("options_trading.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Trading mode configuration
# Set to "PAPER" for paper trading (practice with fake money)
# Set to "LIVE" for live trading (real money)
TRADING_MODE = "PAPER"  # Change this to "LIVE" when ready for live trading

class OptionsTrader:
    """Options trading class that interfaces with Alpaca API."""
    
    def __init__(self):
        """Initialize the options trader with API credentials and clients."""
        # API credentials
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_API_SECRET")
        self.trading_mode = TRADING_MODE.upper()
        
        # Set the trading and data URLs based on trading mode
        if self.trading_mode == "PAPER":
            self.trading_url = os.getenv("PAPER_TRADING_URL")
            self.data_url = os.getenv("PAPER_DATA_URL")
        elif self.trading_mode == "LIVE":
            self.trading_url = os.getenv("LIVE_TRADING_URL")
            self.data_url = os.getenv("LIVE_DATA_URL")
        else:
            # Default to paper trading if invalid mode
            logger.warning(f"Invalid trading mode: {self.trading_mode}. Defaulting to PAPER trading.")
            self.trading_mode = "PAPER"
            self.trading_url = os.getenv("PAPER_TRADING_URL")
            self.data_url = os.getenv("PAPER_DATA_URL")
        
        if not all([self.api_key, self.api_secret, self.trading_url, self.data_url]):
            raise ValueError("Missing Alpaca API credentials or URLs. Please check your .env file.")
        
        # Initialize clients
        logger.info(f"Initializing Alpaca clients with paper={self.is_paper_trading()}")
        try:
            # Initialize the trading client with the appropriate base URL
            self.trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                paper=self.is_paper_trading(),
                url_override=self.trading_url
            )
            
            # Initialize the data client with the appropriate base URL
            self.data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                url_override=self.data_url
            )
            
            logger.info("Alpaca clients initialized successfully")
            logger.info(f"Trading URL: {self.trading_url}")
            logger.info(f"Data URL: {self.data_url}")
        except Exception as e:
            logger.error(f"Error initializing Alpaca clients: {e}")
            raise
        
        logger.info(f"Trading mode: {self.trading_mode}")
        
        # Trading parameters
        # Get values from env or use defaults, and handle any comments in the values
        risk_per_trade_str = os.getenv("RISK_PER_TRADE", "0.02")
        max_positions_str = os.getenv("MAX_POSITIONS", "5")
        
        # Strip comments and whitespace
        if isinstance(risk_per_trade_str, str) and '#' in risk_per_trade_str:
            risk_per_trade_str = risk_per_trade_str.split('#')[0].strip()
        if isinstance(max_positions_str, str) and '#' in max_positions_str:
            max_positions_str = max_positions_str.split('#')[0].strip()
            
        # Convert to appropriate types
        self.risk_per_trade = float(risk_per_trade_str)
        self.max_positions = int(max_positions_str)
        
        logger.info(f"Options trader initialized with paper trading: {self.is_paper_trading()}")
    
    def is_paper_trading(self):
        """Determine if we're using paper trading based on the trading mode."""
        return self.trading_mode == "PAPER"
    
    def get_account_info(self):
        """Retrieve and display account information."""
        account = self.trading_client.get_account()
        logger.info(f"Account ID: {account.id}")
        logger.info(f"Cash: ${account.cash}")
        logger.info(f"Portfolio Value: ${account.portfolio_value}")
        logger.info(f"Buying Power: ${account.buying_power}")
        return account
    
    def get_option_chain(self, symbol):
        """
        Get the options chain for a given symbol.
        Note: This is a placeholder as Alpaca's options API integration is still evolving.
        In a production environment, you might need to use a different data provider or
        Alpaca's latest options API endpoints.
        """
        logger.info(f"Fetching options chain for {symbol}")
        # This is where you would integrate with Alpaca's options API
        # For now, we'll return a placeholder
        logger.warning("Options chain retrieval is a placeholder. Implement with actual Alpaca options API.")
        return None
    
    def calculate_implied_volatility(self, option_data):
        """
        Calculate implied volatility for options.
        This is a placeholder for actual IV calculation logic.
        """
        logger.info("Calculating implied volatility")
        # Placeholder for actual IV calculation
        return None
    
    def run_covered_call_strategy(self, symbol, expiration_days=30, delta_target=0.3):
        """
        Implement a covered call options strategy.
        
        1. Check if we own the underlying stock
        2. If yes, sell a call option with target delta and expiration
        3. If no, consider buying the stock first
        
        Args:
            symbol: The stock symbol
            expiration_days: Target days to expiration
            delta_target: Target delta for the call option (0.3 = 30 delta)
        """
        logger.info(f"Running covered call strategy for {symbol}")
        
        # Check if we own the underlying stock
        positions = self.trading_client.get_all_positions()
        stock_position = next((p for p in positions if p.symbol == symbol), None)
        
        if stock_position is None or int(stock_position.qty) <= 0:
            logger.info(f"No position in {symbol} for covered call strategy")
            return
        
        # Get options chain
        options_chain = self.get_option_chain(symbol)
        if not options_chain:
            logger.warning(f"Could not retrieve options chain for {symbol}")
            return
        
        # Find appropriate call option (placeholder logic)
        logger.info(f"Looking for call option with ~{delta_target} delta, {expiration_days} DTE")
        
        # Place the covered call order (placeholder)
        logger.info(f"Would sell covered call for {symbol} here")
        
        # In a real implementation, you would:
        # 1. Filter options chain for calls with target expiration
        # 2. Find the strike with delta closest to target
        # 3. Verify the option has sufficient liquidity
        # 4. Calculate position size based on stock holdings
        # 5. Place the sell-to-open order for the call
    
    def run_cash_secured_put_strategy(self, symbol, expiration_days=30, delta_target=0.3):
        """
        Implement a cash-secured put options strategy.
        
        1. Check if we have sufficient cash
        2. Sell a put option with target delta and expiration
        
        Args:
            symbol: The stock symbol
            expiration_days: Target days to expiration
            delta_target: Target delta for the put option (0.3 = 30 delta)
        """
        logger.info(f"Running cash-secured put strategy for {symbol}")
        
        # Check account cash
        account = self.trading_client.get_account()
        available_cash = float(account.cash)
        
        # Get current stock price
        bars_request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=5),
            end=datetime.now()
        )
        bars = self.data_client.get_stock_bars(bars_request)
        
        if symbol not in bars or not bars[symbol]:
            logger.warning(f"Could not retrieve price data for {symbol}")
            return
        
        current_price = bars[symbol][-1].close
        
        # Check if we have enough cash for at least 100 shares (1 contract)
        if available_cash < current_price * 100:
            logger.warning(f"Insufficient cash for cash-secured put on {symbol}")
            return
        
        # Get options chain
        options_chain = self.get_option_chain(symbol)
        if not options_chain:
            logger.warning(f"Could not retrieve options chain for {symbol}")
            return
        
        # Find appropriate put option (placeholder logic)
        logger.info(f"Looking for put option with ~{delta_target} delta, {expiration_days} DTE")
        
        # Place the cash-secured put order (placeholder)
        logger.info(f"Would sell cash-secured put for {symbol} here")
        
        # In a real implementation, you would:
        # 1. Filter options chain for puts with target expiration
        # 2. Find the strike with delta closest to target
        # 3. Verify the option has sufficient liquidity
        # 4. Calculate how many puts you can afford to sell
        # 5. Place the sell-to-open order for the put
    
    def run_iron_condor_strategy(self, symbol, expiration_days=30, wing_width=0.1):
        """
        Implement an iron condor options strategy.
        
        Args:
            symbol: The stock symbol
            expiration_days: Target days to expiration
            wing_width: Width between short and long strikes as a percentage
        """
        logger.info(f"Running iron condor strategy for {symbol}")
        
        # Get options chain
        options_chain = self.get_option_chain(symbol)
        if not options_chain:
            logger.warning(f"Could not retrieve options chain for {symbol}")
            return
        
        # Get current stock price and implied volatility
        # (placeholder - would use actual data in real implementation)
        current_price = 100  # Placeholder
        
        # Calculate strike prices (placeholder logic)
        # In a real implementation, you would select strikes based on delta or standard deviations
        short_put_strike = current_price * 0.9
        long_put_strike = short_put_strike * (1 - wing_width)
        short_call_strike = current_price * 1.1
        long_call_strike = short_call_strike * (1 + wing_width)
        
        logger.info(f"Iron condor strikes - Short put: {short_put_strike}, Long put: {long_put_strike}, "
                   f"Short call: {short_call_strike}, Long call: {long_call_strike}")
        
        # Place the iron condor order (placeholder)
        logger.info(f"Would place iron condor for {symbol} here")
        
        # In a real implementation, you would:
        # 1. Filter options chain for options with target expiration
        # 2. Find the appropriate strikes based on your strategy
        # 3. Verify the options have sufficient liquidity
        # 4. Calculate position size based on account risk parameters
        # 5. Place the multi-leg order for the iron condor
    
    def run_options_strategy(self, symbol, strategy="covered_call"):
        """
        Run the specified options strategy for a symbol.
        
        Args:
            symbol: The stock symbol
            strategy: The options strategy to run
        """
        logger.info(f"Running {strategy} strategy for {symbol}")
        
        if strategy == "covered_call":
            self.run_covered_call_strategy(symbol)
        elif strategy == "cash_secured_put":
            self.run_cash_secured_put_strategy(symbol)
        elif strategy == "iron_condor":
            self.run_iron_condor_strategy(symbol)
        else:
            logger.error(f"Unknown options strategy: {strategy}")
    
    def run(self, symbols=None, strategy="covered_call"):
        """Run the options trader on the specified symbols with the given strategy."""
        if symbols is None:
            symbols = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META']
        
        logger.info(f"Starting options trader for symbols: {symbols} with strategy: {strategy}")
        
        # Display account information
        self.get_account_info()
        
        # Run strategy for each symbol
        for symbol in symbols:
            logger.info(f"Running {strategy} for {symbol}")
            self.run_options_strategy(symbol, strategy)
        
        logger.info("Options trading execution completed")


if __name__ == "__main__":
    try:
        # Initialize and run the options trader
        options_trader = OptionsTrader()
        
        # Define symbols to trade
        symbols = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META']
        
        # Choose strategy: "covered_call", "cash_secured_put", or "iron_condor"
        strategy = "covered_call"
        
        # Run the system
        options_trader.run(symbols, strategy)
        
    except Exception as e:
        logger.error(f"Error in options trading execution: {e}", exc_info=True)
