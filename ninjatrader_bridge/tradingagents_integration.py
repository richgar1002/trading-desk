#!/usr/bin/env python3
"""
TradingAgents + NinjaTrader Integration
========================================
Combines the TradingAgents multi-agent framework with NinjaTrader 8 data.
"""

import asyncio
import os
import sys
from datetime import date

# Add trading-desk to path
sys.path.insert(0, '/tmp/trading-agents')
sys.path.insert(0, '/tmp/trading-desk/ninjatrader_bridge')

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

from ninjatrader_bridge import NinjaTraderBridge
from ninjatrader_tools import initialize_bridge, get_quote, subscribe_instruments


class NinjaTraderTradingAgents:
    """
    Combined system: TradingAgents framework with NinjaTrader 8 data.
    """
    
    def __init__(self, api_token: str, model: str = "qwen2.5-coder:7b"):
        self.api_token = api_token
        self.model = model
        self.bridge = None
        self.ta = None
        
    async def initialize(self):
        """Initialize both the bridge and TradingAgents."""
        print("=" * 60)
        print("TradingAgents + NinjaTrader Integration")
        print("=" * 60)
        
        # Initialize NinjaTrader Bridge
        print("\n[1/3] Connecting to NinjaTrader 8...")
        self.bridge = NinjaTraderBridge(api_token=self.api_token)
        if await self.bridge.connect():
            print("  ✓ NinjaTrader connected")
        else:
            print("  ✗ NinjaTrader connection failed")
            return False
        
        # Subscribe to key instruments
        instruments = ["ES 06-26", "MNQ 06-26", "GC 06-26", "6E 06-26"]
        await self.bridge.subscribe(instruments)
        print(f"  ✓ Subscribed to {len(instruments)} instruments")
        
        # Initialize TradingAgents tools with bridge
        print("\n[2/3] Initializing TradingAgents...")
        initialize_bridge(self.bridge)
        
        # Configure TradingAgents to use Ollama
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = "ollama"
        config["deep_think_llm"] = self.model
        config["quick_think_llm"] = self.model
        config["backend_url"] = "http://localhost:11434/v1"
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        
        self.ta = TradingAgentsGraph(debug=False, config=config)
        print("  ✓ TradingAgents initialized")
        
        print("\n[3/3] Ready!")
        print("=" * 60)
        return True
    
    async def analyze_instrument(self, symbol: str, trade_date: str = None) -> dict:
        """
        Run TradingAgents analysis on an instrument using live NinjaTrader data.
        """
        if trade_date is None:
            trade_date = date.today().isoformat()
        
        print(f"\nAnalyzing {symbol} for {trade_date}...")
        
        # Get current quote from NinjaTrader
        quote = self.bridge.get_quote(symbol)
        if quote:
            print(f"  Current Quote: {symbol} @ {quote.last} (Bid: {quote.bid}, Ask: {quote.ask})")
        
        # Run TradingAgents analysis
        result, decision = self.ta.propagate(symbol, trade_date)
        
        return {
            "symbol": symbol,
            "trade_date": trade_date,
            "quote": quote.to_dict() if quote else None,
            "decision": decision,
            "full_result": result
        }
    
    async def run_session(self, instruments: list, session_type: str = "NY"):
        """
        Run analysis for a trading session.
        
        Args:
            instruments: List of symbols to analyze
            session_type: "ASIAN", "LONDON", or "NY"
        """
        print(f"\n{'=' * 60}")
        print(f"{session_type} Session Analysis")
        print(f"{'=' * 60}")
        
        results = []
        for symbol in instruments:
            try:
                result = await self.analyze_instrument(symbol)
                results.append(result)
                print(f"  → {symbol}: {result['decision']}")
            except Exception as e:
                print(f"  ✗ {symbol}: Error - {e}")
        
        return results
    
    async def close(self):
        """Clean shutdown."""
        if self.bridge:
            await self.bridge.disconnect()


async def main():
    """Main entry point."""
    import json
    
    # Configuration
    API_TOKEN = os.environ.get("CROSSTRADE_API_TOKEN", "YOUR_API_TOKEN_HERE")
    MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
    
    # Create integrated system
    system = NinjaTraderTradingAgents(api_token=API_TOKEN, model=MODEL)
    
    # Initialize
    if not await system.initialize():
        print("Initialization failed")
        return
    
    try:
        # Example: Analyze a few instruments
        instruments = ["ES 06-26", "MNQ 06-26"]
        results = await system.run_session(instruments, "NY")
        
        # Print summary
        print(f"\n{'=' * 60}")
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        for r in results:
            print(f"{r['symbol']}: {r['decision']}")
        
    finally:
        await system.close()


if __name__ == "__main__":
    asyncio.run(main())
