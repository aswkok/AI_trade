# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AItrade is an integrated trading framework combining two distinct but complementary systems:

1. **Quantitative Trading Engine**: Real-time MACD-based algorithmic trading with **IBKR TWS API (primary)** and **Alpaca API (fallback)** integration
2. **Multi-Agent AI Framework**: LLM-powered collaborative trading decision making system

The codebase merges technical analysis automation with AI-driven market analysis through specialized agent teams.

## 🆕 **MAJOR UPDATE: IBKR TWS API Integration**

**New Broker Architecture**: The system now supports **Interactive Brokers TWS API** as the primary broker with automatic fallback to Alpaca. This provides professional-grade trading capabilities with enhanced features and lower costs.

## Core Architecture

### Dual System Design

**🚀 Enhanced Quantitative Engine** (`/` root level):
- **`quant_main.py`** - **ENHANCED**: Primary entry point with IBKR/Alpaca unified system + legacy mode
- **`broker_selector.py`** - **NEW**: Intelligent broker switching and management
- **`ibkr_trading_system.py`** - **NEW**: IBKR TWS API integration and adapter
- `integrated_macd_trader.py` - Real-time MACD trading with extended hours support
- `strategies.py` - Technical analysis strategies (MACD, RSI, Moving Average Crossover)
- `MACD_option_trading/` - Options trading system with sophisticated Greeks tracking
- **`tests/`** - **NEW**: Testing scripts and validation tools
- **`demos/`** - **NEW**: Demo scripts and interactive examples

**AI Agent System** (`tradingagents/`):
- `trading_agent_main.py` - Multi-agent system entry point
- `graph/trading_graph.py` - LangGraph orchestration of agent collaboration
- `agents/` - Specialized agent implementations (analysts, researchers, risk managers)
- `dataflows/` - Multi-source data integration (FinnHub, Yahoo Finance, Reddit)

### Key Integration Points

1. **🆕 Broker Layer**: **IBKR TWS API (primary)** with **Alpaca API (fallback)** for professional execution
2. **🆕 Data Layer**: Both systems share data sources (Yahoo Finance primary, IBKR/Alpaca fallback, market data caching)
3. **Decision Synthesis**: AI analysis can inform quantitative strategy parameters
4. **Risk Management**: Combined technical and fundamental risk assessment
5. **Execution**: Unified system handles trade execution via **IBKR first, then Alpaca**
6. **🆕 Broker Switching**: Manual and automatic broker switching capabilities

## Development Commands

### Environment Setup
```bash
# Install all dependencies (merged requirements)
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env  # Edit with your API keys
```

### Required API Keys
```bash
# 🆕 IBKR TWS API (Primary Broker)
export IBKR_HOST=127.0.0.1
export IBKR_PORT=7497              # TWS: 7497 (paper), 7496 (live)
export IBKR_CLIENT_ID=1            # Gateway: 4002 (paper), 4001 (live)

# Alpaca API (Fallback Broker)
export ALPACA_API_KEY=your_alpaca_key
export ALPACA_API_SECRET=your_alpaca_secret
export PAPER_TRADING_URL=https://paper-api.alpaca.markets
export PAPER_DATA_URL=https://data.alpaca.markets

# AI Agent System
export OPENAI_API_KEY=your_openai_key  # Or DeepSeek key
export FINNHUB_API_KEY=your_finnhub_key

# 🆕 Data Source Configuration (Yahoo Finance Primary)
export DATA_SOURCE=YAHOO           # YAHOO (primary), ALPACA (fallback)
export YAHOO_PRICE_TYPE=MID        # MID (bid/ask average), CLOSE (close price)

# 🆕 Broker Selection
export FORCE_BROKER=AUTO           # AUTO, IBKR, ALPACA
```

### 🚀 Running Enhanced Trading System (IBKR + Alpaca)
```bash
# Test connection to IBKR TWS
python tests/test_ibkr_connection.py

# Quick test with historical data (IBKR primary, Alpaca fallback)
python quant_main.py --mode historical --symbols NVDA AAPL

# Continuous trading with IBKR primary
python quant_main.py --mode continuous --interval 1 --symbols NVDA

# Force specific broker
python quant_main.py --broker ibkr --mode continuous        # Force IBKR
python quant_main.py --broker alpaca --mode historical      # Force Alpaca
python quant_main.py --broker legacy --mode continuous      # Legacy Alpaca-only

# Interactive broker switching
python quant_main.py --interactive --mode continuous
python demos/demo_broker_switching.py
```

