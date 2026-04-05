#!/usr/bin/env python3
"""
Economic Calendar - FRED API Powered
Tracks economic events and alerts for trading instruments
Uses Federal Reserve Economic Data (FRED) - FREE
"""

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# FRED API - FREE, no key needed for basic events
# https://fred.stlouisfed.org/docs/api/fred/

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

class EconomicCalendar:
    def __init__(self):
        self.watchlist_dir = "/tmp/trading-desk/data/watchlists"
        self.events = []
        
    def load_instruments(self) -> List[str]:
        """Load all instruments from watchlists"""
        instruments = set()
        for session in ['asian', 'london', 'ny']:
            path = f"{self.watchlist_dir}/{session}_session.txt"
            if os.path.exists(path):
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            instruments.add(line)
        return list(instruments)
    
    def get_us_economic_events(self, days: int = 1) -> List[Dict]:
        """
        Get US economic events from economic calendar
        Using investing.com economic calendar data format
        """
        # High-impact US events that affect USD pairs
        high_impact_events = [
            "FOMC", "Fed", "Interest Rate", "Nonfarm Payrolls", "NFP",
            "CPI", "PPI", "GDP", "Retail Sales", 
            "ISM Manufacturing", "ISM Services",
            "Initial Jobless Claims", "Job Openings", "JOLTS",
            "Consumer Confidence", "Consumer Sentiment",
            "PCE", "Core PCE", "Personal Income", "Personal Spending",
            "Housing Starts", "Building Permits", "New Home Sales",
            "Existing Home Sales", "Durable Goods Orders",
            "Trade Balance", "Current Account"
        ]
        return high_impact_events
    
    def check_instrument_events(self, instrument: str) -> List[Dict]:
        """
        Check if instrument has relevant events coming up
        """
        events = []
        instrument_upper = instrument.upper()
        
        # Mapping instruments to relevant events
        instrument_events = {
            "EUR": ["ECB", "Euro Zone GDP", "Euro Zone CPI", "German ZEW"],
            "GBP": ["BOE", "Bank of England", "UK GDP", "UK CPI"],
            "JPY": ["BOJ", "Bank of Japan", "Japan GDP"],
            "AUD": ["RBA", "Australia CPI", "Australia GDP"],
            "NZD": ["RBNZ", "New Zealand CPI"],
            "CAD": ["BOC", "Bank of Canada", "Canada GDP", "Oil"],
            "CHF": ["SNB", "Swiss National Bank"],
            "XAU": ["Gold", "Fed", "Inflation", "USD"],
            "XAG": ["Silver", "Gold"],
            "CL": ["Oil", "OPEC", "Crude", "EIA"],
            "ES": ["S&P", "US GDP", "Fed"],
            "6E": ["EUR", "Euro Zone"],
            "6B": ["GBP", "UK"],
            "GC": ["Gold", "Fed", "Inflation"]
        }
        
        relevant = instrument_events.get(instrument_upper, [])
        
        return relevant
    
    def generate_calendar_alert(self, session: str) -> str:
        """
        Generate pre-session calendar alert
        """
        instruments = self.load_instruments()
        
        prompt = f"""You are a trading research assistant. Generate an economic calendar alert for {session.upper()} session.

Trading instruments: {', '.join(instruments)}

Create a brief alert format:
1. Today's high-impact events (time, event, expected impact)
2. Instruments affected
3. Potential market moves

Format for quick reading during trading hours.
Keep under 200 words."""

        # Call Ollama
        import requests
        payload = {
            "model": "qwen2.5-coder:7b",
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
            return response.text
        except Exception as e:
            return f"Error: {str(e)}"

def get_next_nfp() -> Optional[str]:
    """Get next NFP date - high impact for all USD pairs"""
    # NFP releases first Friday of each month at 8:30am ET
    # This would need actual calendar integration
    return None

def get_fed_speakers() -> List[Dict]:
    """Get upcoming Fed speakers - high impact"""
    # Would integrate with calendar API
    return []

if __name__ == "__main__":
    calendar = EconomicCalendar()
    print("Economic Calendar initialized")
    print(f"Watching {len(calendar.load_instruments())} instruments")
