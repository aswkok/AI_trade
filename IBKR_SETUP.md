# IBKR TWS API Integration Setup Guide

This guide will help you set up Interactive Brokers TWS API integration with your trading system.

## 🎯 Overview

Your trading system now uses **IBKR TWS API as the primary broker** with **Alpaca as fallback**. The system automatically tries IBKR first, and if that fails, falls back to Alpaca.

## 📋 Prerequisites

1. **Interactive Brokers Account** (paper or live)
2. **TWS (Trader Workstation) or IB Gateway** installed
3. **Python 3.8+** with required packages

## 🔧 Installation Steps

### Step 1: Install Required Packages

```bash
# Install IBKR API package
pip install ib_async

# Install other dependencies (if not already installed)
pip install pandas numpy python-dotenv alpaca-py
```

### Step 2: Download and Install TWS/Gateway

1. **Download** from [IBKR website](https://www.interactivebrokers.com/en/trading/tws.php)
2. **Install** TWS or IB Gateway (Gateway is lighter and recommended for API use)
3. **Login** with your IBKR account credentials

### Step 3: Configure TWS/Gateway for API Access

#### Enable API in TWS:
1. **File → Global Configuration → API → Settings**
2. ✅ **Enable "Enable ActiveX and Socket Clients"**
3. ✅ **Check "Download open orders on connection"**
4. **Socket Port**: 
   - Paper Trading: `7497` (TWS) or `4002` (Gateway)
   - Live Trading: `7496` (TWS) or `4001` (Gateway)
5. **Trusted IPs**: Add `127.0.0.1`
6. **Master API client ID**: Leave as `0` (or set to specific value)
7. **Restart TWS/Gateway** after changes

#### Gateway Configuration:
If using IB Gateway instead of full TWS:
1. **Login** to IB Gateway
2. **Configure → Settings**
3. Set same API settings as above
4. Gateway uses less memory and is more stable for automated trading

### Step 4: Configure Environment Variables

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file** with your settings:
   ```bash
   # IBKR Configuration (Primary)
   IBKR_HOST=127.0.0.1
   IBKR_PORT=7497          # 7497 for TWS paper, 4002 for Gateway paper
   IBKR_CLIENT_ID=1        # Unique client ID
   
   # Alpaca Configuration (Fallback)
   ALPACA_API_KEY=your_alpaca_key
   ALPACA_API_SECRET=your_alpaca_secret
   ```

### Step 5: Test Connection

Run the connection test script:

```bash
python test_ibkr_connection.py
```

You should see:
```
🎉 ALL TESTS PASSED!
✅ IBKR TWS API integration is ready to use
```

## 🚀 Usage

### Quick Start

```bash
# Test with historical data
python unified_main.py --mode historical --symbols AAPL MSFT

# Run continuous trading (1-minute intervals)
python unified_main.py --mode continuous --interval 1

# Run with specific strategy
python unified_main.py --mode continuous --strategy macd --symbols NVDA
```

### Available Modes

1. **Historical** - Backtest on historical data
2. **Realtime** - Single execution with live data  
3. **Continuous** - Continuous trading at specified intervals

### Broker Selection

The system automatically selects brokers in this order:
1. **IBKR TWS API** (primary)
2. **Alpaca API** (fallback)

You can see which broker is being used in the logs:
```
🎯 Using IBKR TWS API (PRIMARY)
⚠️  Using Alpaca API (FALLBACK)
```

## 🔧 Port Configuration Guide

| Account Type | Platform | Port | Usage |
|-------------|----------|------|-------|
| Paper | TWS | 7497 | Paper trading with full TWS |
| Paper | Gateway | 4002 | Paper trading with lightweight Gateway |
| Live | TWS | 7496 | Live trading with full TWS |
| Live | Gateway | 4001 | Live trading with lightweight Gateway |

**Recommendation**: Use Gateway (4002 for paper, 4001 for live) as it's more stable for automated trading.

## ⚠️ Important Notes

### Security
- **Start with paper trading** to test everything
- Keep your **API keys secure** and never commit them to version control
- Use **strong passwords** and **2FA** on your IBKR account

### Trading Hours
- **Regular Hours**: 9:30 AM - 4:00 PM ET
- **Extended Hours**: 4:00 AM - 8:00 PM ET (if enabled)
- **Overnight**: 8:00 PM - 4:00 AM ET (if enabled)

### Position Limits
- IBKR may have **position size limits** based on account type
- **PDT rules** apply to accounts under $25k
- **Margin requirements** vary by security

## 🐛 Troubleshooting

### Common Issues

#### 1. "Failed to connect to IBKR"
**Solutions:**
- Ensure TWS/Gateway is **running and logged in**
- Check **API is enabled** in settings
- Verify **port number** matches your configuration
- Confirm **127.0.0.1** is in trusted IPs
- Try different **client ID** (1-32)

#### 2. "Socket connection refused"
**Solutions:**
- Check if **another application** is using the same client ID
- **Restart TWS/Gateway**
- Verify **firewall** isn't blocking the port
- Try **different port** (switch between TWS/Gateway)

#### 3. "No data received"
**Solutions:**
- Ensure you have **market data subscriptions**
- Check **symbol format** (use correct exchange)
- Verify **account permissions**
- Some data requires **real-time subscriptions**

#### 4. "Order rejected"
**Solutions:**
- Check **account buying power**
- Verify **order size** meets minimum requirements
- Ensure **market is open** (or extended hours enabled)
- Check **position limits**

### Debug Mode

Enable debug logging:
```python
import logging
logging.getLogger('ib_async').setLevel(logging.DEBUG)
```

### Test Commands

```bash
# Test just the connection
python test_ibkr_connection.py

# Test with debug output
python -c "
from broker_selector import UnifiedTradingSystem
import logging
logging.basicConfig(level=logging.DEBUG)
system = UnifiedTradingSystem()
print(f'Connected to: {system.get_broker_type()}')
"
```

## 📁 File Structure

```
AItrade/
├── ibkr_trading_system.py     # IBKR TWS API adapter
├── broker_selector.py         # Unified broker selection
├── unified_main.py            # New main entry point
├── test_ibkr_connection.py    # Connection test script
├── .env.example               # Environment template
├── IBKR_SETUP.md             # This setup guide
├── quant_main.py             # Original Alpaca-only system
└── strategies.py             # Trading strategies (unchanged)
```

## 🔄 Migration from Alpaca-Only

Your existing strategies work without changes! The new system:

1. **Maintains same interface** as AlpacaTradingSystem
2. **Automatically selects** IBKR as primary, Alpaca as fallback
3. **Preserves all existing functionality**
4. **Adds IBKR-specific features**

To migrate:
1. **Install ib_async**: `pip install ib_async`
2. **Setup TWS/Gateway** (this guide)
3. **Configure .env** file
4. **Use unified_main.py** instead of quant_main.py

## 📞 Support

### IBKR API Documentation
- [TWS API Documentation](https://interactivebrokers.github.io/tws-api/)
- [ib_async Documentation](https://ib-insync.readthedocs.io/)

### Getting Help
1. **Check logs** in `unified_trading.log`
2. **Run test script**: `python test_ibkr_connection.py`  
3. **IBKR Support**: Contact for account/platform issues
4. **GitHub Issues**: For code-related problems

---

## 🎉 Ready to Trade!

Once setup is complete, you'll have:
- ✅ **IBKR TWS API** as primary broker
- ✅ **Alpaca API** as automatic fallback  
- ✅ **Seamless broker switching**
- ✅ **All existing strategies** working with both brokers
- ✅ **Enhanced features** from IBKR integration

Happy trading! 🚀