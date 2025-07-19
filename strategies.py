#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Trading strategies module for the Alpaca-based quantitative trading system.
This module contains various trading strategies that can be used with the system.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Strategy:
    """Base strategy class that all strategies should inherit from."""
    
    def __init__(self, name="BaseStrategy"):
        """Initialize the strategy."""
        self.name = name
        logger.info(f"Initialized {self.name} strategy")
    
    def generate_signals(self, data):
        """
        Generate trading signals from the data.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            DataFrame with signals column added
        """
        raise NotImplementedError("Subclasses must implement generate_signals method")


class MovingAverageCrossover(Strategy):
    """
    Moving Average Crossover strategy.
    
    Generates buy signals when the short-term moving average crosses above
    the long-term moving average, and sell signals when it crosses below.
    """
    
    def __init__(self, short_window=20, long_window=50):
        """
        Initialize the strategy with the specified windows.
        
        Args:
            short_window: Window for the short-term moving average
            long_window: Window for the long-term moving average
        """
        super().__init__(name=f"MA_Crossover_{short_window}_{long_window}")
        self.short_window = short_window
        self.long_window = long_window
        logger.info(f"Initialized MA Crossover strategy with windows {short_window}/{long_window}")
    
    def generate_signals(self, data):
        """
        Generate trading signals based on moving average crossovers.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            DataFrame with signals column added (1 for buy, -1 for sell, 0 for hold)
        """
        # Make a copy of the data to avoid modifying the original
        signals = data.copy()
        
        # Create the short and long moving averages
        signals[f'SMA{self.short_window}'] = signals['close'].rolling(window=self.short_window).mean()
        signals[f'SMA{self.long_window}'] = signals['close'].rolling(window=self.long_window).mean()
        
        # Create signals
        signals['signal'] = 0.0
        
        # Generate signals
        signals['signal'] = np.where(
            signals[f'SMA{self.short_window}'] > signals[f'SMA{self.long_window}'], 1.0, 0.0
        )
        
        # Generate trading orders
        signals['position'] = signals['signal'].diff()
        
        return signals


class RSIStrategy(Strategy):
    """
    Relative Strength Index (RSI) strategy.
    
    Generates buy signals when RSI falls below the oversold level and then rises back above it,
    and sell signals when RSI rises above the overbought level and then falls back below it.
    """
    
    def __init__(self, window=14, oversold=30, overbought=70):
        """
        Initialize the strategy with the specified parameters.
        
        Args:
            window: Window for RSI calculation
            oversold: Oversold threshold
            overbought: Overbought threshold
        """
        super().__init__(name=f"RSI_{window}_{oversold}_{overbought}")
        self.window = window
        self.oversold = oversold
        self.overbought = overbought
        logger.info(f"Initialized RSI strategy with window {window}, oversold {oversold}, overbought {overbought}")
    
    def _calculate_rsi(self, data):
        """
        Calculate the RSI for the data.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            Series with RSI values
        """
        # Calculate price changes
        delta = data['close'].diff()
        
        # Separate gains and losses
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Calculate average gain and loss
        avg_gain = gain.rolling(window=self.window).mean()
        avg_loss = loss.rolling(window=self.window).mean()
        
        # Calculate relative strength
        rs = avg_gain / avg_loss
        
        # Calculate RSI
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def generate_signals(self, data):
        """
        Generate trading signals based on RSI.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            DataFrame with signals column added (1 for buy, -1 for sell, 0 for hold)
        """
        # Make a copy of the data to avoid modifying the original
        signals = data.copy()
        
        # Calculate RSI
        signals['RSI'] = self._calculate_rsi(signals)
        
        # Create signals
        signals['signal'] = 0.0
        signals['oversold'] = signals['RSI'] < self.oversold
        signals['overbought'] = signals['RSI'] > self.overbought
        
        # Generate buy signals when RSI crosses above oversold level
        oversold_crossover = (signals['oversold'].shift(1) == True) & (signals['oversold'] == False)
        signals.loc[oversold_crossover, 'signal'] = 1.0
        
        # Generate sell signals when RSI crosses below overbought level
        overbought_crossover = (signals['overbought'].shift(1) == True) & (signals['overbought'] == False)
        signals.loc[overbought_crossover, 'signal'] = -1.0
        
        # Generate trading orders
        signals['position'] = signals['signal']
        
        return signals


