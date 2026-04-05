#!/usr/bin/env python3
"""
Trading Data Manager - Phase 2
Unified interface for trading data from multiple sources:
1. Quantower CSV exports (free, no credentials)
2. Rithmic async API (when credentials available via Apex)

Richard's Instruments:
- Forex: 6E (EUR), 6B (GBP), 6J (JPY), 6A (AUD), 6N (NZD)
- Indices: MES, MNQ, MYM
- Energy: MCL (WTI Crude), NG (Natural Gas), BZ (Brent)
- Metals: GC (Gold), MGC (Micro Gold), SI (Silver)
"""

import os
import csv
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

# Configuration
DATA_DIR = "/tmp/trading-desk/data"
QUANTOWER_EXPORT_DIR = os.path.expanduser("~/Quantower/Exports")
RITHMIC_CREDENTIALS_FILE = "/tmp/trading-desk/config/rithmic_credentials.json"

@dataclass
class Tick:
    timestamp: datetime
    symbol: str
    last: float
    bid: float
    ask: float
    volume: int
    
@dataclass  
class Bar:
    timestamp: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int

class QuantowerDataManager:
    """
    Handles data from Quantower History Exporter CSV files.
    No API needed - just point to the export directory.
    """
    
    def __init__(self, export_dir: str = QUANTOWER_EXPORT_DIR):
        self.export_dir = export_dir
        
    def parse_csv_file(self, filepath: str) -> List[Bar]:
        """Parse Quantower exported CSV file"""
        bars = []
        if not os.path.exists(filepath):
            return bars
            
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    bar = Bar(
                        timestamp=datetime.fromisoformat(row['Time']),
                        symbol=row.get('Symbol', 'UNKNOWN'),
                        timeframe=row.get('Timeframe', '1min'),
                        open=float(row['Open']),
                        high=float(row['High']),
                        low=float(row['Low']),
                        close=float(row['Close']),
                        volume=int(row.get('Volume', 0))
                    )
                    bars.append(bar)
                except (ValueError, KeyError) as e:
                    continue  # Skip malformed rows
        return bars
    
    def get_latest_bars(self, symbol: str, timeframe: str = "1min", count: int = 100) -> List[Bar]:
        """
        Get latest bars for a symbol from CSV.
        Assumes naming convention: {symbol}_{timeframe}.csv
        """
        filename = f"{symbol.upper()}_{timeframe}.csv"
        filepath = os.path.join(self.export_dir, filename)
        
        bars = self.parse_csv_file(filepath)
        return bars[-count:] if len(bars) > count else bars
    
    def get_daily_range(self, symbol: str, date: datetime = None) -> Dict:
        """Get high/low for a symbol on a specific date"""
        if date is None:
            date = datetime.now()
            
        bars = self.get_latest_bars(symbol, "1min", count=1440)  # Full day
        
        day_bars = [b for b in bars if b.timestamp.date() == date.date()]
        
        if not day_bars:
            return {"high": None, "low": None, "range": None}
            
        return {
            "high": max(b.high for b in day_bars),
            "low": min(b.low for b in day_bars),
            "range": max(b.high for b in day_bars) - min(b.low for b in day_bars)
        }


class RithmicDataManager:
    """
    Handles real-time and historical data from Rithmic API.
    Requires credentials from Apex Trader Funding.
    """
    
    def __init__(self, credentials_path: str = RITHMIC_CREDENTIALS_FILE):
        self.credentials_path = credentials_path
        self.credentials = None
        self.client = None
        self.connected = False
        
    def load_credentials(self) -> bool:
        """Load Rithmic credentials from file"""
        if not os.path.exists(self.credentials_path):
            print(f"Credentials file not found: {self.credentials_path}")
            print("Create it with your Apex/Rithmic login details")
            return False
            
        with open(self.credentials_path) as f:
            self.credentials = json.load(f)
        return True
    
    async def connect(self) -> bool:
        """Connect to Rithmic"""
        if not self.load_credentials():
            return False
            
        try:
            from async_rithmic import AsyncRithmicClient
            
            self.client = AsyncRithmicClient(
                login=self.credentials["login"],
                password=self.credentials["password"],
                system_name=self.credentials.get("system_name", "RITHMIC MOCK SERVER"),
                system_version="3.2"
            )
            
            await self.client.connect()
            self.connected = True
            print("Connected to Rithmic!")
            return True
        except Exception as e:
            print(f"Failed to connect to Rithmic: {e}")
            return False
    
    async def subscribe_ticks(self, symbol: str, exchange: str, callback):
        """Subscribe to real-time tick data"""
        if not self.connected:
            print("Not connected to Rithmic")
            return
            
        from async_rithmic import DataType
        
        self.client.on_tick += callback
        await self.client.subscribe_to_market_data(symbol, exchange, DataType.LAST_TRADE | DataType.BBO)
    
    async def get_historical_bars(self, symbol: str, exchange: str, 
                                   timeframe: str = "1min", 
                                   count: int = 100) -> List[Bar]:
        """Get historical bars"""
        # Implementation depends on Rithmic historical API
        pass


