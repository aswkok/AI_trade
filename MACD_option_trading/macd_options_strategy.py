#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MACD-based Options Trading Strategy

This module extends the stock-based MACD strategy to options trading,
incorporating options-specific considerations like strike selection,
expiration dates, and options Greeks.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import the base Strategy class from the existing module
from strategies import Strategy, MACDStrategy

logger = logging.getLogger(__name__)

class OptionsStrategyBase(Strategy):
    """Base strategy class for options trading."""
    
    def __init__(self, name="BaseOptionsStrategy"):
        """Initialize the options strategy."""
        super().__init__(name=name)
        logger.info(f"Initialized {self.name} options strategy")
        
    def select_options_contract(self, data, direction, days_to_expiration=30, delta_target=0.50):
        """
        Select an appropriate options contract based on the strategy direction.
        
        Args:
            data: DataFrame with options chain data
            direction: 'bullish' or 'bearish'
            days_to_expiration: Target days to expiration (default: 30)
            delta_target: Target delta value (default: 0.50 - at the money)
            
        Returns:
            Selected options contract info (dict)
        """
        # This is a placeholder method - in a real implementation, this would query
        # an options chain API to get available contracts and filter based on criteria
        
        # Real implementation would:
        # 1. Get options chain for the symbol
        # 2. Filter for appropriate expiration date
        # 3. Select strike price based on delta target
        # 4. Filter for adequate liquidity
        
        # For now, return a mock contract
        expiration_date = datetime.now() + timedelta(days=days_to_expiration)
        
        if direction == 'bullish':
            contract_type = 'call'
        else:
            contract_type = 'put'
            
        contract = {
            'symbol': data.iloc[-1].name if isinstance(data.index[-1], str) else 'UNKNOWN',
            'type': contract_type,
            'strike': data['close'].iloc[-1], # ATM strike based on last close
            'expiration': expiration_date.strftime('%Y-%m-%d'),
            'delta': delta_target,
            'premium': 0.0,  # Would be calculated based on real options data
            'days_to_expiration': days_to_expiration
        }
        
        logger.info(f"Selected {contract_type} option contract with strike {contract['strike']} "
                   f"expiring on {contract['expiration']}")
        
        return contract
    
    def calculate_position_size(self, account_value, risk_percentage, premium):
        """
        Calculate the number of contracts to trade based on risk management rules.
        
        Args:
            account_value: Total account value
            risk_percentage: Percentage of account to risk per trade (e.g., 0.02 for 2%)
            premium: Premium per contract
            
        Returns:
            Number of contracts to trade
        """
        if premium <= 0:
            logger.error("Premium must be greater than zero")
            return 0
            
        risk_amount = account_value * risk_percentage
        contracts = max(1, int(risk_amount / premium / 100))  # Each option contract represents 100 shares
        
        logger.info(f"Position sizing: Risking ${risk_amount:.2f} allows for {contracts} contracts "
                   f"at ${premium:.2f} per share premium")
        
        return contracts


