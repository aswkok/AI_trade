# Data Sources for Quant Trading System

This document explains how to use different data sources with the Quant Trading system.

## Available Data Sources

The system now supports two data sources for real-time market data:

1. **Alpaca API** (Default): Uses Alpaca's WebSocket API to stream real-time quotes.
2. **Yahoo Finance API**: Uses Yahoo Finance as an alternative data source, especially useful during extended hours or as a fallback.

## How to Switch Between Data Sources

You can easily switch between data sources by changing the `DATA_SOURCE` environment variable in your `.env` file:

```
# Set to ALPACA to use Alpaca's WebSocket API (default)
# Set to YAHOO to use Yahoo Finance as a fallback or alternative
DATA_SOURCE=ALPACA
```

Change this to `DATA_SOURCE=YAHOO` to use Yahoo Finance instead.

## Comparison of Data Sources

### Alpaca API
- **Pros**: 
  - Real-time WebSocket streaming
  - Accurate bid/ask prices
  - Lower latency
  - Direct integration with trading execution
- **Cons**:
  - Requires API keys
  - May have data limitations based on your account tier
  - May not provide data during some extended hours

### Yahoo Finance API
- **Pros**:
  - No API keys required
  - Extended hours data availability
  - Good fallback option
  - Works even when Alpaca is down
- **Cons**:
  - Slightly higher latency
  - Less accurate bid/ask prices (sometimes estimated)
  - Rate limits may apply
  - No direct trading execution

## Implementation Details

The system uses a wrapper module called `quote_monitor_selector.py` that automatically selects the appropriate data source based on your environment settings. This ensures that all other components of the system work seamlessly regardless of which data source is being used.

The `integrated_macd_trader.py` script has been updated to use this selector, so you don't need to modify any code when switching between data sources.

## Usage Examples

### Running with Alpaca (Default)

```bash
# Make sure DATA_SOURCE=ALPACA in your .env file
python integrated_macd_trader.py --symbol AAPL --shares 100 --interval 2 --extended-hours
```

### Running with Yahoo Finance

```bash
# First, set DATA_SOURCE=YAHOO in your .env file
python integrated_macd_trader.py --symbol AAPL --shares 100 --interval 2 --extended-hours
```

### Testing Yahoo Finance Directly

You can also test the Yahoo Finance quote monitor directly:

```bash
python yahoo_quote_monitor.py --symbol AAPL --interval 5
```

## Troubleshooting

If you encounter issues with one data source, try switching to the other. For example, if Alpaca is experiencing downtime or rate limiting, you can switch to Yahoo Finance by changing the `DATA_SOURCE` environment variable.

Remember to install the required dependencies for both data sources:
```bash
pip install alpaca-py websocket-client yfinance
```
