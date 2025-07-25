# AItrade: Advanced AI-Powered Trading Framework

<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

A comprehensive trading platform that combines quantitative analysis with AI-driven decision making. This integrated framework merges technical analysis automation with multi-agent AI collaboration for sophisticated trading strategies.

## 🎯 **NEW: IBKR TWS API Integration**

**Major Update**: Now supports **Interactive Brokers TWS API** as the primary broker with **automatic fallback to Alpaca**. This provides professional-grade trading capabilities with lower costs and enhanced features.

### Broker Priority System
1. **🥇 Primary**: IBKR TWS API (professional features, lower costs)
2. **🥈 Fallback**: Alpaca API (reliable backup)
3. **🔄 Manual Switching**: Switch between brokers anytime

## 🚀 Key Features

### Quantitative Trading Engine
- **🏆 Dual-broker architecture**: IBKR TWS API (primary) + Alpaca API (fallback)
- **Real-time MACD-based trading** with live market data streams
- **Professional-grade execution** with Interactive Brokers integration
- **Dual-mode architecture**: Stock trading and sophisticated options trading
- **Multiple data sources**: IBKR, Alpaca API, with Yahoo Finance fallback
- **Advanced risk management** with position sizing and portfolio limits
- **Extended hours trading** support (pre-market, after-hours, overnight)
- **Real-time monitoring** with terminal and web-based interfaces
- **Manual broker switching** with seamless failover capabilities

### Multi-Agent AI Framework
- **Collaborative agent system** mimicking real-world trading firms
- **Specialized AI agents**: Fundamentals, sentiment, news, and technical analysts
- **Dynamic research team**: Bull and bear researchers engaging in structured debates
- **Risk management team**: Comprehensive portfolio evaluation and decision approval
- **LLM-powered insights**: Using OpenAI GPT models for deep market analysis

## 🏗️ System Architecture

### Quantitative Trading Components (`/`)
- **🚀 `quant_main.py`** - **ENHANCED**: Main entry point with IBKR primary/Alpaca fallback + legacy mode
- **🆕 `broker_selector.py`** - **NEW**: Intelligent broker selection and switching
- **🆕 `ibkr_trading_system.py`** - **NEW**: IBKR TWS API integration
- `integrated_macd_trader.py` - Complete real-time MACD trading system
- `strategies.py` - Technical analysis strategies library
- `enhanced_quote_monitor.py` - Real-time quote monitoring
- `MACD_option_trading/` - Sophisticated options trading system

### AI Trading Agents (`tradingagents/`)
- `trading_agent_main.py` - Multi-agent system entry point
- `agents/analysts/` - Fundamental, sentiment, news, and technical analysts
- `agents/researchers/` - Bull and bear research teams
- `agents/risk_mgmt/` - Risk assessment and portfolio management
- `graph/trading_graph.py` - Agent coordination and decision flow

### Data Infrastructure
- `dataflows/` - Multi-source data integration (Yahoo Finance, FinnHub, Reddit)
- `data_cache/` - Historical data caching system
- `results/` - Trading decisions and analysis reports

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- **🆕 Interactive Brokers TWS/Gateway** (recommended - professional trading)
- Alpaca API account (backup broker)
- OpenAI API key (for AI agents)
- FinnHub API key (for AI market data)

### Installation

```bash
git clone <repository-url>
cd AItrade
pip install -r requirements.txt

# Install IBKR TWS API support
pip install ib_async
```

### Environment Setup

Create a `.env` file with your API credentials:

```env
# 🆕 IBKR TWS API (Primary Broker)
IBKR_HOST=127.0.0.1
IBKR_PORT=7497              # TWS: 7497 (paper), 7496 (live)
IBKR_CLIENT_ID=1            # Gateway: 4002 (paper), 4001 (live)

# Alpaca Trading API (Fallback Broker)
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_API_SECRET=your_alpaca_secret
PAPER_TRADING_URL=https://paper-api.alpaca.markets
PAPER_DATA_URL=https://data.alpaca.markets

# AI Agent APIs  
OPENAI_API_KEY=your_openai_api_key
FINNHUB_API_KEY=your_finnhub_api_key

# Trading Parameters
RISK_PER_TRADE=0.02
MAX_POSITIONS=5
EXTENDED_HOURS=True
OVERNIGHT_TRADING=True

# Broker Selection (AUTO, IBKR, ALPACA)
FORCE_BROKER=AUTO           # AUTO = IBKR first, then Alpaca
```

