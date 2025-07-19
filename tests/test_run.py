#!/usr/bin/env python3
"""Quick test to ensure the trading agent works correctly."""

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

def test_trading_agent():
    """Test the trading agent with a simple example."""
    try:
        # Create the trading agent
        ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
        
        # Test with a simple stock and date
        print("Testing TradingAgents with NVDA...")
        _, decision = ta.propagate("NVDA", "2024-05-10")
        
        print(f"Trading decision: {decision}")
        print("✅ TradingAgents test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        raise

if __name__ == "__main__":
    test_trading_agent()