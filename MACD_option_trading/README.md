# MACD Options Trading Strategy

## Strategy Overview

The MACD (Moving Average Convergence Divergence) options trading strategy is an adaptation of the traditional MACD stock trading strategy, specifically designed for options trading. This strategy leverages the MACD indicator's ability to identify trend changes and momentum shifts while incorporating options-specific considerations such as strike selection, expiration timing, implied volatility, and the unique risk/reward characteristics of options.

## Key Components

### 1. Signal Generation
- **Bullish Signal**: When MACD line crosses above the signal line
- **Bearish Signal**: When MACD line crosses below the signal line
- **Confirmation**: Current MACD position relative to signal line (above/below)

### 2. Trading Styles
The strategy offers three distinct approaches to options trading:

#### Directional Style
- **Bullish Signal Actions**: Buy call options with 45-day expiration and ~0.60 delta 
- **Bearish Signal Actions**: Buy put options with 45-day expiration and ~0.60 delta
- **Exit Rules**: Exit long calls on bearish signals; exit long puts on bullish signals

#### Income Style
- **Bullish Signal Actions**: Sell put options with 30-day expiration and ~0.30 delta
- **Bearish Signal Actions**: Sell call options with 30-day expiration and ~0.30 delta
- **Management Rules**: 
  - Roll positions when approaching 21 days to expiration
  - Consider early exit when MACD trend shifts against the position
  - Target 50-75% of maximum profit for early exits

#### Combined Style
- **Bullish Signal Actions**: Buy calls (directional) AND sell puts (income)
- **Bearish Signal Actions**: Buy puts (directional) AND sell calls (income)
- **Risk Adjustment**: Reduce position size for each leg to maintain total risk per trade

### 3. Position Sizing
- Risk a fixed percentage of account value per trade (default: 2%)
- Adjust position size based on option premium
- For short options, further reduce position size to account for higher potential risk

### 4. Implied Volatility Considerations
- Track IV rank to adjust strategy parameters
- In high IV environments:
  - Favor selling options (income style)
  - Use fewer contracts for long options
- In low IV environments:
  - Favor buying options (directional style)
  - Consider wider strikes for short options

### 5. Risk Management
- Monitor portfolio-level Greeks (Delta, Gamma, Theta, Vega)
- Balance positive and negative exposures
- Set maximum allocation limits for each strategy type
- Implement stop-loss mechanisms for long options (percentage of premium)
- Use defined-risk strategies for short options in high-risk scenarios

## System Architecture

The MACD options trading system consists of several interconnected components that work together to monitor the market, generate signals, and execute trades:

### Core Components

1. **MACDOptionsStrategy (`macd_options_strategy.py`)**
   - Extends the base MACD strategy to generate options-specific trading signals
   - Handles contract selection based on delta targeting
   - Calculates appropriate position sizing based on risk parameters
   - Implements different trading styles (directional, income, combined)

2. **Options Classes (`options_trader.py`)**
   - **OptionsContract**: Represents an individual options contract with strike, expiration, and Greeks
   - **OptionsChain**: Manages the collection of available options for a given underlying
   - Provides utilities for option symbol generation (OCC format) and expiration calculations

3. **MACDOptionsTrader (`macd_options_trader.py`)**
   - Integrates real-time market data with the MACD strategy
   - Manages the execution of options trades based on signals
   - Handles position management and risk monitoring
   - Calculates portfolio-level Greeks (Delta, Gamma, Theta, Vega)

4. **Continuous Options Trader Service (`continuous_options_trader_service.py`)**
   - Runs the trading system as a background service
   - Handles market hours detection and scheduling
   - Implements error recovery and system health monitoring
   - Provides state persistence for trading positions
   - Integrates with real-time display for live monitoring

5. **Real-Time Display (`real_time_display.py`)**
   - Provides a terminal-based user interface for monitoring trading activity
   - Displays latest quote data (bid, ask, timestamp) for monitored symbols
   - Shows calculated MACD, Signal line, and Histogram values
   - Displays current trade signal (Buy, Sell, Hold) based on MACD position and crossovers
   - Shows recent data entries in a scrollable table format
   - Tracks and displays trade decisions and MACD signals
   - Offers multiple views (quotes, history, trades, messages) accessible via keyboard shortcuts
   - Supports pause/resume functionality without disrupting data collection
   - Includes a dedicated view for system messages with scrolling controls

6. **Web Display (`web_display.py` and `web_display_integration.py`)**
   - Provides a browser-based interface for monitoring trading activity
   - Visualizes price data and MACD indicators using interactive charts
   - Displays real-time quotes, trade history, and system messages
   - Offers responsive design with filtering and sorting capabilities
   - Accessible from any device with a web browser
   - Runs alongside the terminal display or as an alternative

7. **Quote Monitoring System**
   - **QuoteMonitor**: Base class for real-time market data collection
   - **YahooQuoteMonitor**: Implementation using Yahoo Finance data
   - Calculates MACD indicators in real-time
   - Provides data for strategy decisions
   - Feeds real-time market data to the display system

## Key Differences from Stock Trading

1. **Contract Selection**
   - Options require selecting both strike price and expiration date
   - Delta targeting allows selecting contracts with appropriate probability of profit
   - Time decay (theta) requires careful expiration management

2. **Asymmetric Risk/Reward**
   - Long options have limited risk (premium paid) but unlimited profit potential
   - Short options have limited profit (premium received) but potentially larger risk
   - Position sizing must account for these asymmetries