class BollingerBandsStrategy(Strategy):
    """
    Bollinger Bands strategy.
    
    Generates buy signals when price touches the lower band and sell signals when it touches the upper band.
    """
    
    def __init__(self, window=20, num_std=2):
        """
        Initialize the strategy with the specified parameters.
        
        Args:
            window: Window for moving average calculation
            num_std: Number of standard deviations for the bands
        """
        super().__init__(name=f"BollingerBands_{window}_{num_std}")
        self.window = window
        self.num_std = num_std
        logger.info(f"Initialized Bollinger Bands strategy with window {window}, std {num_std}")
    
    def generate_signals(self, data):
        """
        Generate trading signals based on Bollinger Bands.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            DataFrame with signals column added (1 for buy, -1 for sell, 0 for hold)
        """
        # Make a copy of the data to avoid modifying the original
        signals = data.copy()
        
        # Calculate Bollinger Bands
        signals['SMA'] = signals['close'].rolling(window=self.window).mean()
        signals['STD'] = signals['close'].rolling(window=self.window).std()
        signals['UpperBand'] = signals['SMA'] + (signals['STD'] * self.num_std)
        signals['LowerBand'] = signals['SMA'] - (signals['STD'] * self.num_std)
        
        # Create signals
        signals['signal'] = 0.0
        
        # Generate buy signals when price touches the lower band
        signals.loc[signals['close'] <= signals['LowerBand'], 'signal'] = 1.0
        
        # Generate sell signals when price touches the upper band
        signals.loc[signals['close'] >= signals['UpperBand'], 'signal'] = -1.0
        
        # Generate trading orders
        signals['position'] = signals['signal']
        
        return signals