### Running Specialized Trading Systems
```bash
# Real-time MACD trading (specialized system)
python integrated_macd_trader.py --symbol NVDA --interval 60 --shares 100 --extended-hours

# Options trading with MACD signals
cd MACD_option_trading && python main.py
```

### Running AI Agent System
```bash
# Interactive CLI interface
python -m cli.main

# Direct Python usage
python trading_agent_main.py

# Custom configuration example
python -c "
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
config = DEFAULT_CONFIG.copy()
config['max_debate_rounds'] = 3
ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate('NVDA', '2024-05-10')
print(decision)
"
```

### Testing and Validation
```bash
# 🆕 Test IBKR TWS API connection
python tests/test_ibkr_connection.py

# 🆕 Test broker switching capabilities
python demos/demo_broker_switching.py

# Test MACD strategy with historical data
python strategies.py  # Contains embedded tests

# Validate market hours detection
python MACD_option_trading/test_market_hours.py

# Test data source connectivity
python yahoo_quote_monitor.py --symbol AAPL --interval 5
python enhanced_quote_monitor.py --symbol AAPL --interval 60

# Test AI agent system
python test_run.py

# 🆕 Test enhanced system end-to-end
python quant_main.py --mode historical --symbols AAPL  # Quick test
```

## Key Architecture Patterns

### Quantitative Trading Flow
1. **Data Collection**: Multi-source real-time quotes (Alpaca WebSocket + Yahoo Finance fallback)
2. **Signal Generation**: MACD crossover/crossunder detection with position state management
3. **Risk Management**: Position sizing, extended hours eligibility, time-based throttling
4. **Execution**: Market/limit orders through Alpaca API with session-aware pricing
5. **State Persistence**: JSON-based strategy state tracking for continuous operation

### AI Agent Collaboration Flow
1. **Analyst Team**: Parallel analysis (fundamentals, sentiment, news, technical)
2. **Research Debate**: Bull vs bear researchers engage in structured arguments
3. **Investment Planning**: Trader synthesizes research into actionable plan
4. **Risk Assessment**: Multi-perspective risk evaluation (conservative, aggressive, neutral)
5. **Final Decision**: Portfolio manager approves/rejects with comprehensive reasoning

### Data Source Architecture (🆕 UPDATED)
- **🆕 PRIMARY**: Yahoo Finance for real-time and historical data (24/7 availability)
- **FALLBACK**: IBKR/Alpaca APIs for broker-specific data and execution
- **AI Data**: FinnHub, Google News, Reddit via specialized dataflows
- **Caching**: Local CSV caching for historical data and backtesting
- **Selection**: `quote_monitor_selector.py` and `broker_selector.py` with Yahoo Finance priority

### State Management Patterns
```python
# Quantitative system - JSON state files
strategy_state = {
    'position_type': 'LONG',
    'shares': 100,
    'last_action': 'BUY',
    'last_signal_time': datetime.now().isoformat()
}

# AI system - LangGraph state objects
class AgentState(TypedDict):
    ticker: str
    analysis_date: str
    market_data: dict
    analyst_reports: list
    debate_history: list
    final_decision: dict
```

## Configuration Systems

### Quantitative Trading Configuration
```python
# strategies.py
DEFAULT_STRATEGY = "macd"
DEFAULT_SYMBOLS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'META']
DEFAULT_STRATEGY_CONFIGS = {
    "macd": {
        "fast_window": 13,
        "slow_window": 21, 
        "signal_window": 9,
        "shares_per_trade": 100
    }
}

# Environment variables
RISK_PER_TRADE=0.02
MAX_POSITIONS=5
EXTENDED_HOURS=True
OVERNIGHT_TRADING=True
DATA_SOURCE=ALPACA  # or YAHOO for fallback
```

### AI Agent Configuration
```python
# tradingagents/default_config.py  
DEFAULT_CONFIG = {
    "llm_provider": "openai",
    "deep_think_llm": "deepseek-reasoner",  # Complex analysis
    "quick_think_llm": "deepseek-chat",     # Fast decisions
    "backend_url": "https://api.deepseek.com/v1",
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "online_tools": True  # Real-time vs cached data
}
```

## Extended Hours Trading Implementation