### 🆕 IBKR TWS Setup

1. **Download TWS/Gateway** from Interactive Brokers
2. **Enable API**: File → Global Configuration → API → Settings
3. **Configure Settings**:
   - ✅ Enable "Enable ActiveX and Socket Clients"
   - ✅ Add `127.0.0.1` to "Trusted IPs"
   - ✅ Check "Download open orders on connection"
   - Set Socket Port: `7497` (paper) or `7496` (live)
4. **Test Connection**:
   ```bash
   python tests/test_ibkr_connection.py
   ```

See [IBKR_SETUP.md](IBKR_SETUP.md) for detailed setup instructions.

## 🎯 Usage Examples

### 🚀 Enhanced Quantitative Trading (IBKR + Alpaca)

**Quick Test (Historical Data):**
```bash
python quant_main.py --mode historical --symbols NVDA AAPL
```

**Continuous Trading (IBKR Primary):**
```bash
python quant_main.py --mode continuous --interval 1 --symbols NVDA
```

**Force Specific Broker:**
```bash
python quant_main.py --broker ibkr --mode continuous     # Force IBKR
python quant_main.py --broker alpaca --mode historical   # Force Alpaca
python quant_main.py --broker legacy --mode continuous   # Legacy Alpaca-only
```

**Interactive Broker Switching:**
```bash
python quant_main.py --interactive --mode continuous
python demos/demo_broker_switching.py  # Demo switching capabilities
```

### Specialized Trading Systems

**Real-Time MACD Trading:**
```bash
python integrated_macd_trader.py --symbol NVDA --warmup 30 --interval 60 --shares 100
```

**Multi-Strategy Portfolio Trading:**
```bash
python quant_main.py --mode continuous --symbols AAPL MSFT NVDA --strategy macd --interval 5
```

**Options Trading with MACD:**
```bash
cd MACD_option_trading
python main.py
```

### AI-Powered Trading

**CLI Interface:**
```bash
python -m cli.main
```

**Python Integration:**
```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# Initialize AI trading system
ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# Get AI-powered trading decision
_, decision = ta.propagate("NVDA", "2024-05-10")
print(decision)
```

**Custom AI Configuration:**
```python
config = DEFAULT_CONFIG.copy()
config["deep_think_llm"] = "gpt-4o"
config["quick_think_llm"] = "gpt-4o-mini" 
config["max_debate_rounds"] = 3
config["online_tools"] = True

ta = TradingAgentsGraph(debug=True, config=config)
```

## 🤖 AI Agent System

### Analyst Team
- **Fundamentals Analyst**: Evaluates company financials and performance metrics
- **Sentiment Analyst**: Analyzes social media and public sentiment 
- **News Analyst**: Monitors global news and macroeconomic indicators
- **Technical Analyst**: Uses technical indicators for pattern recognition

### Research Team
- **Bull Researcher**: Advocates for bullish positions with detailed analysis
- **Bear Researcher**: Provides bearish counterarguments and risk assessment
- **Research Manager**: Coordinates research activities and synthesizes insights

### Risk Management
- **Portfolio Manager**: Makes final trading decisions based on comprehensive analysis
- **Risk Evaluators**: Assess market volatility, liquidity, and risk factors
- **Conservative/Aggressive Debators**: Provide balanced risk perspectives

## 📊 Trading Strategies

### MACD Strategy (Quantitative)
- **Components**: Fast EMA (13), Slow EMA (21), Signal line (9)
- **Entry Signals**: MACD crossover/crossunder events
- **Position Management**: Full-cycle trading (always long or short)
- **Risk Controls**: Time-based throttling, position mismatch handling

### AI-Enhanced Decision Making
- **Multi-perspective Analysis**: Combines technical, fundamental, and sentiment data
- **Collaborative Filtering**: Agent debates refine trading decisions
- **Dynamic Risk Assessment**: Real-time portfolio evaluation
- **Adaptive Strategies**: Learning from market conditions and performance

## 🔧 Configuration

### Quantitative Trading
```python
# strategies.py configuration
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
```

### AI Agent System
```python
# tradingagents/default_config.py
DEFAULT_CONFIG = {
    "deep_think_llm": "gpt-4o",
    "quick_think_llm": "gpt-4o-mini",
    "max_debate_rounds": 2,
    "online_tools": True,
    "research_depth": "standard"
}
```