class MACDStrategy(Strategy):
    """
    Enhanced MACD-based Trading Strategy with real-time data support.
    
    Rules:
    1. Buy when the MACD line crosses above the Signal line (crossover).
    2. Sell when the MACD line crosses below the Signal line (crossunder).
    3. If a crossover turns into a crossunder:
       - Sell all previously bought shares
       - Short an additional set of stocks
    4. If a crossunder turns into a crossover:
       - Buy to cover all shorts
       - Buy an additional set of stocks
    5. Option to use real-time quote data from QuoteMonitor
    """
    
    def __init__(self, fast_window=13, slow_window=21, signal_window=9, shares_per_trade=100):
        """
        Initialize the strategy with the specified parameters.
        
        Args:
            fast_window: Window for the fast EMA
            slow_window: Window for the slow EMA
            signal_window: Window for the signal line
            shares_per_trade: Number of shares to trade per signal (default: 100)
        """
        super().__init__(name=f"MACD_{fast_window}_{slow_window}_{signal_window}")
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.shares_per_trade = shares_per_trade
        self.quote_monitor = None  # Will be set if using real-time data
        logger.info(f"Initialized MACD strategy with windows {fast_window}/{slow_window}/{signal_window}")
    
    def set_quote_monitor(self, quote_monitor):
        """
        Set the quote monitor for real-time data.
        
        Args:
            quote_monitor: QuoteMonitor instance for real-time data
        """
        self.quote_monitor = quote_monitor
        logger.info(f"QuoteMonitor set for real-time MACD strategy")
    
    def generate_signals(self, data, symbol=None, use_realtime=False):
        """
        Generate trading signals based on MACD crossovers.
        
        Args:
            data: DataFrame with OHLCV data
            symbol: The stock symbol being analyzed (optional)
            use_realtime: Whether to use real-time data from quote_monitor (default: False)
            
        Returns:
            DataFrame with signals
        """
        # If using real-time data and we have a quote monitor
        if use_realtime and self.quote_monitor and not self.quote_monitor.quotes_df.empty:
            logger.info("Using real-time quote data for MACD calculation")
            signals = self.quote_monitor.quotes_df.copy()
            
            # Calculate MACD components using mid prices from quote monitor
            if 'mid' in signals.columns:
                signals['EMAfast'] = signals['mid'].ewm(span=self.fast_window, adjust=False).mean()
                signals['EMAslow'] = signals['mid'].ewm(span=self.slow_window, adjust=False).mean()
                signals['MACD'] = signals['EMAfast'] - signals['EMAslow']
                signals['Signal'] = signals['MACD'].ewm(span=self.signal_window, adjust=False).mean()
            else:
                logger.warning("No 'mid' column found in quote data, falling back to historical data")
                return self._generate_signals_historical(data, symbol)
        else:
            # Fall back to historical data
            return self._generate_signals_historical(data, symbol)
            
        # Rest of processing remains the same as historical method
        return self._process_macd_signals(signals, symbol)
    
    def _generate_signals_historical(self, data, symbol=None):
        """
        Generate signals using historical OHLCV data.
        
        Args:
            data: DataFrame with OHLCV data
            symbol: The stock symbol being analyzed (optional)
            
        Returns:
            DataFrame with signals
        """
        # Create a copy of the data
        signals = data.copy()
        
        # Calculate required warmup period for accurate MACD
        warmup_period = max(self.slow_window * 3, self.fast_window * 3) + self.signal_window
        
        # Check if we have enough data for accurate MACD calculation
        if len(signals) < warmup_period:
            logger.warning(f"Not enough data for reliable MACD calculation. Have {len(signals)} bars, need at least {warmup_period} bars.")
        else:
            logger.info(f"Sufficient data ({len(signals)} bars) for reliable MACD calculation (minimum: {warmup_period} bars).")
        
        # Calculate MACD components using standard method
        signals['EMAfast'] = signals['close'].ewm(span=self.fast_window, adjust=False).mean()
        signals['EMAslow'] = signals['close'].ewm(span=self.slow_window, adjust=False).mean()
        signals['MACD'] = signals['EMAfast'] - signals['EMAslow']
        signals['Signal'] = signals['MACD'].ewm(span=self.signal_window, adjust=False).mean()
        
        # Process the signals
        return self._process_macd_signals(signals, symbol)
    
    def _process_macd_signals(self, signals, symbol=None):
        """
        Process MACD signals for trading decisions.
        
        Args:
            signals: DataFrame with MACD components calculated
            symbol: The stock symbol being analyzed (optional)
            
        Returns:
            DataFrame with trading signals
        """
        # Add debug logging to see the actual values
        if len(signals) > 0:
            latest = signals.iloc[-1]
            logger.info(f"MACD Calculation - Fast EMA: {latest.get('EMAfast', 0):.4f}, Slow EMA: {latest.get('EMAslow', 0):.4f}")
            logger.info(f"MACD Value: {latest.get('MACD', 0):.6f}, Signal Line: {latest.get('Signal', 0):.6f}")
            logger.info(f"MACD Position: {'ABOVE' if latest.get('MACD', 0) > latest.get('Signal', 0) else 'BELOW'} signal line")
            logger.info(f"MACD Histogram: {(latest.get('MACD', 0) - latest.get('Signal', 0)):.6f}")
        
        # Calculate crossovers
        signals['MACD_prev'] = signals['MACD'].shift(1)
        signals['Signal_prev'] = signals['Signal'].shift(1)
        
        # MACD crosses above Signal line (buy signal)
        macd_crossover = (signals['MACD'] > signals['Signal']) & (signals['MACD_prev'] <= signals['Signal_prev'])
        
        # MACD crosses below Signal line (sell signal)
        macd_crossunder = (signals['MACD'] < signals['Signal']) & (signals['MACD_prev'] >= signals['Signal_prev'])
        
        # Current MACD position (above or below signal line)
        macd_above_signal = signals['MACD'] > signals['Signal']
        
        # Initialize columns
        signals['signal'] = 0.0
        signals['position'] = 0.0
        signals['position_type'] = ''
        signals['shares'] = 0
        signals['action'] = ''
        signals['macd_position'] = ''
        
        # Process signals sequentially to track position transitions
        for i in range(1, len(signals)):
            current_date = signals.index[i]
            
            # Determine current MACD position
            if macd_above_signal.iloc[i]:
                current_macd_position = 'ABOVE'
            else:
                current_macd_position = 'BELOW'
            
            signals.loc[current_date, 'macd_position'] = current_macd_position
            
            # Get previous position type and MACD position
            if i > 1:
                prev_position_type = signals.loc[signals.index[i-1], 'position_type']
                prev_macd_position = signals.loc[signals.index[i-1], 'macd_position']
            else:
                prev_position_type = ''
                prev_macd_position = ''
            
            # Handle crossover (MACD crosses above Signal line)
            if macd_crossover.iloc[i]:
                signals.loc[current_date, 'signal'] = 1.0  # Buy signal
                signals.loc[current_date, 'position'] = 1.0  # Long position
                signals.loc[current_date, 'position_type'] = 'LONG'
                signals.loc[current_date, 'shares'] = self.shares_per_trade
                
                # Check for transition from SHORT to LONG
                if prev_position_type == 'SHORT':
                    # Rule 5: If a crossunder turns into a crossover:
                    # - Buy to cover all shorts
                    # - Buy an additional 100 stocks
                    signals.loc[current_date, 'action'] = 'COVER_AND_BUY'
                elif prev_position_type == '':
                    # Rule 1: When no stock holding, buy 100 stocks on crossover
                    signals.loc[current_date, 'action'] = 'BUY'
                else:
                    # Already in a LONG position, no action needed
                    signals.loc[current_date, 'action'] = ''
                    
            # Handle crossunder (MACD crosses below Signal line)
            elif macd_crossunder.iloc[i]:
                signals.loc[current_date, 'signal'] = -1.0  # Sell signal
                signals.loc[current_date, 'position'] = -1.0  # Short position
                signals.loc[current_date, 'position_type'] = 'SHORT'
                signals.loc[current_date, 'shares'] = self.shares_per_trade
                
                # Check for transition from LONG to SHORT
                if prev_position_type == 'LONG':
                    # Rule 4: If a crossover turns into a crossunder:
                    # - Sell all previously bought shares
                    # - Short an additional 100 stocks
                    signals.loc[current_date, 'action'] = 'SELL_AND_SHORT'
                elif prev_position_type == '':
                    # Rule 2: When no stock holding, sell 100 stocks on crossunder
                    signals.loc[current_date, 'action'] = 'SHORT'
                else:
                    # Already in a SHORT position, no action needed
                    signals.loc[current_date, 'action'] = ''
            
            # No new crossover or crossunder
            else:
                # Carry forward the previous position
                if i > 1:
                    signals.loc[current_date, 'signal'] = signals.loc[signals.index[i-1], 'signal']
                    signals.loc[current_date, 'position'] = signals.loc[signals.index[i-1], 'position']
                    signals.loc[current_date, 'position_type'] = prev_position_type
                    signals.loc[current_date, 'shares'] = signals.loc[signals.index[i-1], 'shares']
                    
                    # Rule 3: If the crossover/crossunder status remains the same, do nothing
                    signals.loc[current_date, 'action'] = ''
                    
                    # Check for position changes without crossover/crossunder
                    if prev_macd_position != current_macd_position:
                        # MACD moved above signal without a proper crossover (rare case)
                        if current_macd_position == 'ABOVE' and prev_position_type == 'SHORT':
                            signals.loc[current_date, 'signal'] = 1.0
                            signals.loc[current_date, 'position'] = 1.0
                            signals.loc[current_date, 'position_type'] = 'LONG'
                            signals.loc[current_date, 'shares'] = self.shares_per_trade
                            signals.loc[current_date, 'action'] = 'COVER_AND_BUY'
                            
                        # MACD moved below signal without a proper crossunder (rare case)
                        elif current_macd_position == 'BELOW' and prev_position_type == 'LONG':
                            signals.loc[current_date, 'signal'] = -1.0
                            signals.loc[current_date, 'position'] = -1.0
                            signals.loc[current_date, 'position_type'] = 'SHORT'
                            signals.loc[current_date, 'shares'] = self.shares_per_trade
                            signals.loc[current_date, 'action'] = 'SELL_AND_SHORT'
        
        return signals
    
    def get_macd_signal_from_monitor(self):
        """
        Get the current MACD signal from the quote monitor if available.
        
        Returns:
            dict: MACD signal information or None if no quote monitor is available
        """
        if self.quote_monitor:
            return self.quote_monitor.get_macd_signal()
        return None
