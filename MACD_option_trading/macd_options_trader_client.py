#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MACD Options Trading Client

This module implements a trading client that connects to an independently running
quote monitor service. It allows the trading logic to:
1. Connect to an already warmed-up quote monitor
2. Start trading immediately once market conditions are met
3. Operate independently from the data collection process
"""

import os
import time
import logging
import argparse
import socket
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Import the base trading system
from main import AlpacaTradingSystem

# Import our options strategy
from options_trader import MACDOptionsStrategy, OptionsContract, OptionsChain

# Import the quote monitor service client interface
from quote_monitor_service_client import QuoteMonitorClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("options_trading_client.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MACDOptionsTraderClient:
    """
    Client for trading options based on MACD signals from an independent quote monitor.
    
    This class connects to a running quote monitor service, retrieves market data,
    and executes options trades based on the MACD signals.
    """
    
    def __init__(self, symbol, interval_seconds=60, 
                 fast_window=13, slow_window=21, signal_window=9,
                 risk_per_trade=0.02, trade_style='directional',
                 extended_hours=True):
        """
        Initialize the MACD options trader client.
        
        Args:
            symbol: Underlying stock symbol to trade
            interval_seconds: Update interval in seconds
            fast_window: Fast EMA window for MACD
            slow_window: Slow EMA window for MACD
            signal_window: Signal line window for MACD
            risk_per_trade: Percentage of account to risk per trade (default: 0.02)
            trade_style: Trading style - 'directional', 'income', or 'combined' (default: 'directional')
            extended_hours: Whether to trade during extended hours
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
        
        # Initialize components
        logger.info(f"Initializing MACD options trader client for {symbol}")
        
        # 1. Connect to the Quote Monitor Service
        self.quote_client = QuoteMonitorClient(symbol)
        
        # 2. Initialize the MACD Options Strategy
        self.strategy = MACDOptionsStrategy(
            fast_window=fast_window,
            slow_window=slow_window,
            signal_window=signal_window,
            risk_per_trade=risk_per_trade,
            trade_style=trade_style
        )
        
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
        
        logger.info(f"MACD Options Trader client initialized for {symbol}")
    
    def wait_for_quote_monitor_ready(self, timeout_seconds=300):
        """
        Wait for the quote monitor to be ready with sufficient data.
        
        Args:
            timeout_seconds: Maximum time to wait in seconds
            
        Returns:
            bool: True if ready, False if timed out
        """
        logger.info(f"Waiting for quote monitor to be ready for {self.symbol}...")
        
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout_seconds:
            if self.quote_client.is_data_ready():
                logger.info(f"Quote monitor for {self.symbol} is ready with MACD data")
                return True
            
            logger.info(f"Quote monitor not ready yet, waiting... ({self.quote_client.get_status()})")
            time.sleep(10)  # Check every 10 seconds
        
        logger.warning(f"Timed out waiting for quote monitor to be ready for {self.symbol}")
        return False
    
    def update_quotes(self):
        """
        Update the latest quote data from the quote monitor service.
        
        Returns:
            bool: True if new data was retrieved, False otherwise
        """
        return self.quote_client.update()
    
    def get_options_chain(self):
        """
        Get the current options chain for the underlying symbol.
        
        In a production system, this would query a broker API or data provider.
        For this example, we'll return a simulated options chain.
        
        Returns:
            OptionsChain object
        """
        # Get the current price from the quote monitor
        current_price = self.quote_client.get_current_price()
        
        if not current_price:
            logger.warning("Unable to get current price from quote monitor")
            return None
        
        # Create a simulated options chain
        chain = OptionsChain(self.symbol)
        
        # Current date for expiration calculations
        today = datetime.now().date()
        
        # Generate some expiration dates (weekly and monthly)
        expirations = []
        
        # Add weekly expirations for the next 6 weeks
        for i in range(1, 7):
            # Find the next Friday
            days_to_friday = (4 - today.weekday()) % 7
            if days_to_friday == 0:
                days_to_friday = 7  # If today is Friday, go to next Friday
            
            friday = today + timedelta(days=days_to_friday + (i-1)*7)
            expirations.append(friday)
        
        # Add monthly expirations for the next 6 months
        for i in range(1, 7):
            # Find the third Friday of each month
            month = (today.month + i - 1) % 12 + 1
            year = today.year + (today.month + i - 1) // 12
            
            # Start with the first day of the month
            first_day = datetime(year, month, 1).date()
            
            # Find the first Friday
            days_to_friday = (4 - first_day.weekday()) % 7
            first_friday = first_day + timedelta(days=days_to_friday)
            
            # The third Friday is 14 days after the first Friday
            third_friday = first_friday + timedelta(days=14)
            
            expirations.append(third_friday)
        
        # Remove duplicates and sort
        expirations = sorted(list(set(expirations)))
        
        # Add expirations to the chain
        for expiry in expirations:
            chain.add_expiration(expiry)
        
        # Generate option contracts for each expiration
        for expiry in expirations:
            days_to_expiry = (expiry - today).days
            
            # Adjust IV based on days to expiration (longer = higher IV)
            base_iv = self.current_iv_rank * 0.4 + 0.1  # Scale to 0.1-0.5
            iv_adjustment = min(0.2, days_to_expiry / 365 * 0.3)  # Time value
            
            # Generate strikes around the current price
            for pct in [-0.30, -0.25, -0.20, -0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
                strike = round(current_price * (1 + pct) * 2) / 2  # Round to nearest 0.5
                
                # Create call option
                call_iv = base_iv + iv_adjustment
                if pct < 0:  # OTM calls have higher IV (volatility skew)
                    call_iv += abs(pct) * 0.2
                
                call_delta = self._calculate_approx_delta('call', current_price, strike, days_to_expiry, call_iv)
                call_option = OptionsContract(
                    symbol=self.symbol,
                    expiration=expiry,
                    strike=strike,
                    option_type='call',
                    bid=self._calculate_option_price('call', current_price, strike, days_to_expiry, call_iv) * 0.95,
                    ask=self._calculate_option_price('call', current_price, strike, days_to_expiry, call_iv) * 1.05,
                    delta=call_delta,
                    gamma=0.01 * (1 - abs(call_delta)),  # Approximate gamma
                    theta=-0.01 * (1 - abs(call_delta)) * current_price / 100,  # Approximate theta
                    vega=0.1 * current_price / 100,  # Approximate vega
                    implied_volatility=call_iv
                )
                chain.add_contract(call_option)
                
                # Create put option
                put_iv = base_iv + iv_adjustment
                if pct > 0:  # OTM puts have higher IV (volatility skew)
                    put_iv += abs(pct) * 0.2
                
                put_delta = self._calculate_approx_delta('put', current_price, strike, days_to_expiry, put_iv)
                put_option = OptionsContract(
                    symbol=self.symbol,
                    expiration=expiry,
                    strike=strike,
                    option_type='put',
                    bid=self._calculate_option_price('put', current_price, strike, days_to_expiry, put_iv) * 0.95,
                    ask=self._calculate_option_price('put', current_price, strike, days_to_expiry, put_iv) * 1.05,
                    delta=put_delta,
                    gamma=0.01 * (1 - abs(put_delta)),  # Approximate gamma
                    theta=-0.01 * (1 - abs(put_delta)) * current_price / 100,  # Approximate theta
                    vega=0.1 * current_price / 100,  # Approximate vega
                    implied_volatility=put_iv
                )
                chain.add_contract(put_option)
        
        return chain
    
    def _calculate_option_price(self, option_type, current_price, strike, days_to_expiry, iv):
        """
        Calculate a simplified option price based on the Black-Scholes approximation.
        This is a very simplified model for simulation purposes only.
        
        Args:
            option_type: 'call' or 'put'
            current_price: Current price of the underlying
            strike: Strike price of the option
            days_to_expiry: Days to expiration
            iv: Implied volatility
            
        Returns:
            float: Approximate option price
        """
        # Convert days to years
        t = days_to_expiry / 365.0
        
        # Intrinsic value
        intrinsic = max(0, current_price - strike) if option_type == 'call' else max(0, strike - current_price)
        
        # Time value (very simplified)
        time_value = current_price * iv * np.sqrt(t)
        
        # Adjust time value based on moneyness
        moneyness = current_price / strike
        if option_type == 'call':
            if moneyness < 0.95:  # OTM
                time_value *= 0.8
            elif moneyness > 1.05:  # ITM
                time_value *= 0.6
        else:  # put
            if moneyness > 1.05:  # OTM
                time_value *= 0.8
            elif moneyness < 0.95:  # ITM
                time_value *= 0.6
        
        return intrinsic + time_value
    
    def _calculate_approx_delta(self, option_type, current_price, strike, days_to_expiry, iv):
        """
        Calculate an approximate delta for an option.
        This is a simplified model for simulation purposes only.
        
        Args:
            option_type: 'call' or 'put'
            current_price: Current price of the underlying
            strike: Strike price of the option
            days_to_expiry: Days to expiration
            iv: Implied volatility
            
        Returns:
            float: Approximate delta (-1.0 to 1.0)
        """
        # Moneyness ratio
        moneyness = current_price / strike
        
        # Time factor (shorter time = more extreme delta)
        time_factor = 1.0 - min(0.9, days_to_expiry / 365.0)
        
        if option_type == 'call':
            # For calls: delta approaches 1.0 as stock price increases above strike
            if moneyness >= 1.0:  # ITM
                delta = 0.5 + 0.5 * min(1.0, (moneyness - 1.0) * 10 + time_factor)
            else:  # OTM
                delta = 0.5 * max(0.0, 1.0 - (1.0 - moneyness) * 10 + time_factor)
        else:  # put
            # For puts: delta approaches -1.0 as stock price decreases below strike
            if moneyness <= 1.0:  # ITM
                delta = -0.5 - 0.5 * min(1.0, (1.0 - moneyness) * 10 + time_factor)
            else:  # OTM
                delta = -0.5 * max(0.0, 1.0 - (moneyness - 1.0) * 10 + time_factor)
        
        return delta
    
    def update_iv_rank(self):
        """
        Update the current IV rank for the underlying.
        
        In a production system, this would query historical IV data.
        For this example, we'll simulate an IV rank that changes over time.
        """
        # Simulate IV rank changes
        # In a real system, this would be calculated from historical IV data
        
        # Get a pseudo-random value based on the current time
        time_seed = int(time.time() / 300)  # Change every 5 minutes
        np.random.seed(time_seed)
        
        # Generate a random walk for IV rank
        iv_change = (np.random.random() - 0.5) * 0.1  # -0.05 to +0.05 change
        self.current_iv_rank = max(0.05, min(0.95, self.current_iv_rank + iv_change))
        
        logger.info(f"Updated IV rank for {self.symbol}: {self.current_iv_rank:.2f}")
    
    def execute_option_order(self, action, contract, quantity):
        """
        Execute an options order.
        
        In a production system, this would connect to a broker API.
        For this example, we'll simulate order execution.
        
        Args:
            action: Order action (buy_to_open, sell_to_open, buy_to_close, sell_to_close)
            contract: OptionsContract object
            quantity: Number of contracts
            
        Returns:
            str: Order ID
        """
        # Generate a unique order ID
        order_id = f"order_{int(time.time())}_{action}_{contract.symbol}_{contract.strike}_{contract.option_type}"
        
        # Log the order
        logger.info(f"Executing order: {action} {quantity} contracts of {contract}")
        logger.info(f"Contract details: Strike=${contract.strike}, Expiration={contract.expiration}, Type={contract.option_type}")
        logger.info(f"Price: Bid=${contract.bid:.2f}, Ask=${contract.ask:.2f}")
        
        # Simulate order execution
        # In a real system, this would connect to a broker API
        if action in ['buy_to_open', 'buy_to_close']:
            execution_price = contract.ask  # Buy at ask
        else:
            execution_price = contract.bid  # Sell at bid
        
        logger.info(f"Order executed at ${execution_price:.2f} per contract")
        logger.info(f"Total cost: ${(execution_price * quantity * 100):.2f}")
        
        return order_id
    
    def process_macd_signal(self):
        """
        Process the latest MACD signal and execute options trades if necessary.
        
        Returns:
            bool: True if a trade was executed, False otherwise
        """
        # Get the latest MACD signal from the quote monitor
        macd_signal = self.quote_client.get_macd_signal()
        
        if not macd_signal:
            logger.warning("Unable to get MACD signal from quote monitor")
            return False
        
        signal = macd_signal.get('signal', 0)
        position = macd_signal.get('position', 'UNKNOWN')
        
        logger.info(f"Processing MACD signal for {self.symbol}: Signal={signal}, Position={position}")
        
        # Update IV rank
        self.update_iv_rank()
        
        # Get the options chain
        options_chain = self.get_options_chain()
        
        if not options_chain:
            logger.warning("Unable to get options chain")
            return False
        
        # Get account value (in a real system, this would come from the broker API)
        account_value = 100000.0  # Simulated account value
        
        # Track if we executed a trade
        executed_trade = False
        
        # Process the signal
        if signal > 0:  # Bullish signal
            logger.info(f"Bullish signal detected for {self.symbol}")
            
            if self.trade_style == 'directional' or self.trade_style == 'combined':
                # Directional trade - buy calls
                expiration = options_chain.get_nearest_expiration(45)
                
                if expiration:
                    # Get a call option with delta around 0.60
                    call_option = options_chain.get_contract_by_delta('call', 0.60, expiration)
                    
                    if call_option:
                        # Calculate position size
                        premium = call_option.premium if call_option.premium else 5.0
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
                expiration = options_chain.get_nearest_expiration(30)
                
                if expiration:
                    # Get a put option with delta around 0.30 (absolute value)
                    put_option = options_chain.get_contract_by_delta('put', -0.30, expiration)
                    
                    if put_option:
                        # Calculate position size - more conservative for short options
                        premium = put_option.premium if put_option.premium else 2.0
                        
                        # For cash-secured puts, you would need to have cash to cover assignment
                        # For this example, we'll just use a small risk percentage
                        contracts = max(1, int((account_value * self.risk_per_trade * 0.5) / (put_option.strike * 100)))
                        
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
            
        elif signal < 0:  # Bearish signal
            logger.info(f"Bearish signal detected for {self.symbol}")
            
            if self.trade_style == 'directional' or self.trade_style == 'combined':
                # Directional trade - buy puts
                expiration = options_chain.get_nearest_expiration(45)
                
                if expiration:
                    # Get a put option with delta around 0.60 (absolute value)
                    put_option = options_chain.get_contract_by_delta('put', -0.60, expiration)
                    
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
        
        else:  # No signal or hold
            logger.info(f"No trading signal for {self.symbol}")
        
        return executed_trade
    
    def run(self, max_runtime=None):
        """
        Run the MACD options trader.
        
        Args:
            max_runtime: Maximum runtime in seconds (None for indefinite)
        """
        logger.info(f"Starting MACD Options Trader for {self.symbol}")
        
        # Wait for the quote monitor to be ready
        if not self.wait_for_quote_monitor_ready():
            logger.error("Quote monitor not ready, exiting")
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        
        try:
            while self.is_running:
                # Check if we've reached the maximum runtime
                if max_runtime and (datetime.now() - self.start_time).total_seconds() > max_runtime:
                    logger.info(f"Maximum runtime of {max_runtime} seconds reached, stopping")
                    break
                
                # Update quotes from the quote monitor
                if self.update_quotes():
                    # Process MACD signal
                    self.process_macd_signal()
                
                # Sleep for the update interval
                time.sleep(self.interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("MACD Options Trader stopped by user")
            
        except Exception as e:
            logger.error(f"Error in MACD Options Trader: {e}", exc_info=True)
            
        finally:
            self.is_running = False
            logger.info("MACD Options Trader stopped")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="MACD Options Trader Client")
    
    parser.add_argument(
        "--symbol", 
        type=str, 
        default="SPY",
        help="Stock symbol to trade (default: SPY)"
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        default=60,
        help="Update interval in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--risk", 
        type=float, 
        default=0.02,
        help="Risk percentage per trade (default: 0.02 = 2%)"
    )
    
    parser.add_argument(
        "--style", 
        type=str, 
        choices=['directional', 'income', 'combined'],
        default='directional',
        help="Trading style (default: directional)"
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
    
    parser.add_argument(
        "--extended-hours",
        action="store_true",
        help="Enable trading during extended hours"
    )
    
    parser.add_argument(
        "--runtime",
        type=int,
        default=None,
        help="Maximum runtime in seconds (default: indefinite)"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Create and run the MACD options trader
    trader = MACDOptionsTraderClient(
        symbol=args.symbol,
        interval_seconds=args.interval,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        signal_window=args.signal_window,
        risk_per_trade=args.risk,
        trade_style=args.style,
        extended_hours=args.extended_hours
    )
    
    # Run the trader
    trader.run(max_runtime=args.runtime)