### Market Session Detection
```python
# Current time-based session logic
market_open = dt_time(9, 30)     # 9:30 AM ET
market_close = dt_time(16, 0)    # 4:00 PM ET  
pre_market_open = dt_time(4, 0)  # 4:00 AM ET
after_hours_close = dt_time(20, 0) # 8:00 PM ET

# Session-aware order placement
if is_extended_hours:
    # Must use limit orders with adjusted pricing
    limit_price = ask_price * (1 + buffer_percentage/100)
    order = LimitOrderRequest(extended_hours=True)
else:
    # Regular hours can use market orders
    order = MarketOrderRequest()
```

### MACD Strategy State Machine
```python
# Position state transitions
if macd_position == 'ABOVE' and current_position_type == 'SHORT':
    action = 'COVER_AND_BUY'  # Close short, open long
elif macd_position == 'BELOW' and current_position_type == 'LONG':
    action = 'SELL_AND_SHORT'  # Close long, open short
elif no_position and macd_position == 'ABOVE':
    action = 'BUY'  # Initial long position
elif no_position and macd_position == 'BELOW':
    action = 'SHORT'  # Initial short position
```

## Critical File Relationships

### Entry Points
- **🚀 `quant_main.py`** - **RECOMMENDED**: Enhanced main entry point with IBKR/Alpaca unified system + legacy mode
- **🆕 `test_ibkr_connection.py`** - Test IBKR TWS connection and setup
- **🆕 `demo_broker_switching.py`** - Demonstrate broker switching capabilities
- `integrated_macd_trader.py` - Specialized real-time MACD system
- `trading_agent_main.py` - AI agent system
- `cli/main.py` - Interactive AI agent interface

### Strategy Implementation
- `strategies.py` - Base strategy classes and MACD implementation
- `MACD_option_trading/macd_options_strategy.py` - Options-specific MACD adaptation
- `tradingagents/agents/analysts/technical_analyst.py` - AI technical analysis

### Data Integration
- **🆕 `broker_selector.py`** - **NEW**: Unified broker selection and management
- **🆕 `ibkr_trading_system.py`** - **NEW**: IBKR TWS API integration
- `quote_monitor_selector.py` - Legacy automatic data source selection
- `enhanced_quote_monitor.py` - Real-time Alpaca quotes
- `yahoo_quote_monitor.py` - Yahoo Finance fallback
- `tradingagents/dataflows/` - AI agent data sources

### Risk and Execution
- **🚀 `quant_main.py`** - **ENHANCED**: Main execution with IBKR/Alpaca unified system + legacy mode
- **🆕 `broker_selector.py:place_market_order()`** - **NEW**: Multi-broker order placement
- `tradingagents/agents/risk_mgmt/` - AI risk assessment agents
- `MACD_option_trading/options_trader.py` - Options execution engine

## Memory and Persistence

### Quantitative System
- Strategy states: `strategy_state/{SYMBOL}_{STRATEGY}.json`
- Data cache: `data_cache/{SYMBOL}_{DATE_RANGE}.csv`
- Trading logs: `trading.log`, `integrated_trading.log`

### AI Agent System  
- Agent memory: `tradingagents/agents/utils/memory.py`
- Results: `results/{SYMBOL}/{DATE}/reports/`
- Graphiti MCP: Neo4j-based persistent memory (optional)

## Integration Patterns

### Hybrid Decision Making
```python
# Use AI agents for market analysis
ai_decision = ta.propagate("NVDA", "2024-05-10")

# Use quantitative signals for execution timing
signals = macd_strategy.generate_signals(market_data)

# Combine for enhanced trading
if ai_decision['recommendation'] == 'BUY' and signals['action'] == 'BUY':
    execute_trade('NVDA', 'BUY', enhanced_confidence=True)
```

### Data Source Redundancy (🆕 UPDATED)
```python
# 🆕 NEW: Yahoo Finance primary with broker fallback
def get_realtime_data(symbol):
    # Try Yahoo Finance first (PRIMARY)
    try:
        quote_data = yahoo_finance.get_latest_quote(symbol)
        return quote_data
    except Exception:
        # Fall back to broker APIs (IBKR/Alpaca)
        return broker_client.get_latest_quotes(symbol)

# Historical data with same priority
def get_historical_data(symbol):
    # Yahoo Finance first, then Alpaca, then cache
    return yahoo_finance.download(symbol) or alpaca_api.get_bars(symbol) or local_cache.get(symbol)
```

This architecture enables both systematic algorithmic trading and intelligent AI-driven market analysis, with robust risk management and execution capabilities across all market sessions.