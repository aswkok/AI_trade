#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MACD Options Trading System

This module implements a trading system that uses MACD signals to trade options,
extending the existing stock trading system to handle options-specific requirements.
"""

import os
import time
import logging
import warnings
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Suppress specific warnings for cleaner display
warnings.filterwarnings("ignore", category=RuntimeWarning, message="divide by zero encountered")
warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered")

# Import the base trading system and quote monitor
from main import AlpacaTradingSystem
from quote_monitor_selector import QuoteMonitor

# Import our options strategy
from options_trader import MACDOptionsStrategy, OptionsContract, OptionsChain

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

class MACDOptionsTrader:
    """
    Integrated trading system for options based on MACD signals.
    This class connects real-time market data, MACD strategy, and options execution.
    """
    
    def __init__(self, symbol, interval_seconds=60, 
                 fast_window=13, slow_window=21, signal_window=9,
                 risk_per_trade=0.02, trade_style='directional',
                 extended_hours=True, warmup_period_minutes=60):
        """
        Initialize the MACD options trader.
        
        Args:
            symbol: Underlying stock symbol to trade
            interval_seconds: Update interval in seconds
            fast_window: Fast EMA window for MACD
            slow_window: Slow EMA window for MACD
            signal_window: Signal line window for MACD
            risk_per_trade: Percentage of account to risk per trade (default: 0.02)
            trade_style: Trading style - 'directional', 'income', or 'combined' (default: 'directional')
            extended_hours: Whether to trade during extended hours
            warmup_period_minutes: Warm-up period in minutes before trading begins
        """
        # Load environment variables
        load_dotenv(override=True)
        
        # Store configuration
        self.symbol = symbol
        self.interval_seconds = interval_seconds
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.risk_per_trade = risk_per_trade
        self.trade_style = trade_style
        self.extended_hours = extended_hours
        self.warmup_period_minutes = warmup_period_minutes
        
        # Initialize components
        logger.info(f"Initializing MACD options trader for {symbol}")
        
        # 1. Initialize the Quote Monitor for underlying stock
        self.quote_monitor = QuoteMonitor(
            symbol=symbol,
            max_records=max(slow_window * 3, 500),  # Keep enough records for good MACD calculation
            interval_seconds=interval_seconds,
            fast_window=fast_window,
            slow_window=slow_window,
            signal_window=signal_window
        )
        
        # 2. Initialize the MACD Options Strategy
        self.strategy = MACDOptionsStrategy(
            fast_window=fast_window,
            slow_window=slow_window,
            signal_window=signal_window,
            risk_per_trade=risk_per_trade
        )
        
        # Set the quote monitor for the strategy
        self.strategy.set_quote_monitor(self.quote_monitor)
        
        # 3. Initialize the Trading System
        self.trading_system = AlpacaTradingSystem()
        self.trading_system.extended_hours = extended_hours
        
        # System state
        self.is_running = False
        self.start_time = None
        self.last_trade_time = None
        self.current_positions = []  # Track current options positions
        
        # Track IV rank
        self.current_iv_rank = 0.50  # Default to middle IV
        
        logger.info(f"MACD Options Trader initialized for {symbol}")
        logger.info(f"MACD Parameters: Fast={fast_window}, Slow={slow_window}, Signal={signal_window}")
        logger.info(f"Trading style: {trade_style}")
        logger.info(f"Risk per trade: {risk_per_trade:.1%}")
        logger.info(f"Extended hours trading: {extended_hours}")
        logger.info(f"Warm-up period: {warmup_period_minutes} minutes")
    
    def is_warmup_complete(self):
        """Check if the warm-up period is complete."""
        if not self.start_time:
            return False
            
        elapsed_minutes = (datetime.now() - self.start_time).total_seconds() / 60
        return elapsed_minutes >= self.warmup_period_minutes
    
    def update_quotes(self):
        """Check for new quote data from the monitor."""
        if not self.quote_monitor.quotes_df.empty:
            return True
        return False
    
    def get_options_chain(self):
        """
        Get the current options chain for the underlying symbol.
        
        In a production system, this would query a broker API or data provider.
        For this example, we'll return a simulated options chain.
        
        Returns:
            OptionsChain object
        """
        logger.info(f"Fetching options chain for {self.symbol}")
        logger.debug("Starting get_options_chain method")
        
        # In a real implementation, this would call a broker API
        # For now, we'll create a simulated options chain
        
        try:
            logger.debug("Getting current underlying price")
            # Get the current underlying price
            current_price = 0
            if hasattr(self.quote_monitor, 'quotes_df'):
                logger.debug(f"quotes_df exists, type: {type(self.quote_monitor.quotes_df)}")
                if isinstance(self.quote_monitor.quotes_df, pd.DataFrame):
                    logger.debug(f"quotes_df is a DataFrame with {len(self.quote_monitor.quotes_df)} rows")
                    # Explicitly check if the DataFrame is empty to avoid ambiguous truth value error
                    if len(self.quote_monitor.quotes_df) > 0:
                        logger.debug("quotes_df has data, getting mid price")
                        current_price = self.quote_monitor.quotes_df['mid'].iloc[-1]
                        logger.debug(f"Current price from quotes_df: {current_price}")
                    else:
                        logger.info(f"No quotes available for {self.symbol} yet (empty DataFrame)")
                else:
                    logger.debug(f"quotes_df is not a DataFrame: {type(self.quote_monitor.quotes_df)}")
            else:
                logger.debug("No quotes_df attribute found, using fallback")
                
            # Fallback to last known price if needed
            if current_price == 0:
                logger.debug("Using fallback to get current price")
                try:
                    logger.debug("Getting historical data")
                    data = self.trading_system.get_historical_data(self.symbol, limit=1)
                    logger.debug(f"Historical data type: {type(data)}, empty: {data.empty if hasattr(data, 'empty') else 'N/A'}")
                    if hasattr(data, 'empty') and not data.empty:
                        current_price = data['close'].iloc[-1]
                        logger.debug(f"Current price from historical data: {current_price}")
                    else:
                        logger.debug("Historical data is empty or not a DataFrame")
                except Exception as e:
                    logger.error(f"Error getting current price for {self.symbol}: {e}")
                    current_price = 100  # Default value
                    logger.debug(f"Using default price: {current_price}")
        except Exception as e:
            logger.error(f"Error in price determination: {e}")
            current_price = 100  # Default value
            logger.debug(f"Using default price after error: {current_price}")
                
        logger.info(f"Current price for {self.symbol}: ${current_price:.2f}")
        
        try:
            logger.debug("Generating simulated expiration dates")
            # Generate simulated expiration dates (every Friday for next 3 months)
            today = datetime.now()
            expiration_dates = []
            
            # Start with next Friday
            friday = today + timedelta(days=(4 - today.weekday()) % 7)
            for i in range(12):  # 12 weekly expirations
                exp_date = friday + timedelta(days=i*7)
                expiration_dates.append(exp_date.strftime('%Y-%m-%d'))
                
            # Add monthly expirations (third Friday of each month)
            for i in range(1, 6):  # Next 6 months
                month = (today.month + i - 1) % 12 + 1
                year = today.year + (today.month + i - 1) // 12
                
                # Find the third Friday
                first_day = datetime(year, month, 1)
                friday_offset = (4 - first_day.weekday()) % 7
                third_friday = first_day + timedelta(days=friday_offset + 14)
                
                expiration_dates.append(third_friday.strftime('%Y-%m-%d'))
                
            # Remove duplicates and sort
            expiration_dates = sorted(list(set(expiration_dates)))
            logger.debug(f"Generated {len(expiration_dates)} expiration dates")
        except Exception as e:
            logger.error(f"Error generating expiration dates: {e}")
            # Provide a default set of expiration dates
            expiration_dates = [(today + timedelta(days=30)).strftime('%Y-%m-%d'), 
                              (today + timedelta(days=60)).strftime('%Y-%m-%d')]
            logger.debug(f"Using default expiration dates: {expiration_dates}")
        
        try:
            logger.debug("Generating simulated options data")
            # Generate simulated options data
            calls_data = []
            puts_data = []
            
            # Generate strikes around current price (±20%)
            min_strike = current_price * 0.8
            max_strike = current_price * 1.2
            strikes = np.linspace(min_strike, max_strike, 20)
            logger.debug(f"Generated {len(strikes)} strike prices from {min_strike:.2f} to {max_strike:.2f}")
        except Exception as e:
            logger.error(f"Error generating strike prices: {e}")
            # Provide default strike prices
            strikes = [current_price * 0.9, current_price, current_price * 1.1]
            logger.debug(f"Using default strike prices: {strikes}")
        
        # Simulated IV rank - will affect premiums
        iv_rank = self.current_iv_rank
        logger.debug(f"Using IV rank: {iv_rank:.2f}")
        
        # Process each expiration date
        try:
            logger.debug("Starting to process expiration dates")
            for expiration in expiration_dates:
                try:
                    logger.debug(f"Processing expiration date: {expiration}")
                    exp_date = datetime.strptime(expiration, '%Y-%m-%d')
                    days_to_exp = (exp_date - today).days
                    
                    # Base IV - higher for longer expiration
                    base_iv = 0.3 + (days_to_exp / 365) * 0.1
                    
                    # Adjust based on IV rank
                    iv = base_iv * (0.7 + 0.6 * iv_rank)
                    logger.debug(f"Expiration: {expiration}, Days to exp: {days_to_exp}, IV: {iv:.2f}")
                    
                    # Process each strike price for this expiration
                    for strike in strikes:
                        logger.debug(f"Processing strike: {strike:.2f}")
                        
                        try:
                            # Call option
                            call_delta = max(0, min(1, 0.5 + (current_price - strike) / (current_price * iv * np.sqrt(days_to_exp/365))))
                            call_gamma = (np.exp(-(current_price-strike)**2/(2*current_price**2*iv**2*days_to_exp/365)) / 
                                        (current_price * iv * np.sqrt(2*np.pi*days_to_exp/365)))
                            call_theta = -(current_price * iv * np.exp(-(current_price-strike)**2/(2*current_price**2*iv**2*days_to_exp/365)) / 
                                        (2 * np.sqrt(2*np.pi*days_to_exp/365))) / 365
                            call_vega = (current_price * np.sqrt(days_to_exp/365) * 
                                        np.exp(-(current_price-strike)**2/(2*current_price**2*iv**2*days_to_exp/365)) /
                                    (100 * np.sqrt(2*np.pi)))
                            logger.debug(f"Call option Greeks calculated for strike {strike:.2f}")
                            
                            # Call premium (simplified Black-Scholes approximation)
                            call_premium = current_price * call_delta * iv * np.sqrt(days_to_exp/365)
                            logger.debug(f"Call premium calculated: {call_premium:.2f}")
                            
                            # Put option
                            put_delta = max(-1, min(0, -0.5 + (current_price - strike) / (current_price * iv * np.sqrt(days_to_exp/365))))
                            put_gamma = call_gamma  # Same gamma for calls and puts
                            put_theta = call_theta - (strike * 0.01 / 365)  # Slightly more theta decay for puts
                            put_vega = call_vega  # Same vega for calls and puts
                            logger.debug(f"Put option Greeks calculated for strike {strike:.2f}")
                            
                            # Put premium (simplified approximation)
                            put_premium = strike * abs(put_delta) * iv * np.sqrt(days_to_exp/365)
                            logger.debug(f"Put premium calculated: {put_premium:.2f}")
                            
                            # Add to call options data
                            calls_data.append({
                                'expiration': expiration,
                                'strike': strike,
                                'bid': call_premium * 0.95,  # Simulated bid-ask spread
                                'ask': call_premium * 1.05,
                                'delta': call_delta,
                                'gamma': call_gamma,
                                'theta': call_theta,
                                'vega': call_vega,
                                'iv': iv,
                                'underlying_price': current_price,
                                'volume': np.random.randint(10, 1000),
                                'open_interest': np.random.randint(100, 5000)
                            })
                            logger.debug(f"Added call option for strike {strike:.2f} to calls_data")
                            
                            # Add to put options data
                            puts_data.append({
                                'expiration': expiration,
                                'strike': strike,
                                'bid': put_premium * 0.95,  # Simulated bid-ask spread
                                'ask': put_premium * 1.05,
                                'delta': put_delta,
                                'gamma': put_gamma,
                                'theta': put_theta,
                                'vega': put_vega,
                                'iv': iv,
                                'underlying_price': current_price,
                                'volume': np.random.randint(10, 1000),
                                'open_interest': np.random.randint(100, 5000)
                            })
                            logger.debug(f"Added put option for strike {strike:.2f} to puts_data")
                            
                        except Exception as e:
                            logger.error(f"Error processing options for strike {strike:.2f}: {e}")
                            continue
                except Exception as e:
                    logger.error(f"Error processing expiration date {expiration}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error processing expiration dates: {e}")
        
        try:
            logger.debug(f"Converting options data to DataFrames: {len(calls_data)} calls, {len(puts_data)} puts")
            # Convert to DataFrames
            calls_df = pd.DataFrame(calls_data)
            puts_df = pd.DataFrame(puts_data)
            logger.debug("Successfully created DataFrames")
            
            # Create and return the options chain
            logger.debug("Creating OptionsChain object")
            options_chain = OptionsChain(
                underlying=self.symbol,
                expiration_dates=expiration_dates,
                calls=calls_df,
                puts=puts_df
            )
            logger.debug("Successfully created OptionsChain object")
            return options_chain
        except Exception as e:
            logger.error(f"Error creating options chain: {e}")
            # Return a minimal valid options chain to avoid errors
            logger.debug("Creating minimal valid options chain as fallback")
            empty_df = pd.DataFrame(columns=['expiration', 'strike', 'bid', 'ask', 'delta'])
            return OptionsChain(
                underlying=self.symbol,
                expiration_dates=[],
                calls=empty_df,
                puts=empty_df
            )
    
    def update_iv_rank(self):
        """
        Update the current IV rank for the underlying.
        
        In a production system, this would query historical IV data.
        For this example, we'll simulate an IV rank that changes over time.
        """
        # Simulate IV rank - in reality this would be based on historical data
        # For simplicity, let's just oscillate between low and high IV
        hour_of_day = datetime.now().hour
        day_of_week = datetime.now().weekday()
        
        # IV tends to rise before earnings and fall after
        # Here we'll just simulate some patterns
        
        # Higher IV in the morning and late afternoon
        time_factor = 0.5 + 0.5 * np.sin(hour_of_day / 24.0 * 2 * np.pi)
        
        # Higher IV mid-week
        week_factor = 0.5 + 0.5 * np.sin((day_of_week - 2) / 7.0 * 2 * np.pi)
        
        # Combine factors with some randomness
        iv_rank = (0.3 * time_factor + 0.3 * week_factor + 0.4 * np.random.random())
        
        # Clamp to [0, 1] range
        self.current_iv_rank = max(0, min(1, iv_rank))
        
        logger.info(f"Updated IV rank for {self.symbol}: {self.current_iv_rank:.2f}")
        
        return self.current_iv_rank
    
    def process_macd_signal(self):
        """
        Process the latest MACD signal and execute options trades if necessary.
        
        Returns:
            bool: True if a trade was executed, False otherwise
        """
        try:
            # Get the latest MACD signal from the quote monitor
            logger.debug("Getting MACD signal from quote monitor")
            macd_signal = self.quote_monitor.get_macd_signal()
            logger.debug(f"MACD signal received: {macd_signal}")
            
            # If we don't have a valid signal yet, do nothing
            if macd_signal['macd_position'] is None:
                logger.info("Not enough data for MACD calculation yet")
                return False
            
            # Get account information
            logger.debug("Getting account information")
            account = self.trading_system.get_account_info()
            account_value = float(account.portfolio_value)
            logger.debug(f"Account value: ${account_value}")
            
            # Update IV rank
            logger.debug("Updating IV rank")
            self.update_iv_rank()
            
            # Extract signal information
            logger.debug("Extracting signal information")
            signal = macd_signal['signal']
            macd_position = macd_signal['macd_position']
            logger.debug(f"Signal: {signal}, MACD position: {macd_position}")
            
            # Log the types of crossover and crossunder values
            logger.debug(f"Crossover type: {type(macd_signal['crossover'])}, value: {macd_signal['crossover']}")
            logger.debug(f"Crossunder type: {type(macd_signal['crossunder'])}, value: {macd_signal['crossunder']}")
            
            # Ensure crossover and crossunder are proper boolean values, not DataFrames
            crossover = False
            crossunder = False
            
            if isinstance(macd_signal['crossover'], (bool, int, float)):
                crossover = bool(macd_signal['crossover'])
            elif hasattr(macd_signal['crossover'], 'item'):
                # Handle pandas Series or DataFrame
                crossover = bool(macd_signal['crossover'].item())
            else:
                logger.warning(f"Unexpected crossover type: {type(macd_signal['crossover'])}")
            
            if isinstance(macd_signal['crossunder'], (bool, int, float)):
                crossunder = bool(macd_signal['crossunder'])
            elif hasattr(macd_signal['crossunder'], 'item'):
                # Handle pandas Series or DataFrame
                crossunder = bool(macd_signal['crossunder'].item())
            else:
                logger.warning(f"Unexpected crossunder type: {type(macd_signal['crossunder'])}")
                
            logger.debug(f"Processed crossover: {crossover}, crossunder: {crossunder}")
        except Exception as e:
            logger.error(f"Error in signal extraction: {e}")
            raise
        
        # Get the options chain
        logger.debug("Getting options chain")
        options_chain = self.get_options_chain()
        
        # Keep track of whether we executed any trades
        executed_trade = False
        
        # Check for new signals
        logger.debug(f"Checking for signals - crossover: {crossover}, crossunder: {crossunder}")
        if crossover:  # Bullish signal
            logger.info(f"Bullish MACD signal detected for {self.symbol}")
            
            if self.is_warmup_complete():
                if self.trade_style == 'directional' or self.trade_style == 'combined':
                    # Directional trade - buy calls
                    expiration = options_chain.get_nearest_expiration(45)  # ~45 DTE
                    
                    if expiration:
                        # Get a call option with delta around 0.60
                        call_option = options_chain.get_contract_by_delta('call', 0.60, expiration)
                        
                        if call_option:
                            # Calculate position size
                            premium = call_option.premium if call_option.premium else 5.0  # Default if no premium available
                            contracts = max(1, int((account_value * self.risk_per_trade) / (premium * 100)))
                            
                            # Execute the trade
                            logger.info(f"Buying {contracts} contracts of {call_option}")
                            
                            # In a real system, this would connect to a broker API
                            order_id = self.execute_option_order('buy_to_open', call_option, contracts)
                            
                            # Add to current positions
                            self.current_positions.append({
                                'type': 'long_call',
                                'contract': call_option,
                                'contracts': contracts,
                                'entry_price': premium,
                                'entry_date': datetime.now(),
                                'order_id': order_id,
                                'strategy': 'MACD_directional'
                            })
                            
                            executed_trade = True
                
                if self.trade_style == 'income' or self.trade_style == 'combined':
                    # Income trade - sell puts
                    expiration = options_chain.get_nearest_expiration(30)  # ~30 DTE
                    
                    if expiration:
                        # Get a put option with delta around 0.30 (30% probability of expiring ITM)
                        put_option = options_chain.get_contract_by_delta('put', 0.30, expiration)
                        
                        if put_option:
                            # Calculate position size - more conservative for short options
                            premium = put_option.premium if put_option.premium else 2.0
                            contracts = max(1, int((account_value * self.risk_per_trade * 0.5) / (put_option.strike * 100)))
                            
                            # For short puts, the max risk is (strike - premium) * contracts * 100
                            # Limit to a small portion of account
                            contracts = min(contracts, int((account_value * 0.1) / (put_option.strike * 100)))
                            
                            # Execute the trade
                            logger.info(f"Selling {contracts} contracts of {put_option}")
                            
                            # In a real system, this would connect to a broker API
                            order_id = self.execute_option_order('sell_to_open', put_option, contracts)
                            
                            # Add to current positions
                            self.current_positions.append({
                                'type': 'short_put',
                                'contract': put_option,
                                'contracts': contracts,
                                'entry_price': premium,
                                'entry_date': datetime.now(),
                                'order_id': order_id,
                                'strategy': 'MACD_income'
                            })
                        
                        executed_trade = True
            else:
                logger.info(f"Bullish signal detected but still in warm-up period ({self.warmup_period_minutes} minutes)")
                
        elif crossunder:  # Bearish signal
            logger.info(f"Bearish MACD signal detected for {self.symbol}")
            
            if self.is_warmup_complete():
                if self.trade_style == 'directional' or self.trade_style == 'combined':
                    # Directional trade - buy puts
                    expiration = options_chain.get_nearest_expiration(45)
                    
                    if expiration:
                        # Get a put option with delta around 0.60 (absolute value)
                        put_option = options_chain.get_contract_by_delta('put', 0.60, expiration)
                        
                        if put_option:
                            # Calculate position size
                            premium = put_option.premium if put_option.premium else 5.0
                            contracts = max(1, int((account_value * self.risk_per_trade) / (premium * 100)))
                            
                            # Execute the trade
                            logger.info(f"Buying {contracts} contracts of {put_option}")
                            
                            # In a real system, this would connect to a broker API
                            order_id = self.execute_option_order('buy_to_open', put_option, contracts)
                            
                            # Add to current positions
                            self.current_positions.append({
                                'type': 'long_put',
                                'contract': put_option,
                                'contracts': contracts,
                                'entry_price': premium,
                                'entry_date': datetime.now(),
                                'order_id': order_id,
                                'strategy': 'MACD_directional'
                            })
                            
                            executed_trade = True
                
                if self.trade_style == 'income' or self.trade_style == 'combined':
                    # Income trade - sell calls
                    expiration = options_chain.get_nearest_expiration(30)
                    
                    if expiration:
                        # Get a call option with delta around 0.30 (30% probability of expiring ITM)
                        call_option = options_chain.get_contract_by_delta('call', 0.30, expiration)
                        
                        if call_option:
                            # Calculate position size - more conservative for short options
                            premium = call_option.premium if call_option.premium else 2.0
                            
                            # For covered calls, you would limit contracts to the number of shares owned
                            # For this example, we'll just use a small risk percentage
                            contracts = max(1, int((account_value * self.risk_per_trade * 0.5) / (call_option.strike * 100)))
                            
                            # Execute the trade
                            logger.info(f"Selling {contracts} contracts of {call_option}")
                            
                            # In a real system, this would connect to a broker API
                            order_id = self.execute_option_order('sell_to_open', call_option, contracts)
                            
                            # Add to current positions
                            self.current_positions.append({
                                'type': 'short_call',
                                'contract': call_option,
                                'contracts': contracts,
                                'entry_price': premium,
                                'entry_date': datetime.now(),
                                'order_id': order_id,
                                'strategy': 'MACD_income'
                            })
                            
                            executed_trade = True
            else:
                logger.info(f"Bearish signal detected but still in warm-up period ({self.warmup_period_minutes} minutes)")