3. **Greek Exposures**
   - Delta: Directional exposure to underlying
   - Gamma: Rate of change of delta (acceleration)
   - Theta: Time decay (negative for long options, positive for short options)
   - Vega: Sensitivity to implied volatility changes

4. **Volatility Sensitivity**
   - Options prices are affected by implied volatility, not just price movement
   - Strategy adjustments needed based on IV environment
   - Volatility mean reversion can be exploited with appropriate tactics

## Practical Considerations

1. **Liquidity**
   - Only trade options with adequate liquidity (tight bid-ask spreads)
   - Focus on standard expiration cycles when possible
   - Avoid deep ITM or OTM options unless specifically needed

2. **Commission Impact**
   - Options commissions can significantly impact profitability, especially for multi-leg strategies
   - Consider per-contract costs when sizing positions
   - Factor in bid-ask spreads as an additional "cost" of trading

3. **Assignment Risk**
   - Short options can be assigned early, especially around dividends or corporate events
   - Have a plan for handling assignment
   - Consider closing positions before ex-dividend dates

4. **Expiration Management**
   - Avoid holding short options into expiration week (gamma risk increases)
   - Roll positions before reaching 21 days to expiration to avoid accelerated time decay
   - Consider rolling to different strikes based on updated market outlook

## Usage Instructions

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/aswkok/Quant-Trading.git
   cd Quant-Trading/MACD_option_trading
   ```

2. Set up a Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install alpaca-py pandas numpy matplotlib tabulate curses-menu
   ```

4. Configure your API credentials by creating a `.env` file:
   ```
   ALPACA_API_KEY=your_api_key
   ALPACA_API_SECRET=your_api_secret
   ALPACA_PAPER=True  # Set to False for live trading
   ```

### Basic Usage

Run the MACD options trader with default settings:

```bash
python macd_options_trader.py --symbol SPY
```

### Advanced Options

Customize the trading parameters:

```bash
python macd_options_trader.py --symbol SPY --interval 60 --risk 0.02 --style directional --fast-window 13 --slow-window 21 --signal-window 9 --extended-hours --warmup 30
```

### Running as a Background Service

Start the continuous trading service:

```bash
python continuous_options_trader_service.py --symbols SPY QQQ --style combined --risk 0.015
```

To run as a daemon process in the background:

```bash
python continuous_options_trader_service.py --symbols SPY QQQ --daemon
```

### Display Options

#### Terminal Display

The terminal display is enabled by default. You can control it with these options:

```bash
# Disable the terminal display
python continuous_options_trader_service.py --symbols SPY --no-display

# Toggle the display on/off during execution (press 'd')
python continuous_options_trader_service.py --symbols SPY --toggle-display

# Adjust the display update interval
python continuous_options_trader_service.py --symbols SPY --display-interval 1.0
```

#### Web Display

Run the web display integration to view trading data in a browser:

```bash
python web_display_integration.py --symbols SPY --port 8080
```

Then open your browser and navigate to `http://localhost:8080`

### Logging Options

Control the verbosity of log messages:

```bash
# Specify a custom log file location
python continuous_options_trader_service.py --symbols SPY --log-file /path/to/logfile.log

# Set the log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
python continuous_options_trader_service.py --symbols SPY --log-level WARNING

# Reduce console output (only show warnings and errors)
python continuous_options_trader_service.py --symbols SPY --quiet-console
```

### Real-Time Display Options

Enable the real-time display for visual monitoring:

```bash
python continuous_options_trader_service.py --symbols SPY --extended-hours
```

Disable the display for headless operation:

```bash
python continuous_options_trader_service.py --symbols SPY --no-display
```

Customize the display update interval:

```bash
python continuous_options_trader_service.py --symbols SPY --display-interval 1.0
```

Test the display with simulated data:

```bash
python test_display.py
```

## System Requirements

### Software Requirements

- Python 3.7+
- Required packages:
  - alpaca-py (for API integration)
  - pandas (for data manipulation)
  - numpy (for numerical operations)
  - matplotlib (for visualization)
  - tabulate (for display formatting)
  - curses-menu (for terminal-based UI)

### Market Data Requirements

- Real-time quotes for underlying securities
- Options chain data with Greeks
- Historical implied volatility data for IV rank calculation

### Trading Infrastructure

- Broker API with options trading capabilities (Alpaca, etc.)
- Order types: market, limit, stop, and complex orders
- Capability to handle multi-leg strategies

## Backtesting and Optimization Considerations

1. **Historical Options Data**
   - Need historical options data with accurate pricing and Greeks
   - Consider bid-ask spreads in backtests, not just mid prices
   - Factor in realistic fill assumptions

2. **Parameter Optimization**
   - MACD parameters (fast, slow, signal windows)
   - Target delta for contracts
   - Days to expiration
   - Position sizing and risk percentage
   - Early exit thresholds

3. **Performance Metrics**
   - Win rate and average win/loss ratio
   - Risk-adjusted returns (Sharpe, Sortino)
   - Maximum drawdown
   - Profit factor
   - Option-specific metrics (premium capture %, assignment rate)

## Conclusion

The MACD options trading strategy extends the popular indicator-based approach to the more complex world of options. By carefully selecting contracts, managing position sizes, and adapting to market volatility conditions, this strategy offers multiple ways to capitalize on the MACD signals while managing the unique risks of options trading.

The implementation allows for flexible trading approaches - from pure directional plays with long options to income-focused strategies with short options, or a combined approach that balances these tactics. This adaptability makes the strategy suitable for various market conditions and trader preferences.