class MACDOptionsStrategy(OptionsStrategyBase):
    """
    MACD-based Options Trading Strategy.
    
    This strategy uses MACD signals to determine entry and exit points for options trades.
    It extends the base MACD strategy to incorporate options-specific considerations.
    """
    
    def __init__(self, fast_window=13, slow_window=21, signal_window=9, risk_per_trade=0.02,
                long_days_to_expiration=45, short_days_to_expiration=30,
                long_call_delta=0.60, long_put_delta=0.60,
                short_call_delta=0.30, short_put_delta=0.30,
                trade_style='directional'):
        """
        Initialize the MACD Options Strategy.
        
        Args:
            fast_window: Window for the fast EMA (default: 13)
            slow_window: Window for the slow EMA (default: 21)
            signal_window: Window for the signal line (default: 9)
            risk_per_trade: Percentage of account to risk per trade (default: 0.02 - 2%)
            long_days_to_expiration: Target DTE for long options positions (default: 45)
            short_days_to_expiration: Target DTE for short options positions (default: 30)
            long_call_delta: Target delta for long call options (default: 0.60)
            long_put_delta: Target delta for long put options (default: 0.60)
            short_call_delta: Target delta for short call options (default: 0.30)
            short_put_delta: Target delta for short put options (default: 0.30)
            trade_style: Trading style to use - 'directional', 'income', or 'combined' (default: 'directional')
        """
        super().__init__(name=f"MACD_Options_{fast_window}_{slow_window}_{signal_window}")
        
        # MACD parameters
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        
        # Risk management parameters
        self.risk_per_trade = risk_per_trade
        
        # Options contract parameters
        self.long_days_to_expiration = long_days_to_expiration
        self.short_days_to_expiration = short_days_to_expiration
        self.long_call_delta = long_call_delta
        self.long_put_delta = long_put_delta
        self.short_call_delta = short_call_delta
        self.short_put_delta = short_put_delta
        
        # Trading style (directional, income, combined)
        self.trade_style = trade_style
        
        # Current positions
        self.current_positions = []
        
        logger.info(f"Initialized MACD Options strategy with parameters: "
                   f"Fast EMA={fast_window}, Slow EMA={slow_window}, Signal={signal_window}")
        logger.info(f"Options parameters: Long DTE={long_days_to_expiration}, "
                   f"Short DTE={short_days_to_expiration}")
        logger.info(f"Trading style: {trade_style}")

    def _calculate_macd(self, data):
        """
        Calculate MACD components for the data.
        
        Args:
            data: DataFrame with price data
            
        Returns:
            DataFrame with MACD components added
        """
        # Make a copy to avoid modifying the original
        macd_data = data.copy()
        
        # Calculate MACD components
        macd_data['EMAfast'] = data['close'].ewm(span=self.fast_window, adjust=False).mean()
        macd_data['EMAslow'] = data['close'].ewm(span=self.slow_window, adjust=False).mean()
        macd_data['MACD'] = macd_data['EMAfast'] - macd_data['EMAslow']
        macd_data['Signal'] = macd_data['MACD'].ewm(span=self.signal_window, adjust=False).mean()
        macd_data['Histogram'] = macd_data['MACD'] - macd_data['Signal']
        
        # Determine if MACD is above or below signal line
        macd_data['MACD_position'] = np.where(
            macd_data['MACD'] > macd_data['Signal'], 'ABOVE', 'BELOW'
        )
        
        # Calculate crossovers
        macd_data['MACD_prev'] = macd_data['MACD'].shift(1)
        macd_data['Signal_prev'] = macd_data['Signal'].shift(1)
        
        # MACD crosses above Signal line (bullish)
        macd_data['crossover'] = (
            (macd_data['MACD'] > macd_data['Signal']) & 
            (macd_data['MACD_prev'] <= macd_data['Signal_prev'])
        )
        
        # MACD crosses below Signal line (bearish)
        macd_data['crossunder'] = (
            (macd_data['MACD'] < macd_data['Signal']) & 
            (macd_data['MACD_prev'] >= macd_data['Signal_prev'])
        )
        
        return macd_data
    
    def generate_signals(self, data, account_value=100000, iv_rank=0.50):
        """
        Generate options trading signals based on MACD signals.
        
        Args:
            data: DataFrame with OHLCV data
            account_value: Current account value for position sizing (default: 100000)
            iv_rank: Current implied volatility rank (0-1) for the underlying (default: 0.50)
            
        Returns:
            DataFrame with signals and options trade recommendations
        """
        # Calculate MACD components
        macd_data = self._calculate_macd(data)
        
        # Initialize columns for options signals
        macd_data['options_signal'] = 0
        macd_data['trade_type'] = ''
        macd_data['contract_type'] = ''
        macd_data['strike'] = 0.0
        macd_data['expiration'] = ''
        macd_data['premium'] = 0.0
        macd_data['contracts'] = 0
        
        # Process signals for each row
        for i in range(max(self.slow_window, self.fast_window) + self.signal_window, len(macd_data)):
            current_date = macd_data.index[i]
            current_price = macd_data['close'].iloc[i]
            
            # Get the current MACD state
            macd_position = macd_data['MACD_position'].iloc[i]
            crossover = macd_data['crossover'].iloc[i]
            crossunder = macd_data['crossunder'].iloc[i]
            
            # Default - no trade
            macd_data.loc[current_date, 'options_signal'] = 0
            
            # Generate options signals based on MACD signals
            if crossover:  # Bullish signal
                # Determine trade type based on trading style
                if self.trade_style == 'directional' or self.trade_style == 'combined':
                    # Directional play - buy calls
                    contract = self.select_options_contract(
                        data.iloc[:i+1], 
                        'bullish',
                        days_to_expiration=self.long_days_to_expiration,
                        delta_target=self.long_call_delta
                    )
                    
                    # Adjust premium based on IV rank
                    contract['premium'] = current_price * 0.05 * (1 + iv_rank)  # Simplified pricing model
                    
                    # Calculate position size
                    contracts = self.calculate_position_size(
                        account_value, 
                        self.risk_per_trade, 
                        contract['premium']
                    )
                    
                    # Record the signal
                    macd_data.loc[current_date, 'options_signal'] = 1
                    macd_data.loc[current_date, 'trade_type'] = 'BUY_CALL'
                    macd_data.loc[current_date, 'contract_type'] = 'call'
                    macd_data.loc[current_date, 'strike'] = contract['strike']
                    macd_data.loc[current_date, 'expiration'] = contract['expiration']
                    macd_data.loc[current_date, 'premium'] = contract['premium']
                    macd_data.loc[current_date, 'contracts'] = contracts
                    
                elif self.trade_style == 'income':
                    # Income generation - sell puts
                    contract = self.select_options_contract(
                        data.iloc[:i+1], 
                        'bullish',
                        days_to_expiration=self.short_days_to_expiration,
                        delta_target=self.short_put_delta
                    )
                    
                    # Adjust premium based on IV rank
                    contract['premium'] = current_price * 0.03 * (1 + iv_rank)  # Simplified pricing model
                    
                    # Calculate position size - more conservative for short options
                    contracts = max(1, int(self.calculate_position_size(
                        account_value,
                        self.risk_per_trade / 2,  # Half the risk for short options
                        contract['premium']
                    )))
                    
                    # Record the signal
                    macd_data.loc[current_date, 'options_signal'] = 1
                    macd_data.loc[current_date, 'trade_type'] = 'SELL_PUT'
                    macd_data.loc[current_date, 'contract_type'] = 'put'
                    macd_data.loc[current_date, 'strike'] = contract['strike']
                    macd_data.loc[current_date, 'expiration'] = contract['expiration']
                    macd_data.loc[current_date, 'premium'] = contract['premium']
                    macd_data.loc[current_date, 'contracts'] = contracts
                
            elif crossunder:  # Bearish signal
                # Determine trade type based on trading style
                if self.trade_style == 'directional' or self.trade_style == 'combined':
                    # Directional play - buy puts
                    contract = self.select_options_contract(
                        data.iloc[:i+1], 
                        'bearish',
                        days_to_expiration=self.long_days_to_expiration,
                        delta_target=self.long_put_delta
                    )
                    
                    # Adjust premium based on IV rank
                    contract['premium'] = current_price * 0.05 * (1 + iv_rank)  # Simplified pricing model
                    
                    # Calculate position size
                    contracts = self.calculate_position_size(
                        account_value, 
                        self.risk_per_trade, 
                        contract['premium']
                    )
                    
                    # Record the signal
                    macd_data.loc[current_date, 'options_signal'] = -1
                    macd_data.loc[current_date, 'trade_type'] = 'BUY_PUT'
                    macd_data.loc[current_date, 'contract_type'] = 'put'
                    macd_data.loc[current_date, 'strike'] = contract['strike']
                    macd_data.loc[current_date, 'expiration'] = contract['expiration']
                    macd_data.loc[current_date, 'premium'] = contract['premium']
                    macd_data.loc[current_date, 'contracts'] = contracts
                    
                elif self.trade_style == 'income':
                    # Income generation - sell calls
                    contract = self.select_options_contract(
                        data.iloc[:i+1], 
                        'bearish',
                        days_to_expiration=self.short_days_to_expiration,
                        delta_target=self.short_call_delta
                    )
                    
                    # Adjust premium based on IV rank
                    contract['premium'] = current_price * 0.03 * (1 + iv_rank)  # Simplified pricing model
                    
                    # Calculate position size - more conservative for short options
                    contracts = max(1, int(self.calculate_position_size(
                        account_value,
                        self.risk_per_trade / 2,  # Half the risk for short options
                        contract['premium']
                    )))
                    
                    # Record the signal
                    macd_data.loc[current_date, 'options_signal'] = -1
                    macd_data.loc[current_date, 'trade_type'] = 'SELL_CALL'
                    macd_data.loc[current_date, 'contract_type'] = 'call'
                    macd_data.loc[current_date, 'strike'] = contract['strike']
                    macd_data.loc[current_date, 'expiration'] = contract['expiration']
                    macd_data.loc[current_date, 'premium'] = contract['premium']
                    macd_data.loc[current_date, 'contracts'] = contracts
            
            # For the combined strategy, add a second trade if there's a signal
            if self.trade_style == 'combined' and (crossover or crossunder):
                if crossover:  # Bullish combined strategy - also sell puts for income
                    contract = self.select_options_contract(
                        data.iloc[:i+1], 
                        'bullish',
                        days_to_expiration=self.short_days_to_expiration,
                        delta_target=self.short_put_delta
                    )
                    
                    # Add to current positions
                    self.current_positions.append({
                        'date': current_date,
                        'trade_type': 'SELL_PUT',
                        'contract_type': 'put',
                        'strike': contract['strike'],
                        'expiration': contract['expiration'],
                        'premium': current_price * 0.03 * (1 + iv_rank),
                        'contracts': max(1, int(self.calculate_position_size(
                            account_value,
                            self.risk_per_trade / 4,  # Quarter risk for second leg
                            contract['premium']
                        )))
                    })
                
                elif crossunder:  # Bearish combined strategy - also sell calls for income
                    contract = self.select_options_contract(
                        data.iloc[:i+1], 
                        'bearish',
                        days_to_expiration=self.short_days_to_expiration,
                        delta_target=self.short_call_delta
                    )
                    
                    # Add to current positions
                    self.current_positions.append({
                        'date': current_date,
                        'trade_type': 'SELL_CALL',
                        'contract_type': 'call',
                        'strike': contract['strike'],
                        'expiration': contract['expiration'],
                        'premium': current_price * 0.03 * (1 + iv_rank),
                        'contracts': max(1, int(self.calculate_position_size(
                            account_value,
                            self.risk_per_trade / 4,  # Quarter risk for second leg
                            contract['premium']
                        )))
                    })
            
            # Manage existing positions
            for position in list(self.current_positions):
                # Check for exit signals
                if position['trade_type'] == 'BUY_CALL' and crossunder:
                    # Exit long calls on bearish signal
                    logger.info(f"Exit signal for long call position at {current_date}")
                    self.current_positions.remove(position)
                    
                elif position['trade_type'] == 'BUY_PUT' and crossover:
                    # Exit long puts on bullish signal
                    logger.info(f"Exit signal for long put position at {current_date}")
                    self.current_positions.remove(position)
                    
                elif position['trade_type'] in ['SELL_CALL', 'SELL_PUT']:
                    # Check expiration for short positions - roll if approaching expiration
                    entry_date = position['date']
                    days_held = (current_date - entry_date).days if isinstance(entry_date, pd.Timestamp) else 0
                    
                    if days_held > (self.short_days_to_expiration - 21):  # Roll when 21 days to expiration
                        logger.info(f"Rolling short option position at {current_date} - approaching expiration")
                        
                        # Remove the old position
                        self.current_positions.remove(position)
                        
                        # Create new position (roll to new expiration)
                        direction = 'bullish' if position['trade_type'] == 'SELL_PUT' else 'bearish'
                        contract = self.select_options_contract(
                            data.iloc[:i+1], 
                            direction,
                            days_to_expiration=self.short_days_to_expiration,
                            delta_target=self.short_put_delta if position['trade_type'] == 'SELL_PUT' else self.short_call_delta
                        )
                        
                        # Add new position
                        self.current_positions.append({
                            'date': current_date,
                            'trade_type': position['trade_type'],
                            'contract_type': position['contract_type'],
                            'strike': contract['strike'],
                            'expiration': contract['expiration'],
                            'premium': current_price * 0.03 * (1 + iv_rank),
                            'contracts': position['contracts']
                        })
        
        # Clean up and return the results
        return macd_data[['close', 'MACD', 'Signal', 'Histogram', 'MACD_position', 
                         'crossover', 'crossunder', 'options_signal', 'trade_type', 
                         'contract_type', 'strike', 'expiration', 'premium', 'contracts']]
    
    def execute_trade(self, trade, broker_api):
        """
        Execute an options trade using the broker API.
        
        Args:
            trade: Dictionary with trade details
            broker_api: Broker API client for executing trades
            
        Returns:
            Trade execution result
        """
        # This is a placeholder method to be implemented with a real broker API
        logger.info(f"Executing {trade['trade_type']} for {trade['contracts']} "
                   f"contracts of {trade['contract_type']} options with strike {trade['strike']} "
                   f"expiring on {trade['expiration']}")
        
        # Placeholder for actual execution logic
        result = {
            'success': True,
            'order_id': '12345',
            'message': 'Order simulated',
            'filled_price': trade['premium'],
            'timestamp': datetime.now()
        }
        
        return result
    
    def get_option_chain(self, symbol, broker_api):
        """
        Get the options chain for a symbol using the broker API.
        
        Args:
            symbol: The underlying stock symbol
            broker_api: Broker API client for fetching options data
            
        Returns:
            DataFrame with options chain data
        """
        # This is a placeholder method to be implemented with a real broker API
        logger.info(f"Fetching options chain for {symbol}")
        
        # In a real implementation, this would call the broker API
        # to get available options contracts for the symbol
        
        # Placeholder return value
        return pd.DataFrame()
    
    def calculate_iv_rank(self, symbol, broker_api, lookback_days=252):
        """
        Calculate the implied volatility rank for a symbol.
        
        Args:
            symbol: The underlying stock symbol
            broker_api: Broker API client for fetching volatility data
            lookback_days: Number of days to look back for IV rank calculation
            
        Returns:
            IV rank (0-1)
        """
        # This is a placeholder method to be implemented with a real broker API
        logger.info(f"Calculating IV rank for {symbol}")
        
        # In a real implementation, this would:
        # 1. Get historical IV data for the lookback period
        # 2. Calculate current IV percentile within that range
        
        # Placeholder return value - simulating a moderate IV rank
        return 0.50


