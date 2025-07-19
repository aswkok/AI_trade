# TWS (Trader Workstation) Setup Guide

## Overview
This guide helps you set up Interactive Brokers' Trader Workstation (TWS) to work with the ibapi Python library for automated trading.

## Prerequisites
- Interactive Brokers account (live or paper trading)
- TWS or IB Gateway installed
- Python environment with ibapi installed

## Step 1: Download and Install TWS

1. Go to [Interactive Brokers Downloads](https://www.interactivebrokers.com/en/trading/tws.php)
2. Download TWS for your operating system
3. Install and launch TWS
4. Login with your IB credentials

## Step 2: Enable API Access

### In TWS:
1. Go to **Configure** → **API** → **Settings**
2. Check **"Enable ActiveX and Socket Clients"**
3. Set **Socket Port**:
   - **7497** for paper trading
   - **7496** for live trading
4. Optional: Add **127.0.0.1** to **Trusted IPs**
5. Optional: Check **"Download open orders on connection"**
6. Click **OK** and restart TWS

### API Settings Explained:
- **Socket Port**: The port your Python scripts will connect to
- **Trusted IPs**: IP addresses allowed to connect (127.0.0.1 = localhost)
- **Master API client ID**: ID that can modify other clients' orders
- **Read-Only API**: Restricts API to market data only

## Step 3: Test Connection

Run the test script:
```bash
conda activate dev
python test_tws_auto.py
```

Expected output for successful connection:
```
✅ Successfully connected to TWS!
✅ Next valid order ID: 1
✅ Managed accounts: ['DU123456']
✅ Connection test successful!
```

## Step 4: Common Issues and Solutions

### Connection Failed (Error 502)
- **Cause**: TWS not running or API not enabled
- **Solution**: Start TWS and enable API in settings

### Connection Refused
- **Cause**: Wrong port or firewall blocking
- **Solution**: Check port settings (7497/7496) and firewall

### Authentication Error
- **Cause**: Not logged into TWS
- **Solution**: Login to TWS before running scripts

### Market Data Issues
- **Cause**: No market data subscription
- **Solution**: Subscribe to market data in your IB account

## Step 5: Port Configuration

### Paper Trading (Recommended for Testing)
- Port: **7497**
- Use paper trading account
- Safe for testing strategies

### Live Trading
- Port: **7496**
- Use live trading account
- Real money - use with caution

## Step 6: Running Your First Test

Use the interactive test script:
```bash
python test_tws_connection.py
```

This will:
1. Connect to TWS
2. Request account information
3. Get market data for AAPL
4. Disconnect cleanly

## Security Best Practices

1. **Use Paper Trading First**: Always test with paper trading
2. **Limit API Access**: Only enable when needed
3. **Monitor Connections**: Check active API connections in TWS
4. **Set Trusted IPs**: Restrict access to localhost only
5. **Use Client IDs**: Assign unique IDs to different scripts

## Integration with AItrade

To integrate with your existing AItrade system:

1. **Add IB Data Source**: Create an IBDataSource class
2. **Order Execution**: Route orders through IB instead of Alpaca
3. **Account Management**: Use IB account data
4. **Risk Management**: Leverage IB's built-in risk controls

Example integration in your trading system:
```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

class IBTradingClient(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        # Your trading logic here
```

## Troubleshooting

### Check TWS Status
1. Look for "API" in TWS status bar (green = connected)
2. Check **Configure** → **API** → **Active Sessions**
3. Verify correct port in settings

### Connection Issues
```bash
# Test different ports
python -c "
import socket
s = socket.socket()
try:
    s.connect(('127.0.0.1', 7497))
    print('Port 7497 open')
except:
    print('Port 7497 closed')
s.close()
"
```

### Log Files
- TWS logs: `~/Jts/tws/logs/`
- API logs: Enable in API settings

## Next Steps

Once TWS is connected:
1. **Market Data**: Subscribe to real-time data feeds
2. **Order Management**: Implement order placement and tracking
3. **Portfolio Integration**: Sync with your existing strategies
4. **Risk Controls**: Set up automated risk management
5. **Monitoring**: Implement connection health checks

## Resources

- [IB API Documentation](https://interactivebrokers.github.io/tws-api/)
- [Python API Guide](https://interactivebrokers.github.io/tws-api/initial_setup.html)
- [Sample Code](https://github.com/InteractiveBrokers/tws-api/tree/master/samples/Python)