"""
Options trading module for the MACD Options Trading System.

This module provides classes and utilities for options trading, including:
- OptionsContract: Represents an individual options contract
- OptionsChain: Represents a collection of options contracts for a symbol
- OptionsStrategyBase: Base class for options trading strategies
- MACDOptionsStrategy: MACD-based options trading strategy
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

# Configure logging
logger = logging.getLogger(__name__)


class OptionsStrategyBase(ABC):
    """
    Base class for options trading strategies.
    
    This abstract class defines the interface that all options strategies must implement.
    """
    
    @abstractmethod
    def generate_entry_signal(self, data):
        """
        Generate an entry signal based on the strategy.
        
        Args:
            data: Market data to analyze
            
        Returns:
            dict: Signal information
        """
        pass
        
    @abstractmethod
    def generate_exit_signal(self, data, position):
        """
        Generate an exit signal based on the strategy.
        
        Args:
            data: Market data to analyze
            position: Current position information
            
        Returns:
            dict: Signal information
        """
        pass
        
    @abstractmethod
    def select_strike(self, data, signal_type):
        """
        Select the appropriate strike price based on the signal.
        
        Args:
            data: Market data to analyze
            signal_type: Type of signal (e.g., 'buy', 'sell')
            
        Returns:
            float: Selected strike price
        """
        pass
        
    @abstractmethod
    def select_expiration(self, data, signal_type):
        """
        Select the appropriate expiration date based on the signal.
        
        Args:
            data: Market data to analyze
            signal_type: Type of signal (e.g., 'buy', 'sell')
            
        Returns:
            str: Selected expiration date
        """
        pass


class OptionsContract:
    """Class representing an options contract."""
    
    def __init__(self, underlying, contract_type, strike, expiration, premium=None, delta=None, gamma=None, theta=None, vega=None):
        """
        Initialize an options contract.
        
        Args:
            underlying: Underlying stock symbol
            contract_type: 'call' or 'put'
            strike: Strike price
            expiration: Expiration date (YYYY-MM-DD)
            premium: Contract premium (optional)
            delta: Option delta (optional)
            gamma: Option gamma (optional)
            theta: Option theta (optional)
            vega: Option vega (optional)
        """
        self.underlying = underlying
        self.contract_type = contract_type
        self.strike = strike
        self.expiration = expiration
        self.premium = premium
        
        # Greeks
        self.delta = delta
        self.gamma = gamma
        self.theta = theta
        self.vega = vega
        
        # Calculate option symbol (OCC format)
        self.symbol = self._build_option_symbol()
        
    def _build_option_symbol(self):
        """
        Build an option symbol in OCC format: XYZ YYMMDD C/P STRIKE
        """
        # Parse expiration date components
        if isinstance(self.expiration, str):
            exp_date = datetime.strptime(self.expiration, '%Y-%m-%d')
        elif isinstance(self.expiration, datetime):
            exp_date = self.expiration
        else:
            raise ValueError(f"Unsupported expiration date format: {self.expiration}")
            
        # Format expiration in YYMMDD
        exp_format = exp_date.strftime('%y%m%d')
        
        # Format strike price - multiply by 1000 and remove decimal
        strike_format = str(int(self.strike * 1000)).zfill(8)
        
        # Contract type code
        type_code = 'C' if self.contract_type.upper() == 'CALL' else 'P'
        
        # Combine to build OCC symbol
        return f"{self.underlying}{exp_format}{type_code}{strike_format}"
    
    def days_to_expiration(self):
        """Calculate days to expiration from now."""
        if isinstance(self.expiration, str):
            exp_date = datetime.strptime(self.expiration, '%Y-%m-%d')
        elif isinstance(self.expiration, datetime):
            exp_date = self.expiration
        else:
            return 0
            
        now = datetime.now()
        delta = exp_date - now
        return max(0, delta.days)
    
    def __str__(self):
        """String representation of the contract."""
        return (f"{self.underlying} {self.expiration} {self.contract_type.upper()} {self.strike:.2f} "
                f"[DTE: {self.days_to_expiration()}]")


class OptionsChain:
    """Class representing an options chain for a symbol."""
    
    def __init__(self, underlying, expiration_dates=None, calls=None, puts=None):
        """
        Initialize an options chain.
        
        Args:
            underlying: Underlying stock symbol
            expiration_dates: List of available expiration dates
            calls: DataFrame with call options data
            puts: DataFrame with put options data
        """
        self.underlying = underlying
        self.expiration_dates = expiration_dates or []
        self.calls = calls if calls is not None else pd.DataFrame()
        self.puts = puts if puts is not None else pd.DataFrame()
        
    def get_nearest_expiration(self, target_days):
        """
        Get the expiration date nearest to the target days to expiration.
        
        Args:
            target_days: Target days to expiration
            
        Returns:
            Nearest expiration date
        """
        if not self.expiration_dates:
            return None
            
        # Convert dates to datetime objects if they're strings
        exp_dates = []
        for exp in self.expiration_dates:
            if isinstance(exp, str):
                exp_dates.append(datetime.strptime(exp, '%Y-%m-%d'))
            else:
                exp_dates.append(exp)
                
        # Calculate days to expiration for each date
        now = datetime.now()
        days_to_exp = [(exp - now).days for exp in exp_dates]
        
        # Find the nearest expiration to target_days
        nearest_idx = min(range(len(days_to_exp)), key=lambda i: abs(days_to_exp[i] - target_days))
        
        return self.expiration_dates[nearest_idx]
    
    def get_contract_by_delta(self, contract_type, target_delta, expiration=None):
        """
        Get the contract with delta closest to the target delta.
        
        Args:
            contract_type: 'call' or 'put'
            target_delta: Target delta value (positive value, e.g., 0.50)
            expiration: Specific expiration date (optional)
            
        Returns:
            OptionsContract object
        """
        # Select the appropriate chain
        if contract_type.lower() == 'call':
            chain = self.calls
        else:
            chain = self.puts
            
        # Check if DataFrame is empty using the .empty property explicitly
        if hasattr(chain, 'empty') and chain.empty:
            logger.warning(f"No {contract_type} options available for {self.underlying}")
            return None
            
        # Filter by expiration if provided
        if expiration:
            chain = chain[chain['expiration'] == expiration]
            
            # Check if filtered DataFrame is empty
            if hasattr(chain, 'empty') and chain.empty:
                logger.warning(f"No {contract_type} options available for {self.underlying} with expiration {expiration}")
                return None
                
        # Find the strike with delta closest to target
        # Note: Put deltas are negative, so we take the absolute value for comparison
        if 'delta' in chain.columns:
            if contract_type.lower() == 'put':
                chain['delta_diff'] = abs(abs(chain['delta']) - target_delta)
            else:
                chain['delta_diff'] = abs(chain['delta'] - target_delta)
                
            # Get the row with minimum delta difference
            closest = chain.loc[chain['delta_diff'].idxmin()]
            
        else:
            # If no delta information available, use ATM as proxy
            if 'strike' in chain.columns and 'underlying_price' in chain.columns:
                # Find closest strike to current price
                chain['strike_diff'] = abs(chain['strike'] - chain['underlying_price'])
                closest = chain.loc[chain['strike_diff'].idxmin()]
            else:
                logger.warning(f"Insufficient data to select contract by delta for {self.underlying}")
                return None
                
        # Create and return the contract
        return OptionsContract(
            underlying=self.underlying,
            contract_type=contract_type,
            strike=closest['strike'],
            expiration=closest['expiration'] if 'expiration' in closest else expiration,
            premium=closest['ask'] if 'ask' in closest else None,
            delta=closest['delta'] if 'delta' in closest else None,
            gamma=closest['gamma'] if 'gamma' in closest else None,
            theta=closest['theta'] if 'theta' in closest else None,
            vega=closest['vega'] if 'vega' in closest else None
        )

    def get_contract_by_strike(self, contract_type, strike, expiration=None):
        """
        Get the contract with the specified strike price.
        
        Args:
            contract_type: 'call' or 'put'
            strike: Target strike price
            expiration: Specific expiration date (optional)
            
        Returns:
            OptionsContract object
        """
        # Select the appropriate chain
        if contract_type.lower() == 'call':
            chain = self.calls
        else:
            chain = self.puts
            
        # Check if DataFrame is empty using the .empty property explicitly
        if hasattr(chain, 'empty') and chain.empty:
            logger.warning(f"No {contract_type} options available for {self.underlying}")
            return None
            
        # Filter by expiration if provided
        if expiration:
            chain = chain[chain['expiration'] == expiration]
            
            # Check if filtered DataFrame is empty
            if hasattr(chain, 'empty') and chain.empty:
                logger.warning(f"No {contract_type} options available for {self.underlying} with expiration {expiration}")
                return None
                
        # Find the strike closest to target
        if 'strike' in chain.columns:
            chain['strike_diff'] = abs(chain['strike'] - strike)
            closest = chain.loc[chain['strike_diff'].idxmin()]
        else:
            logger.warning(f"No strike data available for {self.underlying} {contract_type} options")
            return None
                
        # Create and return the contract
        return OptionsContract(
            underlying=self.underlying,
            contract_type=contract_type,
            strike=closest['strike'],
            expiration=closest['expiration'] if 'expiration' in closest else expiration,
            premium=closest['ask'] if 'ask' in closest else None,
            delta=closest['delta'] if 'delta' in closest else None,
            gamma=closest['gamma'] if 'gamma' in closest else None,
            theta=closest['theta'] if 'theta' in closest else None,
            vega=closest['vega'] if 'vega' in closest else None
        )



class MACDOptionsStrategy(OptionsStrategyBase):
    """
    MACD-based Options Trading Strategy.
    
    This strategy uses MACD signals to determine entry and exit points for options trades.
    It extends the base MACD strategy to incorporate options-specific considerations.
    """
    
    def __init__(self, fast_window=13, slow_window=21, signal_window=9, risk_per_trade=0.02,
                long_days_to_expiration=45, short_days_to_expiration=30,
                long_delta_target=0.60, short_delta_target=0.30):
        """
        Initialize the MACD Options Strategy.
        
        Args:
            fast_window: Fast EMA window
            slow_window: Slow EMA window
            signal_window: Signal line window
            risk_per_trade: Risk per trade as a fraction of account value
            long_days_to_expiration: Target days to expiration for long options
            short_days_to_expiration: Target days to expiration for short options
            long_delta_target: Target delta for long options
            short_delta_target: Target delta for short options
        """
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.risk_per_trade = risk_per_trade
        
        # Options-specific parameters
        self.long_days_to_expiration = long_days_to_expiration
        self.short_days_to_expiration = short_days_to_expiration
        self.long_delta_target = long_delta_target
        self.short_delta_target = short_delta_target
        
        # Initialize quote monitor reference
        self.quote_monitor = None
        
    def set_quote_monitor(self, quote_monitor):
        """
        Set the quote monitor for this strategy.
        
        Args:
            quote_monitor: QuoteMonitor instance to use for market data
        """
        self.quote_monitor = quote_monitor
        
    def generate_entry_signal(self, data):
        """
        Generate an entry signal based on MACD crossovers.
        
        Args:
            data: DataFrame with MACD data
            
        Returns:
            dict: Signal information
        """
        # Check if we have enough data
        if len(data) < self.slow_window + self.signal_window:
            return {'signal': 'WAIT', 'reason': 'Insufficient data'}
            
        # Get the latest MACD values
        latest = data.iloc[-1]
        
        # Check for MACD crossovers
        if 'crossover' in latest and latest['crossover']:
            return {
                'signal': 'BUY',
                'reason': 'MACD crossed above signal line',
                'strength': abs(latest['MACD'] - latest['Signal']),
                'contract_type': 'call',
                'delta_target': self.long_delta_target,
                'days_to_expiration': self.long_days_to_expiration
            }
            
        elif 'crossunder' in latest and latest['crossunder']:
            return {
                'signal': 'SELL',
                'reason': 'MACD crossed below signal line',
                'strength': abs(latest['MACD'] - latest['Signal']),
                'contract_type': 'put',
                'delta_target': self.long_delta_target,
                'days_to_expiration': self.long_days_to_expiration
            }
            
        # No signal
        return {'signal': 'WAIT', 'reason': 'No MACD crossover detected'}
        
    def generate_exit_signal(self, data, position):
        """
        Generate an exit signal based on MACD and position.
        
        Args:
            data: DataFrame with MACD data
            position: Current position information
            
        Returns:
            dict: Signal information
        """
        # Check if we have a position
        if not position:
            return {'signal': 'NONE', 'reason': 'No position to exit'}
            
        # Get the latest MACD values
        latest = data.iloc[-1]
        
        # Check position type
        if position['type'] == 'long_call':
            # Exit long call on MACD crossunder
            if 'crossunder' in latest and latest['crossunder']:
                return {
                    'signal': 'SELL_TO_CLOSE',
                    'reason': 'MACD crossed below signal line',
                    'strength': abs(latest['MACD'] - latest['Signal'])
                }
                
        elif position['type'] == 'long_put':
            # Exit long put on MACD crossover
            if 'crossover' in latest and latest['crossover']:
                return {
                    'signal': 'SELL_TO_CLOSE',
                    'reason': 'MACD crossed above signal line',
                    'strength': abs(latest['MACD'] - latest['Signal'])
                }
                
        elif position['type'] == 'short_call':
            # Exit short call on MACD crossunder
            if 'crossunder' in latest and latest['crossunder']:
                return {
                    'signal': 'BUY_TO_CLOSE',
                    'reason': 'MACD crossed below signal line',
                    'strength': abs(latest['MACD'] - latest['Signal'])
                }
                
        elif position['type'] == 'short_put':
            # Exit short put on MACD crossover
            if 'crossover' in latest and latest['crossover']:
                return {
                    'signal': 'BUY_TO_CLOSE',
                    'reason': 'MACD crossed above signal line',
                    'strength': abs(latest['MACD'] - latest['Signal'])
                }
                
        # Check time decay - exit if less than 7 days to expiration
        if 'expiration' in position:
            exp_date = datetime.strptime(position['expiration'], '%Y-%m-%d')
            days_left = (exp_date - datetime.now()).days
            
            if days_left <= 7:
                action = 'SELL_TO_CLOSE' if position['type'].startswith('long') else 'BUY_TO_CLOSE'
                return {
                    'signal': action,
                    'reason': f'Time decay risk (only {days_left} days to expiration)'
                }
                
        # No exit signal
        return {'signal': 'HOLD', 'reason': 'No exit criteria met'}
        
    def select_strike(self, data, signal_type):
        """
        Select the appropriate strike price based on the signal.
        
        Args:
            data: Market data including current price
            signal_type: Type of signal (e.g., 'BUY', 'SELL')
            
        Returns:
            float: Selected strike price
        """
        # Get the current price
        current_price = data['price']
        
        # For simplicity, select strikes based on signal type
        if signal_type == 'BUY':
            # For calls, select slightly OTM strike
            return round(current_price * 1.05, 1)
        elif signal_type == 'SELL':
            # For puts, select slightly OTM strike
            return round(current_price * 0.95, 1)
        else:
            # Default to ATM
            return round(current_price, 1)
            
    def select_expiration(self, data, signal_type):
        """
        Select the appropriate expiration date based on the signal.
        
        Args:
            data: Market data
            signal_type: Type of signal (e.g., 'BUY', 'SELL')
            
        Returns:
            str: Selected expiration date
        """
        # Get today's date
        today = datetime.now()
        
        # Select expiration based on signal type
        if signal_type in ['BUY', 'SELL']:
            # For directional trades, use longer-dated options
            target_date = today + timedelta(days=self.long_days_to_expiration)
        else:
            # For income trades, use shorter-dated options
            target_date = today + timedelta(days=self.short_days_to_expiration)
            
        # Format as YYYY-MM-DD
        return target_date.strftime('%Y-%m-%d')
