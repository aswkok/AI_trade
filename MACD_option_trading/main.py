#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main entry point for the Alpaca-based quantitative trading system.
This script handles initialization, strategy execution, and trading operations.
"""

import os
import logging
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest, GetAssetsRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, AssetClass, AssetStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.live import StockDataStream
from alpaca.data.enums import Adjustment, DataFeed

# Import Yahoo Finance for historical data
import yfinance as yf

# Import strategies
from strategies import MACDStrategy, StrategyFactory, DEFAULT_STRATEGY, DEFAULT_STRATEGY_CONFIGS, DEFAULT_SYMBOLS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables (force reload)
load_dotenv(override=True)

# Trading mode configuration
# Set to "PAPER" for paper trading (practice with fake money)
# Set to "LIVE" for live trading (real money)
TRADING_MODE = "PAPER"  # Change this to "LIVE" when ready for live trading

class AlpacaTradingSystem:
    """Main trading system class that interfaces with Alpaca API."""
    
    def __init__(self):
        """Initialize the trading system with API credentials and clients."""
        # API credentials
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_API_SECRET")
        self.trading_mode = TRADING_MODE.upper()
        
        # Debug log API key (first 4 chars only for security)
        if self.api_key:
            logger.info(f"API Key found, starts with: {self.api_key[:4]}...")
        else:
            logger.warning("No API Key found in environment variables")
        
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
        extended_hours_str = os.getenv("EXTENDED_HOURS", "True")
        overnight_trading_str = os.getenv("OVERNIGHT_TRADING", "True")
        
        # Strip comments and whitespace
        if isinstance(risk_per_trade_str, str) and '#' in risk_per_trade_str:
            risk_per_trade_str = risk_per_trade_str.split('#')[0].strip()
        if isinstance(max_positions_str, str) and '#' in max_positions_str:
            max_positions_str = max_positions_str.split('#')[0].strip()
        if isinstance(extended_hours_str, str) and '#' in extended_hours_str:
            extended_hours_str = extended_hours_str.split('#')[0].strip()
        if isinstance(overnight_trading_str, str) and '#' in overnight_trading_str:
            overnight_trading_str = overnight_trading_str.split('#')[0].strip()
            
        # Convert to appropriate types
        self.risk_per_trade = float(risk_per_trade_str)
        self.max_positions = int(max_positions_str)
        self.extended_hours = extended_hours_str.lower() == "true"
        self.overnight_trading = overnight_trading_str.lower() == "true"
        
        logger.info(f"Extended hours trading: {self.extended_hours}")
        logger.info(f"Overnight trading: {self.overnight_trading}")
        
        logger.info(f"Trading system initialized with paper trading: {self.is_paper_trading()}")
    
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
        logger.info(f"Daytrade Count: {account.daytrade_count}")
        return account
    
    def get_positions(self):
        """Get current positions."""
        positions = self.trading_client.get_all_positions()
        logger.info(f"Current positions: {len(positions)}")
        for position in positions:
            logger.info(f"Symbol: {position.symbol}, Qty: {position.qty}, Market Value: ${position.market_value}")
        return positions
    
    def get_historical_data(self, symbol, timeframe=TimeFrame.Day, limit=250):
        """Get historical price data for a symbol using Alpaca API with caching."""
        try:
            # Calculate start and end dates
            end = datetime.now()
            start = end - timedelta(days=limit if timeframe == TimeFrame.Day else 30)  # Limit days for higher frequency data
            
            # Create cache directory if it doesn't exist
            cache_dir = os.path.join(os.getcwd(), 'data_cache')
            os.makedirs(cache_dir, exist_ok=True)
            
            # Define cache file path with timeframe included
            timeframe_str = str(timeframe).split('.')[-1].lower()
            cache_file = os.path.join(cache_dir, f"{symbol}_{timeframe_str}_{start.date()}_{end.date()}.csv")
            
            # Check if we have cached data
            if os.path.exists(cache_file):
                # Load from cache
                logger.info(f"Loading cached data for {symbol} ({timeframe_str}) from {cache_file}")
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                
                # Ensure numeric columns are properly typed
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                        
                logger.info(f"Retrieved {len(df)} bars for {symbol} from cache")
                return df
            
            logger.info(f"Requesting data for {symbol} from {start.date()} to {end.date()} using Alpaca API")
            
            # Determine the appropriate timeframe multiplier
            if timeframe == TimeFrame.Minute:
                # For minute data, limit to last 7 days to avoid huge datasets
                start = max(start, end - timedelta(days=7))
            
            # Try to get data from Alpaca
            try:
                # First attempt with Alpaca's data API
                bars_request = StockBarsRequest(
                    symbol_or_symbols=[symbol],
                    timeframe=timeframe,
                    start=start,
                    end=end,
                    adjustment=Adjustment.ALL,
                    feed=DataFeed.SIP
                )
                
                logger.info(f"Requesting bars for {symbol} with timeframe {timeframe}")
                bars = self.data_client.get_stock_bars(bars_request)
                
                # Convert to DataFrame
                if bars and symbol in bars:
                    # Extract the bars for this symbol
                    symbol_bars = bars[symbol]
                    
                    if symbol_bars:
                        # Convert to DataFrame
                        data = []
                        for bar in symbol_bars:
                            data.append({
                                'timestamp': bar.timestamp,
                                'open': bar.open,
                                'high': bar.high,
                                'low': bar.low,
                                'close': bar.close,
                                'volume': bar.volume
                            })
                        
                        df = pd.DataFrame(data)
                        df.set_index('timestamp', inplace=True)
                        
                        # Cache the data
                        df.to_csv(cache_file)
                        logger.info(f"Retrieved {len(df)} bars for {symbol} from Alpaca and cached to {cache_file}")
                        return df
                    else:
                        logger.warning(f"No bars returned for {symbol} from Alpaca")
                else:
                    logger.warning(f"No data found for {symbol} from Alpaca API")
            
            except Exception as e:
                logger.error(f"Error retrieving data from Alpaca: {e}")
                
                # Fall back to Yahoo Finance if Alpaca fails and we have it imported
                if 'yf' in globals():
                    logger.info(f"Falling back to Yahoo Finance for {symbol}")
                    try:
                        # Map Alpaca timeframe to Yahoo Finance interval
                        interval = '1d'  # default to daily
                        if timeframe == TimeFrame.Minute:
                            interval = '1m'
                        elif timeframe == TimeFrame.Hour:
                            interval = '1h'
                        
                        df = yf.download(
                            symbol,
                            start=start,
                            end=end,
                            interval=interval,
                            progress=False
                        )
                        
                        if not df.empty:
                            # Rename columns to match Alpaca format
                            df.rename(columns={
                                'Open': 'open',
                                'High': 'high',
                                'Low': 'low',
                                'Close': 'close',
                                'Adj Close': 'adj_close',
                                'Volume': 'volume'
                            }, inplace=True)
                            
                            # Cache the data
                            df.to_csv(cache_file)
                            logger.info(f"Retrieved {len(df)} bars for {symbol} from Yahoo Finance fallback")
                            return df
                    except Exception as yf_error:
                        logger.error(f"Yahoo Finance fallback also failed: {yf_error}")
            
            # If we get here, all methods failed
            # Check for any existing cache files for this symbol
            existing_cache_files = [f for f in os.listdir(cache_dir) if f.startswith(f"{symbol}_") and f.endswith(".csv")]
            if existing_cache_files:
                # Use the most recent cache file
                most_recent = max(existing_cache_files, key=lambda f: os.path.getmtime(os.path.join(cache_dir, f)))
                cache_path = os.path.join(cache_dir, most_recent)
                logger.info(f"Using existing cache file for {symbol}: {most_recent}")
                df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                return df
                
            # Try to use a sample data file for testing if available
            sample_file = os.path.join(os.getcwd(), 'sample_data', f"{symbol}_sample.csv")
            if os.path.exists(sample_file):
                logger.info(f"Using sample data for {symbol} from {sample_file}")
                df = pd.read_csv(sample_file, index_col=0, parse_dates=True)
                return df
                
            logger.error(f"Failed to retrieve data for {symbol} from all sources")
            return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Unexpected error retrieving data for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_realtime_data(self, symbol):
        """
        Get real-time market data for a symbol using Alpaca.
        Returns the latest quote and trade information.
        """
        try:
            # Get the latest quote
            quote_request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            quotes = self.data_client.get_stock_latest_quote(quote_request)
            
            # Get the latest trade
            trade_request = StockLatestTradeRequest(symbol_or_symbols=[symbol])
            trades = self.data_client.get_stock_latest_trade(trade_request)
            
            if symbol in quotes and symbol in trades:
                quote = quotes[symbol]
                trade = trades[symbol]
                
                logger.info(f"Real-time data for {symbol}:")
                logger.info(f"  Quote: Ask ${quote.ask_price}, Bid ${quote.bid_price}")
                logger.info(f"  Trade: Price ${trade.price}, Size {trade.size}")
                
                # Create a DataFrame with the latest data
                latest_data = pd.DataFrame({
                    'timestamp': [datetime.now()],
                    'open': [float(trade.price)],
                    'high': [float(quote.ask_price)],
                    'low': [float(quote.bid_price)],
                    'close': [float(trade.price)],
                    'volume': [float(trade.size)]
                })
                latest_data.set_index('timestamp', inplace=True)
                
                return latest_data
            else:
                logger.warning(f"No real-time data available for {symbol}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error retrieving real-time data for {symbol}: {e}")
            return pd.DataFrame()
    
    def setup_realtime_stream(self, symbols):
        """
        Set up a real-time data stream for the given symbols.
        This method uses WebSockets to receive streaming market data.
        """
        try:
            # Initialize the WebSocket connection
            self.stock_stream = StockDataStream(
                api_key=self.api_key,
                secret_key=self.api_secret
            )
            
            # Define callback for trades
            async def trade_callback(trade):
                symbol = trade.symbol
                price = trade.price
                size = trade.size
                timestamp = trade.timestamp
                logger.info(f"Trade: {symbol} - ${price} x {size} at {timestamp}")
                
                # Process the trade data here - you could trigger strategy evaluation
                # self.process_realtime_trade(symbol, price, size, timestamp)
            
            # Define callback for quotes
            async def quote_callback(quote):
                symbol = quote.symbol
                bid_price = quote.bid_price
                ask_price = quote.ask_price
                logger.info(f"Quote: {symbol} - Bid: ${bid_price}, Ask: ${ask_price}")
            
            # Subscribe to trade and quote updates
            self.stock_stream.subscribe_trades(trade_callback, symbols)
            self.stock_stream.subscribe_quotes(quote_callback, symbols)
            
            logger.info(f"Set up real-time data stream for symbols: {symbols}")
            
            # Return the stream object so it can be started elsewhere
            return self.stock_stream
            
        except Exception as e:
            logger.error(f"Error setting up real-time data stream: {e}")
            return None
            
    def run_continuous_strategy(self, symbols, strategy_name="macd", interval=1, **strategy_params):
        """
        Run a strategy continuously at specified intervals with support for extended hours and overnight trading.
        
        Args:
            symbols: List of symbols to trade
            strategy_name: Name of the strategy to use
            interval: Interval in minutes between strategy runs
            **strategy_params: Additional parameters for the strategy
        """
        import time
        import signal
        import sys
        from datetime import datetime, time as dt_time
        
        # Define market hours (Eastern Time)
        market_open = dt_time(9, 30)  # 9:30 AM ET
        market_close = dt_time(16, 0)  # 4:00 PM ET
        pre_market_open = dt_time(4, 0)  # 4:00 AM ET
        after_hours_close = dt_time(20, 0)  # 8:00 PM ET
        
        # Initialize strategy instances for each symbol
        strategy_instances = {}
        historical_data = {}
        
        # Setup signal handler for graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutting down continuous strategy execution...")
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        
        # Initialize with historical data
        for symbol in symbols:
            # Get historical data for initial strategy setup - increased limit for more accurate MACD
            data = self.get_historical_data(symbol, limit=250)  # Increased from 100 to 250 for better MACD accuracy
            if data.empty:
                logger.error(f"No historical data available for {symbol}, skipping")
                continue
                
            logger.info(f"Retrieved {len(data)} historical bars for {symbol} for MACD calculation")
                
            # Ensure data types are numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')
            
            # Create strategy instance
            try:
                strategy = StrategyFactory.get_strategy(strategy_name, **strategy_params)
                strategy_instances[symbol] = strategy
                historical_data[symbol] = data
                logger.info(f"Initialized {strategy.name} for {symbol} with {len(data)} bars of historical data")
                
                # Generate initial signals to determine current MACD position
                initial_signals = strategy.generate_signals(data)
                if not initial_signals.empty:
                    # Get the last signal
                    latest_signal = initial_signals.iloc[-1].copy()  # Create a copy to avoid SettingWithCopyWarning
                    macd_position = latest_signal.get('macd_position', '')
                    
                    # Create a new DataFrame for the initial action
                    initial_action = pd.DataFrame([latest_signal])
                    
                    # Set initial action based on current MACD position
                    if macd_position == 'ABOVE':
                        logger.info(f"Initial MACD position for {symbol} is ABOVE signal line - Taking initial BUY action")
                        initial_action.loc[0, 'action'] = 'BUY'
                        initial_action.loc[0, 'position'] = 1.0
                        initial_action.loc[0, 'position_type'] = 'LONG'
                        initial_action.loc[0, 'shares'] = strategy.shares_per_trade
                        initial_action.loc[0, 'signal'] = 1.0
                        
                        # Execute the initial BUY
                        logger.info(f"Executing initial BUY for {symbol} - {strategy.shares_per_trade} shares")
                        self.place_market_order(symbol, strategy.shares_per_trade, OrderSide.BUY)
                        
                    elif macd_position == 'BELOW':
                        logger.info(f"Initial MACD position for {symbol} is BELOW signal line - Taking initial SHORT action")
                        initial_action.loc[0, 'action'] = 'SHORT'
                        initial_action.loc[0, 'position'] = -1.0
                        initial_action.loc[0, 'position_type'] = 'SHORT'
                        initial_action.loc[0, 'shares'] = strategy.shares_per_trade
                        initial_action.loc[0, 'signal'] = -1.0
                        
                        # Execute the initial SHORT
                        logger.info(f"Executing initial SHORT for {symbol} - {strategy.shares_per_trade} shares")
                        self.place_market_order(symbol, strategy.shares_per_trade, OrderSide.SELL)
                    
                    # Save the initial state
                    self.save_strategy_state(symbol, strategy.name, {
                        'position_type': initial_action.loc[0, 'position_type'],
                        'shares': strategy.shares_per_trade,
                        'last_action': initial_action.loc[0, 'action'],
                        'last_signal_time': datetime.now().isoformat()
                    })
            except Exception as e:
                logger.error(f"Error initializing strategy for {symbol}: {e}")
        
        if not strategy_instances:
            logger.error("No valid symbols to trade. Exiting.")
            return
            
        logger.info(f"Starting continuous strategy execution at {interval} minute intervals")
        logger.info(f"Press Ctrl+C to stop the execution")
        
        # Main loop - run continuously
        while True:
            current_time = datetime.now()
            current_time_et = current_time.time()  # Extract just the time portion
            logger.info(f"Running strategy at {current_time}")
            
            # Check if market is open
            clock = self.trading_client.get_clock()
            
            # Determine the current market session
            if market_open <= current_time_et <= market_close:
                # Regular market hours (9:30 AM - 4:00 PM ET)
                is_market_hours = True
                is_pre_market = False
                is_after_hours = False
                is_overnight = False
            elif pre_market_open <= current_time_et < market_open:
                # Pre-market hours (4:00 AM - 9:30 AM ET)
                is_market_hours = False
                is_pre_market = True
                is_after_hours = False
                is_overnight = False
            elif market_close < current_time_et <= after_hours_close:
                # After-hours session (4:00 PM - 8:00 PM ET)
                is_market_hours = False
                is_pre_market = False
                is_after_hours = True
                is_overnight = False
            else:
                # Overnight session (8:00 PM - 4:00 AM ET)
                is_market_hours = False
                is_pre_market = False
                is_after_hours = False
                is_overnight = True
            
            # Log the current market session
            if is_market_hours:
                logger.info("Current session: Regular market hours")
            elif is_pre_market:
                logger.info("Current session: Pre-market hours")
            elif is_after_hours:
                logger.info("Current session: After-hours session")
            elif is_overnight:
                logger.info("Current session: Overnight session")
            
            # Check if we can trade in the current session
            can_trade = clock.is_open or \
                       (self.extended_hours and (is_pre_market or is_after_hours)) or \
                       (self.overnight_trading and is_overnight)
            
            if not can_trade:
                next_open = clock.next_open.strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"Cannot trade in current session. Next regular market open: {next_open}")
                logger.info(f"Extended hours trading: {self.extended_hours}, Overnight trading: {self.overnight_trading}")
                # Sleep until next check (still check periodically during closed market)
                time.sleep(interval * 60)
                continue
            
            # Process each symbol
            for symbol in symbols:
                if symbol not in strategy_instances:
                    continue
                    
                strategy = strategy_instances[symbol]
                data = historical_data[symbol]
                
                try:
                    # Get latest real-time data
                    realtime_data = self.get_realtime_data(symbol)
                    if realtime_data.empty:
                        logger.warning(f"No real-time data available for {symbol}, skipping this iteration")
                        continue
                        
                    # Append to historical data and keep only the last 100 bars
                    updated_data = pd.concat([data, realtime_data])
                    updated_data = updated_data.iloc[-100:]
                    
                    # Update our stored data for next iteration
                    # Maintain a longer history but limit it to a reasonable size for memory efficiency
                    max_historical_bars = 500  # Keep up to 500 bars for accurate MACD calculation
                    
                    # Store the updated data with the new bar
                    historical_data[symbol] = updated_data
                    
                    # Trim if we exceed our maximum size
                    if len(historical_data[symbol]) > max_historical_bars:
                        historical_data[symbol] = historical_data[symbol].iloc[-max_historical_bars:]
                        
                    logger.info(f"Maintaining {len(historical_data[symbol])} historical bars for {symbol} MACD calculation")
                    
                    # Generate signals - pass the symbol to ensure correct MACD calculation
                    # This allows the strategy to apply symbol-specific adjustments
                    try:
                        # Try to pass the symbol parameter
                        signals = strategy.generate_signals(updated_data, symbol=symbol)
                    except TypeError:
                        # Fall back to the original method if the strategy doesn't accept a symbol parameter
                        signals = strategy.generate_signals(updated_data)
                        
                    # Get current positions to determine if we need to take initial action
                    positions = self.trading_client.get_all_positions()
                    current_position = next((p for p in positions if p.symbol == symbol), None)
                    
                    # If we have no position and no action is specified, but MACD is in a definite position,
                    # we should take initial action based on the current MACD position
                    if not current_position and signals.iloc[-1]['action'] == '':
                        # Get the current MACD position
                        macd_position = signals.iloc[-1]['macd_position']
                        logger.info(f"No current position for {symbol} and MACD is {macd_position} - taking initial action")
                        
                        # Force an initial action based on current MACD position
                        if macd_position == 'ABOVE':
                            # MACD is above signal line - buy
                            signals.iloc[-1, signals.columns.get_loc('action')] = 'BUY'
                            signals.iloc[-1, signals.columns.get_loc('shares')] = 100
                            logger.info(f"Forcing initial BUY for {symbol} based on MACD position ABOVE")
                        elif macd_position == 'BELOW':
                            # MACD is below signal line - short
                            signals.iloc[-1, signals.columns.get_loc('action')] = 'SHORT'
                            signals.iloc[-1, signals.columns.get_loc('shares')] = 100
                            logger.info(f"Forcing initial SHORT for {symbol} based on MACD position BELOW")
                    
                    # Get the latest signal
                    if not signals.empty:
                        latest_signal = signals.iloc[-1]
                        macd_position = latest_signal.get('macd_position', '')
                        action = latest_signal.get('action', '')
                        position_type = latest_signal.get('position_type', '')
                        
                        # Get the current position from Alpaca
                        positions = self.trading_client.get_all_positions()
                        current_position = next((p for p in positions if p.symbol == symbol), None)
                        
                        # Log the current state with all relevant information
                        if current_position:
                            logger.info(f"Current position for {symbol}: {current_position.qty} shares, Side: {current_position.side}")
                            
                        # Check if we need to take action based on the current MACD position
                        # This ensures we're acting on the current state, not just waiting for crossovers
                        if action == '' and macd_position:
                            # Get the strategy state
                            strategy_state = self.get_strategy_state(symbol, strategy.name)
                            current_position_type = strategy_state.get('position_type', '') if strategy_state else ''
                            
                            # If MACD is above signal line but we're in SHORT position
                            if macd_position == 'ABOVE' and current_position_type == 'SHORT':
                                logger.info(f"MACD position mismatch detected: MACD is ABOVE signal but position is SHORT")
                                signals.loc[signals.index[-1], 'action'] = 'COVER_AND_BUY'
                                signals.loc[signals.index[-1], 'position'] = 1.0
                                signals.loc[signals.index[-1], 'position_type'] = 'LONG'
                                signals.loc[signals.index[-1], 'shares'] = strategy.shares_per_trade
                                
                            # If MACD is below signal line but we're in LONG position
                            elif macd_position == 'BELOW' and current_position_type == 'LONG':
                                logger.info(f"MACD position mismatch detected: MACD is BELOW signal but position is LONG")
                                signals.loc[signals.index[-1], 'action'] = 'SELL_AND_SHORT'
                                signals.loc[signals.index[-1], 'position'] = -1.0
                                signals.loc[signals.index[-1], 'position_type'] = 'SHORT'
                                signals.loc[signals.index[-1], 'shares'] = strategy.shares_per_trade
                    
                    # Execute the strategy based on signals
                    self.execute_signals(symbol, signals, strategy)
                    
                    logger.info(f"Completed strategy execution for {symbol}")
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
            
            # Sleep until next interval
            logger.info(f"Waiting for next execution in {interval} minute(s)...")
            logger.info("\n" + "-"*80 + "\n")  # Add a visual separator in logs between intervals
            time.sleep(interval * 60)
    
    def run_with_realtime_data(self, symbols, strategy_name="macd", **strategy_params):
        """
        Run the trading system with real-time data.
        This method combines historical data with real-time updates.
        """
        # First, initialize with historical data
        for symbol in symbols:
            # Get historical data for initial strategy setup
            historical_data = self.get_historical_data(symbol, limit=100)
            if historical_data.empty:
                logger.error(f"No historical data available for {symbol}")
                continue
                
            # Ensure data types are numeric for calculations
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in historical_data.columns:
                    historical_data[col] = pd.to_numeric(historical_data[col], errors='coerce')
            
            logger.info(f"Historical data for {symbol} prepared with columns: {historical_data.columns}")
            
            # Create strategy instance
            try:
                strategy = StrategyFactory.get_strategy(strategy_name, **strategy_params)
                logger.info(f"Using {strategy.name} strategy for {symbol} with real-time data")
            except Exception as e:
                logger.error(f"Error creating strategy: {e}")
                continue
            
            # Generate initial signals from historical data
            try:
                signals = strategy.generate_signals(historical_data)
                logger.info(f"Generated initial signals for {symbol} using historical data")
            except Exception as e:
                logger.error(f"Error generating signals from historical data: {e}")
                continue
            
            # Get the latest real-time data
            realtime_data = self.get_realtime_data(symbol)
            if not realtime_data.empty:
                try:
                    # Append real-time data to historical data
                    updated_data = pd.concat([historical_data, realtime_data])
                    
                    # Re-generate signals with the updated data
                    updated_signals = strategy.generate_signals(updated_data)
                    
                    # Execute the strategy based on the latest signals
                    self.execute_signals(symbol, updated_signals, strategy)
                    
                    logger.info(f"Executed strategy for {symbol} with real-time data")
                except Exception as e:
                    logger.error(f"Error processing real-time data: {e}")
                    # Fall back to historical signals
                    self.execute_signals(symbol, signals, strategy)
            else:
                logger.warning(f"No real-time data available for {symbol}, using historical signals only")
                # Execute the strategy based on historical signals only
                self.execute_signals(symbol, signals, strategy)
        
        # Optionally, set up a streaming connection for continuous updates
        # stream = self.setup_realtime_stream(symbols)
        # if stream:
        #     stream.run()
    
    def execute_signals(self, symbol, signals, strategy):
        """
        Execute trading signals for a symbol.
        This is a helper method used by run_with_realtime_data.
        """
        if len(signals) < 2:
            logger.warning(f"Not enough data for {symbol} to generate signals")
            return
        
        # Get the latest signal
        latest_signal = signals.iloc[-1]
        
        # Extract signal information
        curr_signal = latest_signal['signal']
        position_change = latest_signal['position']
        position_type = latest_signal['position_type']
        shares = latest_signal['shares']
        action = latest_signal['action']
        macd_position = latest_signal.get('macd_position', 'UNKNOWN')
        
        # Get current positions
        positions = self.trading_client.get_all_positions()
        current_position = next((p for p in positions if p.symbol == symbol), None)
        
        # Get current position quantity (positive for long, negative for short)
        current_qty = 0
        position_side = 'none'
        if current_position is not None:
            current_qty = float(current_position.qty)
            position_side = current_position.side
            if position_side == 'short':
                current_qty = -current_qty
        
        # Log the current signal with MACD position and current holdings
        logger.info(f"{symbol} - Signal: {curr_signal}, Position: {position_change}, MACD Position: {macd_position}, Action: {action}, Shares: {shares}")
        logger.info(f"Current position for {symbol}: {abs(current_qty)} shares, Side: {position_side}")
        
        # If no action needed, return early
        if action == '':
            logger.info(f"No action needed for {symbol}")
            return
            
        # Ensure we have a valid action to execute
        if shares <= 0:
            logger.warning(f"Invalid shares quantity for {symbol}: {shares}. Setting to default 100.")
            shares = 100
        
        # Get account information
        account = self.trading_client.get_account()
        account_value = float(account.portfolio_value)
        
        # Check current positions
        positions = self.trading_client.get_all_positions()
        current_position = next((p for p in positions if p.symbol == symbol), None)
        
        # Get current position quantity (positive for long, negative for short)
        current_qty = 0
        if current_position is not None:
            current_qty = float(current_position.qty)
            if current_position.side == 'short':
                current_qty = -current_qty
        
        # Trading logic based on the action
        if action == 'BUY':
            # Simple buy signal - buy shares
            self.place_market_order(symbol, shares, OrderSide.BUY)
            logger.info(f"BUY: {shares} shares of {symbol} - {strategy.name} strategy")
            
        elif action == 'SHORT':
            # Simple short signal - short shares
            self.place_market_order(symbol, shares, OrderSide.SELL)
            logger.info(f"SHORT: {shares} shares of {symbol} - {strategy.name} strategy")
            
        elif action == 'COVER_AND_BUY':
            # Transition from short to long
            # First, cover the existing short position
            if current_qty < 0:
                cover_qty = abs(current_qty)
                self.place_market_order(symbol, cover_qty, OrderSide.BUY)
                logger.info(f"COVER: {cover_qty} shares of {symbol} - {strategy.name} strategy")
            
            # Then buy additional shares
            self.place_market_order(symbol, shares, OrderSide.BUY)
            logger.info(f"BUY: {shares} shares of {symbol} after covering - {strategy.name} strategy")
            
        elif action == 'SELL_AND_SHORT':
            # Transition from long to short
            try:
                # First, sell the existing long position
                if current_qty > 0:
                    sell_order_id = self.place_market_order(symbol, current_qty, OrderSide.SELL)
                    logger.info(f"SELL: {current_qty} shares of {symbol} - {strategy.name} strategy")
                    
                    # Wait for the sell order to complete
                    logger.info(f"Waiting for sell order to complete before shorting...")
                    time.sleep(2)  # Give the order time to process
                    
                    # Check if the order is filled
                    try:
                        order_status = self.trading_client.get_order_by_id(sell_order_id).status
                        logger.info(f"Sell order status: {order_status}")
                    except Exception as e:
                        logger.warning(f"Could not check order status: {e}")
                
                # Get updated position before shorting
                positions = self.trading_client.get_all_positions()
                current_position = next((p for p in positions if p.symbol == symbol), None)
                if current_position:
                    logger.info(f"Current position before shorting: {current_position.qty} shares")
                else:
                    logger.info(f"No current position for {symbol} before shorting")
                
                # Then short additional shares
                self.place_market_order(symbol, shares, OrderSide.SELL)
                logger.info(f"SHORT: {shares} shares of {symbol} after selling - {strategy.name} strategy")
            except Exception as e:
                logger.error(f"Error during SELL_AND_SHORT for {symbol}: {e}")
                # Don't attempt to short if we couldn't sell first
        
        # Update the strategy state
        self.save_strategy_state(symbol, strategy.name, {
            'position_type': position_type,
            'shares': shares,
            'last_action': action,
            'last_signal_time': datetime.now().isoformat()
        })
    
    def calculate_position_size(self, entry_price, stop_price, account_value):
        """Calculate position size based on risk management rules."""
        if entry_price <= stop_price:
            logger.error("Entry price must be greater than stop price for long positions")
            return 0
        
        risk_amount = account_value * self.risk_per_trade
        risk_per_share = abs(entry_price - stop_price)
        
        if risk_per_share == 0:
            logger.error("Risk per share cannot be zero")
            return 0
        
        shares = int(risk_amount / risk_per_share)
        return shares
    
    def check_extended_hours_eligibility(self, symbol):
        """Check if the account and symbol are eligible for extended hours trading.
        
        Args:
            symbol: The stock symbol to check
            
        Returns:
            tuple: (account_eligible, symbol_eligible, error_message)
        """
        try:
            # Check if the account supports extended hours trading
            account = self.trading_client.get_account()
            account_eligible = True  # Assume eligible by default
            
            # Check if the symbol is available for extended hours trading
            try:
                # Get asset information
                asset = self.trading_client.get_asset(symbol)
                
                if not asset.tradable:
                    return False, False, f"{symbol} is not tradable"
                
                if not asset.easy_to_borrow:
                    logger.warning(f"{symbol} is not easy to borrow, which may limit short selling")
                
                # Check if the asset is fractionable (indicates higher liquidity)
                symbol_eligible = asset.fractionable
                
                # Additional check for extended hours eligibility
                if hasattr(asset, 'extended_hours_eligible'):
                    symbol_eligible = asset.extended_hours_eligible
                
                # Log the asset details
                logger.info(f"Asset details for {symbol}: Tradable: {asset.tradable}, Easy to borrow: {asset.easy_to_borrow}, Fractionable: {asset.fractionable}")
                
                return account_eligible, symbol_eligible, ""
            except Exception as e:
                logger.warning(f"Error checking symbol eligibility for {symbol}: {e}")
                return account_eligible, False, f"Error checking symbol: {e}"
                
        except Exception as e:
            logger.error(f"Error checking account eligibility: {e}")
            return False, False, f"Error checking account: {e}"
    
    def place_market_order(self, symbol, qty, side, extended_hours=None, limit_price=None):
        """Place a market order with support for extended hours trading.
        
        Args:
            symbol: The stock symbol
            qty: Quantity of shares to buy/sell
            side: Buy or sell side
            extended_hours: Override the default extended hours setting (optional)
            limit_price: Specific limit price to use (required for extended hours)
        """
        # Check if we should use extended hours
        use_extended_hours = self.extended_hours if extended_hours is None else extended_hours
        
        # Check if it's currently outside regular market hours (9:30 AM - 4:00 PM ET)
        current_time = datetime.now().time()
        market_open = datetime.strptime("09:30", "%H:%M").time()
        market_close = datetime.strptime("16:00", "%H:%M").time()
        pre_market_open = datetime.strptime("04:00", "%H:%M").time()
        after_hours_close = datetime.strptime("20:00", "%H:%M").time()
        
        # Determine the current market session
        if market_open <= current_time <= market_close:
            # Regular market hours (9:30 AM - 4:00 PM ET)
            is_market_hours = True
            is_pre_market = False
            is_after_hours = False
            is_overnight = False
        elif pre_market_open <= current_time < market_open:
            # Pre-market hours (4:00 AM - 9:30 AM ET)
            is_market_hours = False
            is_pre_market = True
            is_after_hours = False
            is_overnight = False
        elif market_close < current_time <= after_hours_close:
            # After-hours session (4:00 PM - 8:00 PM ET)
            is_market_hours = False
            is_pre_market = False
            is_after_hours = True
            is_overnight = False
        else:
            # Overnight session (8:00 PM - 4:00 AM ET)
            is_market_hours = False
            is_pre_market = False
            is_after_hours = False
            is_overnight = True
        
        # Log the current market session
        if is_market_hours:
            logger.info("Trading during regular market hours")
        elif is_pre_market:
            logger.info("Trading during pre-market hours")
        elif is_after_hours:
            logger.info("Trading during after-hours session")
        elif is_overnight:
            logger.info("Trading during overnight session")
        
        # Check if we can trade in the current session based on settings
        can_trade_by_settings = is_market_hours or \
                   (use_extended_hours and (is_pre_market or is_after_hours)) or \
                   (self.overnight_trading and is_overnight)
        
        if not can_trade_by_settings:
            logger.warning(f"Cannot place order for {symbol} - outside of allowed trading hours")
            logger.warning(f"Extended hours trading: {self.extended_hours}, Overnight trading: {self.overnight_trading}")
            return None
            
        # For extended hours or overnight trading, check eligibility
        if use_extended_hours or is_overnight:
            account_eligible, symbol_eligible, error_message = self.check_extended_hours_eligibility(symbol)
            
            if not account_eligible:
                logger.warning(f"Your account does not support extended hours trading: {error_message}")
                return None
                
            if not symbol_eligible:
                logger.warning(f"{symbol} is not eligible for extended hours trading: {error_message}")
                logger.warning("Attempting to place the order anyway, but it may be rejected by the broker")
                # We'll still try to place the order, but warn the user
        
        # For extended hours and overnight trading, we MUST use limit orders
        if use_extended_hours or is_overnight:
            # Get the latest quote to determine a good limit price if not provided
            if limit_price is None:
                try:
                    quote_request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
                    quotes = self.data_client.get_stock_latest_quote(quote_request)
                    
                    if symbol in quotes:
                        quote = quotes[symbol]
                        # Get price information
                        ask_price = float(quote.ask_price)
                        bid_price = float(quote.bid_price)
                        spread = ask_price - bid_price
                        spread_percentage = (spread / bid_price) * 100 if bid_price > 0 else 0
                        
                        # Log the current spread information
                        logger.info(f"Current quote - Ask: ${ask_price}, Bid: ${bid_price}, Spread: ${spread:.2f} ({spread_percentage:.2f}%)")
                        
                        # Adjust limit price based on session and spread
                        if is_overnight:
                            # During overnight, spreads can be wider, so use more aggressive pricing
                            # but with a cap to avoid extreme prices
                            if side == OrderSide.BUY:
                                # For buy orders during overnight, use a higher buffer (1-2%) to ensure execution
                                # but cap it at a reasonable level
                                buffer_percentage = min(max(1.0, spread_percentage), 3.0)
                                limit_price = round(ask_price * (1 + buffer_percentage/100), 2)
                                logger.info(f"Overnight BUY order - Using {buffer_percentage:.2f}% buffer above ask")
                            else:  # SELL
                                # For sell orders during overnight, use a higher buffer (1-2%) to ensure execution
                                # but cap it at a reasonable level
                                buffer_percentage = min(max(1.0, spread_percentage), 3.0)
                                limit_price = round(bid_price * (1 - buffer_percentage/100), 2)
                                logger.info(f"Overnight SELL order - Using {buffer_percentage:.2f}% buffer below bid")
                        else:  # Extended hours (pre-market or after-hours)
                            # During extended hours, spreads are typically narrower than overnight
                            if side == OrderSide.BUY:
                                # For buy orders during extended hours
                                buffer_percentage = min(max(0.5, spread_percentage/2), 1.5)
                                limit_price = round(ask_price * (1 + buffer_percentage/100), 2)
                                logger.info(f"Extended hours BUY order - Using {buffer_percentage:.2f}% buffer above ask")
                            else:  # SELL
                                # For sell orders during extended hours
                                buffer_percentage = min(max(0.5, spread_percentage/2), 1.5)
                                limit_price = round(bid_price * (1 - buffer_percentage/100), 2)
                                logger.info(f"Extended hours SELL order - Using {buffer_percentage:.2f}% buffer below bid")
                        
                        logger.info(f"Setting limit price for {side} order to ${limit_price}")
                    else:
                        logger.warning(f"Could not get quote for {symbol}, cannot place extended hours order without price")
                        return None
                except Exception as e:
                    logger.warning(f"Error getting quote for limit price: {e}")
                    logger.warning("Cannot place extended hours order without a valid limit price")
                    return None
            
            # Create a limit order for extended/overnight hours
            # IMPORTANT: Extended hours trading REQUIRES limit orders with DAY time in force
            order_data = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                limit_price=limit_price,  # Must provide a limit price
                time_in_force=TimeInForce.DAY,  # Must be DAY for extended hours
                extended_hours=True  # Must be True for extended hours
            )
            logger.info(f"Creating limit order for extended/overnight hours: {symbol} at ${limit_price}")
        else:
            # Regular market hours can use market orders
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY
            )
        
        try:
            order = self.trading_client.submit_order(order_data)
            session_type = "regular hours" if is_market_hours else "extended hours" if (is_pre_market or is_after_hours) else "overnight"
            logger.info(f"Order placed during {session_type} - Symbol: {symbol}, Side: {side}, Qty: {qty}, Order ID: {order.id}")
            return order.id
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    def run_strategy(self, symbol, strategy_name="macd", **strategy_params):
        """
        Run a trading strategy on a symbol.
        
        Args:
            symbol: The stock symbol to trade
            strategy_name: The name of the strategy to use (default: "macd")
            **strategy_params: Additional parameters for the strategy
        """
        # Get historical data (100 days should be enough for most strategies)
        data = self.get_historical_data(symbol, limit=100)
        if data.empty:
            logger.error(f"No historical data available for {symbol}")
            return
        
        # Create strategy instance
        try:
            strategy = StrategyFactory.get_strategy(strategy_name, **strategy_params)
            logger.info(f"Using {strategy.name} strategy for {symbol}")
        except Exception as e:
            logger.error(f"Error creating strategy: {e}")
            return
        
        # Generate signals
        signals = strategy.generate_signals(data)
        
        if len(signals) < 2:
            logger.warning(f"Not enough data for {symbol} to generate signals")
            return
        
        # Get the last row to check for position changes
        latest_signal = signals.iloc[-1]
        
        # Extract signal information
        curr_signal = latest_signal['signal']
        position_change = latest_signal['position']
        position_type = latest_signal['position_type']
        shares = latest_signal['shares']
        action = latest_signal['action']
        
        # Log the current signal
        logger.info(f"{symbol} - Signal: {curr_signal}, Position: {position_change}, Action: {action}, Shares: {shares}")
        
        # If no action needed, return early
        if action == '':
            logger.info(f"No action needed for {symbol}")
            return
        
        # Get account information
        account = self.trading_client.get_account()
        account_value = float(account.portfolio_value)
        
        # Check current positions
        positions = self.trading_client.get_all_positions()
        current_position = next((p for p in positions if p.symbol == symbol), None)
        
        # Get current position quantity (positive for long, negative for short)
        current_qty = 0
        if current_position is not None:
            current_qty = float(current_position.qty)
            if current_position.side == 'short':
                current_qty = -current_qty
        
        # Trading logic based on the action
        if action == 'BUY':
            # Simple buy signal - buy 100 shares
            self.place_market_order(symbol, shares, OrderSide.BUY)
            logger.info(f"BUY: {shares} shares of {symbol} - {strategy.name} strategy")
            
        elif action == 'SHORT':
            # Simple short signal - short 100 shares
            self.place_market_order(symbol, shares, OrderSide.SELL)
            logger.info(f"SHORT: {shares} shares of {symbol} - {strategy.name} strategy")
            
        elif action == 'COVER_AND_BUY':
            # Transition from short to long
            # First, cover the existing short position
            if current_qty < 0:
                cover_qty = abs(current_qty)
                self.place_market_order(symbol, cover_qty, OrderSide.BUY)
                logger.info(f"COVER: {cover_qty} shares of {symbol} - {strategy.name} strategy")
            
            # Then buy additional shares
            self.place_market_order(symbol, shares, OrderSide.BUY)
            logger.info(f"BUY: {shares} shares of {symbol} after covering - {strategy.name} strategy")
            
        elif action == 'SELL_AND_SHORT':
            # Transition from long to short
            try:
                # First, sell the existing long position
                if current_qty > 0:
                    sell_order_id = self.place_market_order(symbol, current_qty, OrderSide.SELL)
                    logger.info(f"SELL: {current_qty} shares of {symbol} - {strategy.name} strategy")
                    
                    # Wait for the sell order to complete
                    logger.info(f"Waiting for sell order to complete before shorting...")
                    time.sleep(2)  # Give the order time to process
                    
                    # Check if the order is filled
                    try:
                        order_status = self.trading_client.get_order_by_id(sell_order_id).status
                        logger.info(f"Sell order status: {order_status}")
                    except Exception as e:
                        logger.warning(f"Could not check order status: {e}")
                
                # Get updated position before shorting
                positions = self.trading_client.get_all_positions()
                current_position = next((p for p in positions if p.symbol == symbol), None)
                if current_position:
                    logger.info(f"Current position before shorting: {current_position.qty} shares")
                else:
                    logger.info(f"No current position for {symbol} before shorting")
                
                # Then short additional shares
                self.place_market_order(symbol, shares, OrderSide.SELL)
                logger.info(f"SHORT: {shares} shares of {symbol} after selling - {strategy.name} strategy")
            except Exception as e:
                logger.error(f"Error during SELL_AND_SHORT for {symbol}: {e}")
                # Don't attempt to short if we couldn't sell first
            
        # Update the strategy state
        self.save_strategy_state(symbol, strategy_name, {
            'position_type': position_type,
            'shares': shares,
            'last_action': action,
            'last_signal_time': datetime.now().isoformat()
        })
        
    def save_strategy_state(self, symbol, strategy_name, state_data):
        """
        Save the strategy state for a symbol.
        This allows tracking position and other information between runs.
        """
        import json
        
        # Create state directory if it doesn't exist
        state_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strategy_state')
        os.makedirs(state_dir, exist_ok=True)
        
        # Create state file path
        state_file = os.path.join(state_dir, f"{symbol}_{strategy_name}.json")
        
        # Convert any NumPy types to Python native types
        serializable_data = {}
        for key, value in state_data.items():
            if hasattr(value, 'item'):
                # Convert NumPy types to Python native types
                serializable_data[key] = value.item()
            else:
                serializable_data[key] = value
        
        # Save state to file
        with open(state_file, 'w') as f:
            json.dump(serializable_data, f)
            
        logger.info(f"Strategy state for {symbol} ({strategy_name}): {serializable_data}")
        
    def get_strategy_state(self, symbol, strategy_name):
        """
        Get the saved strategy state for a symbol.
        Returns None if no state is saved.
        """
        import json
        
        # Create state file path
        state_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strategy_state')
        state_file = os.path.join(state_dir, f"{symbol}_{strategy_name}.json")
        
        # Check if state file exists
        if not os.path.exists(state_file):
            return None
            
        # Load state from file
        try:
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            return state_data
        except Exception as e:
            logger.error(f"Error loading strategy state for {symbol} ({strategy_name}): {e}")
            return None
            
    def run_options_strategy(self):
        """
        Placeholder for options trading strategy.
        This would be implemented based on specific options trading logic.
        """
        logger.info("Options trading strategy not yet implemented")
        # Future implementation for options trading
    
    def run(self, symbols=None, strategy_name="macd", **strategy_params):
        """Run the trading system on the specified symbols with the specified strategy."""
        if symbols is None:
            symbols = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META']
        
        logger.info(f"Starting trading system for symbols: {symbols} with strategy: {strategy_name}")
        
        # Display account information
        self.get_account_info()
        
        # Display current positions
        self.get_positions()
        
        # Run strategy for each symbol
        for symbol in symbols:
            logger.info(f"Running {strategy_name} strategy for {symbol}")
            self.run_strategy(symbol, strategy_name, **strategy_params)
        
        logger.info("Trading system execution completed")


if __name__ == "__main__":
    import argparse
    import traceback
    
    # Set up command line arguments
    parser = argparse.ArgumentParser(description='Alpaca Quantitative Trading System')
    parser.add_argument('--mode', type=str, choices=['historical', 'realtime', 'continuous'], default='historical',
                        help='Trading mode: historical (default), realtime (one-time), or continuous (runs every minute)')
    parser.add_argument('--symbols', type=str, nargs='+',
                        help='Symbols to trade (space-separated). If not provided, uses DEFAULT_SYMBOLS from strategies.py')
    parser.add_argument('--strategy', type=str,
                        help='Strategy to use. If not provided, uses DEFAULT_STRATEGY from strategies.py')
    parser.add_argument('--interval', type=int, default=1,
                        help='Interval in minutes between strategy executions (only for continuous mode)')
    
    args = parser.parse_args()
    
    try:
        # Get strategy parameters from strategies.py or command line
        strategy_name = args.strategy if args.strategy else DEFAULT_STRATEGY
        strategy_params = DEFAULT_STRATEGY_CONFIGS.get(strategy_name, {})
        symbols = args.symbols if args.symbols else DEFAULT_SYMBOLS
        
        logger.info(f"Starting trading system in {args.mode} mode")
        logger.info(f"Using strategy: {strategy_name} with symbols: {symbols}")
        
        # Initialize the trading system
        trading_system = AlpacaTradingSystem()
        
        # Run the trading system in the selected mode
        if args.mode == 'continuous':
            logger.info(f"Running continuously with {args.interval} minute intervals")
            trading_system.run_continuous_strategy(symbols, strategy_name=strategy_name, 
                                                interval=args.interval, **strategy_params)
        elif args.mode == 'realtime':
            logger.info("Running with real-time data (one-time execution)")
            trading_system.run_with_realtime_data(symbols, strategy_name=strategy_name, **strategy_params)
        else:
            logger.info("Running with historical data")
            trading_system.run(symbols, strategy_name=strategy_name, **strategy_params)
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        traceback.print_exc()