# Default strategy configurations
DEFAULT_STRATEGY_CONFIGS = {
    'moving_average_crossover': {
        'short_window': 20,
        'long_window': 50
    },
    'rsi': {
        'window': 14,
        'oversold': 30,
        'overbought': 70
    },
    'bollinger_bands': {
        'window': 20,
        'num_std': 2
    },
    'macd': {
        'fast_window': 13,
        'slow_window': 21,
        'signal_window': 9
    }
}

# Trading symbols configuration
# DEFAULT_SYMBOLS = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 'NVDA', 'TSLA', 'PLTR']
DEFAULT_SYMBOLS = ['NVDA']

# Default active strategy
DEFAULT_STRATEGY = 'macd'

class StrategyFactory:
    """Factory class for creating strategy instances."""
    
    @staticmethod
    def get_strategy(strategy_name, **kwargs):
        """
        Get a strategy instance based on the strategy name.
        
        Args:
            strategy_name: Name of the strategy to create
            **kwargs: Additional parameters for the strategy
            
        Returns:
            Strategy instance
        """
        strategies = {
            'moving_average_crossover': MovingAverageCrossover,
            'rsi': RSIStrategy,
            'bollinger_bands': BollingerBandsStrategy,
            'macd': MACDStrategy
        }
        
        if strategy_name not in strategies:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        
        # Get default config for this strategy
        default_config = DEFAULT_STRATEGY_CONFIGS.get(strategy_name, {})
        
        # Override defaults with any provided kwargs
        config = {**default_config, **kwargs}
        
        return strategies[strategy_name](**config)


# Example usage
if __name__ == "__main__":
    # Create a sample DataFrame
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    data = pd.DataFrame({
        'open': np.random.normal(100, 5, 100),
        'high': np.random.normal(105, 5, 100),
        'low': np.random.normal(95, 5, 100),
        'close': np.random.normal(100, 5, 100),
        'volume': np.random.normal(1000000, 200000, 100)
    }, index=dates)
    
    # Create a strategy
    strategy = StrategyFactory.get_strategy('moving_average_crossover', short_window=10, long_window=30)
    
    # Generate signals
    signals = strategy.generate_signals(data)
    
    # Print the signals
    print(signals[['close', 'SMA10', 'SMA30', 'signal', 'position']].tail())