# Example usage and testing
if __name__ == "__main__":
    # Create sample data for testing
    import pandas as pd
    from datetime import datetime, timedelta
    import numpy as np
    
    # Create sample price data
    dates = [datetime.now() - timedelta(days=i) for i in range(100, 0, -1)]
    data = pd.DataFrame({
        'open': np.random.normal(100, 5, 100),
        'high': np.random.normal(105, 5, 100),
        'low': np.random.normal(95, 5, 100),
        'close': np.random.normal(100, 5, 100),
        'volume': np.random.normal(1000000, 200000, 100)
    }, index=dates)
    
    # Create the strategy instance
    strategy = MACDOptionsStrategy(
        fast_window=13,
        slow_window=21,
        signal_window=9,
        risk_per_trade=0.02,
        trade_style='directional'
    )
    
    # Generate signals
    signals = strategy.generate_signals(data)
    
    # Print trade signals
    trades = signals[signals['options_signal'] != 0]
    print(f"Generated {len(trades)} trade signals:")
    for idx, trade in trades.iterrows():
        print(f"Date: {idx.strftime('%Y-%m-%d')}, "
              f"Type: {trade['trade_type']}, "
              f"Strike: {trade['strike']:.2f}, "
              f"Contracts: {trade['contracts']}, "
              f"Premium: ${trade['premium']:.2f}")