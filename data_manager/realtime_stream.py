#!/usr/bin/env python3
"""
Real-time Trading Data Stream - Phase 2
Streams live market data using async_rithmic library.
Calculates session levels (Asian/London/NY highs/lows) in real-time.
"""

import asyncio
import json
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional

# Configuration
CONFIG_DIR = "/tmp/trading-desk/config"
CREDENTIALS_FILE = f"{CONFIG_DIR}/rithmic_credentials.json"

@dataclass
class Tick:
    symbol: str
    exchange: str
    timestamp: datetime
    last: float
    bid: float
    ask: float
    volume: int

@dataclass
class SessionLevels:
    """Tracks session high/low for ICT methodology"""
    symbol: str
    asian_high: float = 0
    asian_low: float = float('inf')
    london_high: float = 0
    london_low: float = float('inf')
    ny_high: float = 0
    ny_low: float = float('inf')
    prev_day_high: float = 0
    prev_day_low: float = float('inf')
    
    def update(self, price: float, timestamp: datetime):
        """Update levels based on new tick"""
        hour = timestamp.hour
        
        # Asian: 0-7 UTC
        if hour < 7:
            if price > self.asian_high:
                self.asian_high = price
            if price < self.asian_low:
                self.asian_low = price
        
        # London: 7-12 UTC
        elif hour < 12:
            if price > self.london_high:
                self.london_high = price
            if price < self.london_low:
                self.london_low = price
        
        # NY: 12-20 UTC
        elif hour < 20:
            if price > self.ny_high:
                self.ny_high = price
            if price < self.ny_low:
                self.ny_low = price
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "asian_high": self.asian_high if self.asian_high > 0 else None,
            "asian_low": self.asian_low if self.asian_low < float('inf') else None,
            "london_high": self.london_high if self.london_high > 0 else None,
            "london_low": self.london_low if self.london_low < float('inf') else None,
            "ny_high": self.ny_high if self.ny_high > 0 else None,
            "ny_low": self.ny_low if self.ny_low < float('inf') else None,
        }

class TradingDataStream:
    """
    Real-time streaming market data using Rithmic.
    Calculates orderflow metrics and session levels.
    """
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.subscriptions: Dict[str, SessionLevels] = {}
        self.credentials = self._load_credentials()
        
    def _load_credentials(self) -> Optional[Dict]:
        """Load Rithmic credentials"""
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE) as f:
                return json.load(f)
        return None
    
    async def connect(self) -> bool:
        """Connect to Rithmic"""
        if not self.credentials:
            print("No Rithmic credentials found.")
            print(f"Add credentials to: {CREDENTIALS_FILE}")
            return False
        
        try:
            from async_rithmic import RithmicClient, DataType
            
            self.client = RithmicClient(
                login=self.credentials["login"],
                password=self.credentials["password"],
                system_name=self.credentials.get("system_name", "APEX RITHMIC SERVER")
            )
            
            print(f"Connecting to Rithmic as {self.credentials['login']}...")
            await self.client.connect()
            self.connected = True
            print("Connected!")
            return True
            
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    async def on_tick(self, data: dict):
        """Handle incoming tick data"""
        try:
            if data.get("data_type") == "LAST_TRADE":
                # Parse tick data
                tick = Tick(
                    symbol=data.get("security_code", ""),
                    exchange=data.get("exchange", ""),
                    timestamp=datetime.now(),
                    last=data.get("last_price", 0),
                    bid=data.get("bid_price", 0),
                    ask=data.get("ask_price", 0),
                    volume=data.get("last_volume", 0)
                )
                
                # Update session levels
                key = f"{tick.exchange}:{tick.symbol}"
                if key not in self.subscriptions:
                    self.subscriptions[key] = SessionLevels(symbol=tick.symbol)
                
                self.subscriptions[key].update(tick.last, tick.timestamp)
                
                # Print update every 10 ticks
                if tick.volume % 10 == 0:
                    levels = self.subscriptions[key]
                    print(f"[{tick.symbol}] Last: {tick.last} | "
                          f"Asian: H{levels.asian_high} L{levels.asian_low} | "
                          f"London: H{levels.london_high} L{levels.london_low} | "
                          f"NY: H{levels.ny_high} L{levels.ny_low}")
                        
        except Exception as e:
            print(f"Error processing tick: {e}")
    
    async def subscribe(self, symbols: list):
        """
        Subscribe to real-time data for symbols.
        symbols = [("6E", "CME"), ("GC", "COMEX"), ("MCL", "NYMEX")]
        """
        if not self.connected:
            print("Not connected to Rithmic")
            return
        
        from async_rithmic import DataType
        
        for symbol, exchange in symbols:
            await self.client.subscribe_to_market_data(
                security_code=symbol,
                exchange=exchange,
                data_type=DataType.LAST_TRADE | DataType.BBO
            )
            
            # Initialize session levels tracker
            key = f"{exchange}:{symbol}"
            self.subscriptions[key] = SessionLevels(symbol=symbol)
            print(f"Subscribed to {symbol} on {exchange}")
    
    async def get_historical_bars(self, symbol: str, exchange: str, 
                                   timeframe: str = "1min", count: int = 100):
        """Get historical bars"""
        if not self.connected:
            return []
        
        # Implementation for historical data
        # Would use client.request_historical_data() or similar
        pass
    
    async def disconnect(self):
        """Disconnect from Rithmic"""
        if self.client and self.connected:
            await self.client.disconnect()
            self.connected = False
            print("Disconnected from Rithmic")


async def main():
    """Demo: Subscribe to a few instruments"""
    stream = TradingDataStream()
    
    if not await stream.connect():
        print("\nCannot connect without credentials.")
        print("This is expected if Rithmic credentials aren't configured.")
        print("\nTo enable live data:")
        print(f"1. Edit: {CREDENTIALS_FILE}")
        print("2. Add your Apex/Rithmic login credentials")
        print("3. Restart the data stream")
        return
    
    # Richard's main instruments
    instruments = [
        ("6E", "CME"),   # Euro
        ("6B", "CME"),   # GBP
        ("GC", "COMEX"), # Gold
        ("MCL", "NYMEX"),# Crude
        ("MES", "CME"),  # S&P
    ]
    
    await stream.subscribe(instruments)
    
    # Keep running for 60 seconds
    print("\nStreaming for 60 seconds...")
    await asyncio.sleep(60)
    
    # Print final levels
    print("\n" + "="*60)
    print("SESSION LEVELS SUMMARY")
    print("="*60)
    for key, levels in stream.subscriptions.items():
        print(f"\n{levels.symbol}:")
        print(json.dumps(levels.to_dict(), indent=2))
    
    await stream.disconnect()


if __name__ == "__main__":
    print("Starting Real-time Trading Data Stream...")
    print("Note: Requires Rithmic credentials from Apex Trader Funding")
    asyncio.run(main())