## 📈 Performance Monitoring

### Real-Time Displays
- **Terminal Interface**: Live MACD signals and position tracking
- **Web Dashboard**: Browser-based monitoring at `http://localhost:5000`
- **Agent Reports**: Detailed analysis reports in `results/` directory

### Logging and Analytics
- **Trading Logs**: Complete transaction history and performance metrics
- **Agent Logs**: Decision-making process and reasoning chains
- **Risk Reports**: Portfolio exposure and risk assessment summaries

## 🔄 Integration Workflow

1. **Data Collection**: Multi-source market data aggregation
2. **Technical Analysis**: Quantitative signal generation
3. **AI Analysis**: Multi-agent collaborative decision making
4. **Risk Assessment**: Portfolio and position risk evaluation
5. **Decision Synthesis**: Combined quant + AI trading signals
6. **Execution**: Automated order placement and management
7. **Monitoring**: Real-time performance and risk tracking

## ⚠️ Risk Management

### Built-in Safeguards
- **Position Limits**: Maximum portfolio exposure controls
- **Time Throttling**: Prevents overtrading in volatile conditions
- **Extended Hours Controls**: Specialized handling for after-hours trading
- **Agent Consensus**: Multiple AI perspectives reduce single-point failures

### Compliance Features
- **Paper Trading Mode**: Safe testing environment with simulated funds
- **Audit Trails**: Complete logging of all decisions and trades
- **Risk Monitoring**: Continuous portfolio risk assessment
- **Emergency Controls**: Manual override capabilities

## 🚦 Deployment Modes

### Paper Trading (Recommended for Testing)
```env
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

### Live Trading (Production)
```env
ALPACA_BASE_URL=https://api.alpaca.markets
```

**⚠️ Important**: Always test thoroughly in paper mode before live deployment.

## 📚 Documentation

- **🆕 [IBKR TWS Setup Guide](IBKR_SETUP.md)** - Complete IBKR integration setup
- [Quantitative Trading Guide](DATA_SOURCES.md)
- [AI Agent Configuration](DEEPSEEK_INTEGRATION.md)
- [Claude MCP Integration](CLAUDE.md)
- [API Reference](cli/)

## 🔄 Broker Switching

The system automatically prioritizes brokers but allows manual control:

### Command Line Broker Selection
```bash
# Automatic (default): IBKR first, then Alpaca
python quant_main.py --mode continuous --symbols NVDA

# Force specific broker
python quant_main.py --broker ibkr --mode continuous      # Force IBKR only
python quant_main.py --broker alpaca --mode continuous    # Force Alpaca only
python quant_main.py --broker legacy --mode continuous    # Legacy Alpaca system

# Interactive switching during execution
python quant_main.py --interactive --mode continuous
```

### Programmatic Broker Control
```python
from broker_selector import UnifiedTradingSystem

# Automatic selection (IBKR first, Alpaca fallback)
system = UnifiedTradingSystem()  
print(f"Using: {system.get_broker_type()}")

# Check available brokers
available = system.get_available_brokers()  # ['IBKR', 'ALPACA']

# Switch manually
system.switch_to_broker("ALPACA")  # Switch to Alpaca
system.switch_to_broker("IBKR")    # Switch back to IBKR

# Interactive switching
system.interactive_switch()  # Prompts user to switch
```

### Environment-Based Forcing
```env
FORCE_BROKER=IBKR     # Force IBKR only
FORCE_BROKER=ALPACA   # Force Alpaca only
FORCE_BROKER=AUTO     # Default: IBKR first, Alpaca fallback
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Test thoroughly in paper trading mode
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 📄 Citation

If you use this framework in your research, please cite:

```bibtex
@misc{aitrade2025,
  title={AItrade: Advanced AI-Powered Trading Framework},
  author={Combined Quant Trading and TradingAgent Systems},
  year={2025},
  note={Integrated quantitative analysis with multi-agent AI decision making}
}
```

## ⚖️ Legal Disclaimer

**⚠️ Important**: This software is for educational and research purposes only. It is not financial advice. Trading involves significant risk of financial loss. Past performance does not guarantee future results. Use at your own risk and only with funds you can afford to lose.

## 📝 License

[MIT License](LICENSE)

---

**Built with**: Python, Alpaca API, OpenAI GPT, LangGraph, pandas, and modern trading infrastructure.