class TradingDataManager:
    """
    Unified interface combining all data sources.
    Use Quantower CSVs for historical, Rithmic for live when available.
    """
    
    def __init__(self):
        self.quantower = QuantowerDataManager()
        self.rithmic = RithmicDataManager()
        
    def setup_rithmic_credentials(self, login: str, password: str, system_name: str = "APEX RITHMIC SERVER"):
        """Save Rithmic credentials for future use"""
        os.makedirs(os.path.dirname(RITHMIC_CREDENTIALS_FILE), exist_ok=True)
        
        credentials = {
            "login": login,
            "password": password,
            "system_name": system_name
        }
        
        with open(RITHMIC_CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials, f, indent=2)
        
        print(f"Credentials saved to {RITHMIC_CREDENTIALS_FILE}")
        
    def get_session_levels(self, symbol: str, session_date: datetime = None) -> Dict:
        """
        Get key levels for a trading session:
        - Asian high/low
        - London high/low  
        - NY high/low
        - Previous day high/low
        """
        if session_date is None:
            session_date = datetime.now()
            
        # For now, use Quantower CSV data
        # When Rithmic is connected, use that for real-time
        
        levels = {
            "symbol": symbol,
            "date": session_date.strftime("%Y-%m-%d"),
            "asian_high": None,
            "asian_low": None,
            "london_high": None,
            "london_low": None,
            "ny_high": None,
            "ny_low": None,
            "prev_day_high": None,
            "prev_day_low": None,
        }
        
        # Try to get from Quantower CSV
        try:
            # Assuming 1-minute bars exported
            bars = self.quantower.get_latest_bars(symbol, "1min", 1440)
            
            for bar in bars:
                hour = bar.timestamp.hour
                
                # Asian: 0-7 UTC
                if hour < 7:
                    if levels["asian_high"] is None or bar.high > levels["asian_high"]:
                        levels["asian_high"] = bar.high
                    if levels["asian_low"] is None or bar.low < levels["asian_low"]:
                        levels["asian_low"] = bar.low
                
                # London: 7-12 UTC
                elif hour < 12:
                    if levels["london_high"] is None or bar.high > levels["london_high"]:
                        levels["london_high"] = bar.high
                    if levels["london_low"] is None or bar.low < levels["london_low"]:
                        levels["london_low"] = bar.low
                
                # NY: 12-20 UTC
                elif hour < 20:
                    if levels["ny_high"] is None or bar.high > levels["ny_high"]:
                        levels["ny_high"] = bar.high
                    if levels["ny_low"] is None or bar.low < levels["ny_low"]:
                        levels["ny_low"] = bar.low
                        
        except Exception as e:
            print(f"Error getting session levels: {e}")
            
        return levels


if __name__ == "__main__":
    manager = TradingDataManager()
    
    print("=" * 60)
    print("TRADING DATA MANAGER - Phase 2")
    print("=" * 60)
    
    print("\n1. Quantower Data:")
    print(f"   Export directory: {QUANTOWER_EXPORT_DIR}")
    print(f"   Directory exists: {os.path.exists(QUANTOWER_EXPORT_DIR)}")
    
    print("\n2. Rithmic Data:")
    print(f"   Credentials file: {RITHMIC_CREDENTIALS_FILE}")
    print(f"   Credentials exist: {os.path.exists(RITHMIC_CREDENTIALS_FILE)}")
    
    print("\n3. Supported Symbols:")
    symbols = ["6E", "6B", "6J", "6A", "6N", "MES", "MNQ", "MYM", 
               "MCL", "NG", "BZ", "GC", "MGC", "SI"]
    print(f"   {', '.join(symbols)}")
    
    print("\nNEXT STEPS:")
    print("1. Configure Quantower to export to:", QUANTOWER_EXPORT_DIR)
    print("2. Add Rithmic credentials when you have them from Apex")
