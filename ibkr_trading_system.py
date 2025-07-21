#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IBKR Trading System

Primary trading adapter for Interactive Brokers TWS API using ib_async.
This system provides the main trading interface with IBKR as the primary broker.
"""

import os
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np
from dotenv import load_dotenv

try:
    from ib_async import IB, Stock, Contract, MarketOrder, LimitOrder, Order
    from ib_async import OrderStatus, PnL, PortfolioItem, Position, AccountValue
    from ib_async import BarData, TickData, util
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    logging.warning("ib_async not available. Install with: pip install ib_async")

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

class IBKRTradingSystem:
    """
    Primary IBKR Trading System using Interactive Brokers TWS API.
    """
    
    def __init__(self, host=None, port=None, client_id=None):
        """
        Initialize IBKR trading system.
        
        Args:
            host: TWS/Gateway host (default from env or localhost)
            port: TWS/Gateway port (default from env or 7497)
            client_id: Client ID (default from env or 1)
        """
        if not IBKR_AVAILABLE:
            raise ImportError("ib_async library not available. Install with: pip install ib_async")
        
        # Connection parameters from environment or defaults
        self.host = host or os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = int(port or os.getenv("IBKR_PORT", "7497"))
        self.client_id = int(client_id or os.getenv("IBKR_CLIENT_ID", "1"))
        
        # IBKR client
        self.ib = IB()
        self.is_connected = False
        
        # Trading parameters
        self.risk_per_trade = float(os.getenv("RISK_PER_TRADE", "0.02"))
        self.max_positions = int(os.getenv("MAX_POSITIONS", "5"))
        self.extended_hours = os.getenv("EXTENDED_HOURS", "True").lower() == "true"
        self.overnight_trading = os.getenv("OVERNIGHT_TRADING", "True").lower() == "true"
        
        # Data cache
        self.data_cache = {}
        
        logger.info(f"IBKR Trading System initialized")
        logger.info(f"Connection: {self.host}:{self.port}, Client ID: {self.client_id}")
    
    def connect(self):
        """Connect to IBKR TWS/Gateway."""
        try:
            if not self.is_connected:
                # Start event loop if not already running
                try:
                    # Try newer ib_async API
                    util.startLoop()
                except Exception:
                    # Handle different ib_async versions
                    pass
                
                self.ib.connect(self.host, self.port, clientId=self.client_id)
                self.is_connected = True
                logger.info(f"Connected to IBKR TWS/Gateway at {self.host}:{self.port}")
                return True
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from IBKR."""
        try:
            if self.is_connected:
                self.ib.disconnect()
                self.is_connected = False
                logger.info("Disconnected from IBKR")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    def _ensure_connected(self):
        """Ensure connection to IBKR."""
        if not self.is_connected:
            return self.connect()
        return True
    
    def _create_stock_contract(self, symbol: str) -> Stock:
        """Create stock contract."""
        return Stock(symbol, 'SMART', 'USD')
    
    def is_paper_trading(self):
        """Check if using paper trading account."""
        if not self._ensure_connected():
            return False
        try:
            account_values = self.ib.accountValues()
            for av in account_values:
                if 'DU' in av.account:  # Demo accounts have 'DU' prefix
                    return True
            return False
        except:
            return False
    
    def get_account_info(self):
        """Get account information."""
        if not self._ensure_connected():
            return {}
        
        try:
            account_values = self.ib.accountValues()
            
            account_info = {
                'cash': 0,
                'portfolio_value': 0,
                'buying_power': 0,
                'id': 'Unknown',
                'daytrade_count': 0
            }
            
            for av in account_values:
                if av.tag == 'TotalCashValue':
                    account_info['cash'] = float(av.value)
                elif av.tag == 'NetLiquidation':
                    account_info['portfolio_value'] = float(av.value)
                elif av.tag == 'BuyingPower':
                    account_info['buying_power'] = float(av.value)
                elif av.tag == 'AccountCode':
                    account_info['id'] = av.value
            
            logger.info(f"Account ID: {account_info['id']}")
            logger.info(f"Cash: ${account_info['cash']:,.2f}")
            logger.info(f"Portfolio Value: ${account_info['portfolio_value']:,.2f}")
            logger.info(f"Buying Power: ${account_info['buying_power']:,.2f}")
            
            return account_info
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return {}
    
    def get_all_positions(self):
        """Get all positions."""
        if not self._ensure_connected():
            return []
        
        try:
            positions = self.ib.positions()
            position_list = []
            
            for pos in positions:
                if pos.position != 0:
                    # Create position object that matches Alpaca interface
                    class Position:
                        def __init__(self, symbol, qty, side, market_value):
                            self.symbol = symbol
                            self.qty = str(abs(qty))
                            self.side = side
                            self.market_value = str(market_value)
                    
                    side = 'long' if pos.position > 0 else 'short'
                    position_obj = Position(
                        pos.contract.symbol,
                        pos.position,
                        side,
                        pos.marketValue
                    )
                    position_list.append(position_obj)
                    
                    logger.info(f"Position: {pos.contract.symbol}, Qty: {pos.position}, Value: ${pos.marketValue}")
            
            logger.info(f"Current positions: {len(position_list)}")
            return position_list
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def get_positions(self):
        """Alias for get_all_positions."""
        return self.get_all_positions()
    
    def get_historical_data(self, symbol, timeframe=None, limit=250):
        """Get historical data."""
        if not self._ensure_connected():
            return pd.DataFrame()
        
        try:
            # Map timeframe to IBKR format
            if timeframe is None or timeframe == 'Day':
                bar_size = '1 day'
                duration = f'{limit} D'
            elif timeframe == 'Hour':
                bar_size = '1 hour'
                duration = f'{min(limit, 120)} H'  # Hours, max 120 hours (5 days)
            elif timeframe == 'Minute':
                bar_size = '1 min'
                # For minute data, IBKR limits historical requests
                # Use days for longer periods, seconds for very short periods
                if limit <= 1440:  # Less than 1 day of minutes
                    duration = f'{limit * 60} S'  # Convert minutes to seconds
                else:
                    duration = f'{min(limit // 1440 + 1, 30)} D'  # Convert to days, max 30 days
            else:
                bar_size = '1 day'
                duration = f'{limit} D'
            
            contract = self._create_stock_contract(symbol)
            
            # Request historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=not self.extended_hours,
                formatDate=1
            )
            
            if not bars:
                logger.warning(f"No historical data for {symbol}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            data = []
            for bar in bars:
                data.append({
                    'timestamp': bar.date,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume
                })
            
            df = pd.DataFrame(data)
            if not df.empty:
                df.set_index('timestamp', inplace=True)
                df.index = pd.to_datetime(df.index)
                
                # Ensure numeric columns
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
            
            logger.info(f"Retrieved {len(df)} historical bars for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_realtime_data(self, symbol):
        """Get real-time market data."""
        if not self._ensure_connected():
            return pd.DataFrame()
        
        try:
            contract = self._create_stock_contract(symbol)
            ticker = self.ib.reqMktData(contract)
            self.ib.sleep(1)  # Wait for data
            
            if ticker.last and ticker.bid and ticker.ask:
                latest_data = pd.DataFrame({
                    'timestamp': [datetime.now()],
                    'open': [float(ticker.last)],
                    'high': [float(ticker.ask)],
                    'low': [float(ticker.bid)],
                    'close': [float(ticker.last)],
                    'volume': [float(ticker.volume) if ticker.volume else 0]
                })
                latest_data.set_index('timestamp', inplace=True)
                
                logger.info(f"Real-time data for {symbol}: ${ticker.last}")
                return latest_data
            else:
                logger.warning(f"No real-time data for {symbol}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error getting real-time data for {symbol}: {e}")
            return pd.DataFrame()
    
    def place_market_order(self, symbol, qty, side, extended_hours=None):
        """Place market order."""
        if not self._ensure_connected():
            return None
        
        try:
            # Convert side to action
            if hasattr(side, 'name'):
                action = side.name
            else:
                action = str(side).upper()
            
            contract = self._create_stock_contract(symbol)
            order = MarketOrder(action, qty)
            
            # Set extended hours
            if extended_hours is not None:
                order.outsideRth = extended_hours
            elif self.extended_hours:
                order.outsideRth = True
            
            trade = self.ib.placeOrder(contract, order)
            order_id = str(trade.order.orderId)
            
            logger.info(f"Market order placed: {action} {qty} {symbol}, ID: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"Error placing market order for {symbol}: {e}")
            return None
    
    def get_clock(self):
        """Get market clock info."""
        now = datetime.now()
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        class Clock:
            def __init__(self):
                self.is_open = market_open <= now <= market_close
                self.next_open = market_open + timedelta(days=1) if now > market_close else market_open
        
        return Clock()
    
    def save_strategy_state(self, symbol, strategy_name, state_data):
        """Save strategy state."""
        import json
        
        state_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strategy_state')
        os.makedirs(state_dir, exist_ok=True)
        
        state_file = os.path.join(state_dir, f"{symbol}_{strategy_name}_ibkr.json")
        
        # Convert numpy types
        serializable_data = {}
        for key, value in state_data.items():
            if hasattr(value, 'item'):
                serializable_data[key] = value.item()
            else:
                serializable_data[key] = value
        
        with open(state_file, 'w') as f:
            json.dump(serializable_data, f)
            
        logger.info(f"IBKR strategy state saved for {symbol} ({strategy_name})")
    
    def get_strategy_state(self, symbol, strategy_name):
        """Get saved strategy state."""
        import json
        
        state_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strategy_state')
        state_file = os.path.join(state_dir, f"{symbol}_{strategy_name}_ibkr.json")
        
        if not os.path.exists(state_file):
            return None
            
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading IBKR strategy state: {e}")
            return None

# Compatibility wrapper for existing Alpaca interface
class IBKRTradingClient:
    """Trading client wrapper to match Alpaca interface."""
    
    def __init__(self, ibkr_system):
        self.ibkr = ibkr_system
    
    def get_account(self):
        """Get account info."""
        info = self.ibkr.get_account_info()
        
        class Account:
            def __init__(self, info):
                self.id = info.get('id', 'Unknown')
                self.cash = info.get('cash', 0)
                self.portfolio_value = info.get('portfolio_value', 0)
                self.buying_power = info.get('buying_power', 0)
                self.daytrade_count = info.get('daytrade_count', 0)
        
        return Account(info)
    
    def get_all_positions(self):
        """Get all positions."""
        return self.ibkr.get_all_positions()
    
    def submit_order(self, order_request):
        """Submit order."""
        try:
            symbol = order_request.symbol
            qty = order_request.qty
            side = order_request.side
            
            if hasattr(order_request, 'limit_price') and order_request.limit_price:
                # Limit order - implement if needed
                return self.ibkr.place_market_order(symbol, qty, side)
            else:
                return self.ibkr.place_market_order(symbol, qty, side)
        except Exception as e:
            logger.error(f"Error submitting order: {e}")
            return None
    
    def get_clock(self):
        """Get market clock."""
        return self.ibkr.get_clock()
    
    def get_order_by_id(self, order_id):
        """Get order by ID."""
        # Simplified implementation
        return None