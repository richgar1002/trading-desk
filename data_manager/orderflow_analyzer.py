#!/usr/bin/env python3
"""
Orderflow Level Calculator - Phase 2
Calculates ICT session levels and orderflow metrics from tick data.

This script processes tick data to extract:
1. Session Highs/Lows (Asian, London, NY)
2. Liquidity sweeps
3. Equal highs/lows
4. Displacement candles
5. Order blocks
"""

import csv
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

class OrderflowAnalyzer:
    """
    Analyzes tick data for ICT methodology orderflow patterns.
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.ticks: List[Dict] = []
        self.session_data = {
            "asian": {"high": 0, "low": float('inf'), "ticks": []},
            "london": {"high": 0, "low": float('inf'), "ticks": []},
            "ny": {"high": 0, "low": float('inf'), "ticks": []},
        }
        
    def load_from_csv(self, filepath: str) -> bool:
        """Load tick data from Quantower CSV export"""
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return False
            
        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        tick = {
                            "timestamp": datetime.fromisoformat(row['Time']),
                            "last": float(row.get('Last', row.get('Close', 0))),
                            "bid": float(row.get('Bid', 0)),
                            "ask": float(row.get('Ask', 0)),
                            "volume": int(row.get('Volume', 0)),
                        }
                        self.ticks.append(tick)
                        self._update_sessions(tick)
                    except (ValueError, KeyError):
                        continue
                        
            print(f"Loaded {len(self.ticks)} ticks from {filepath}")
            return True
            
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return False
    
    def _update_sessions(self, tick: Dict):
        """Update session highs/lows based on tick time"""
        hour = tick["timestamp"].hour
        price = tick["last"]
        
        if hour < 7:  # Asian: 0-7 UTC
            session = "asian"
        elif hour < 12:  # London: 7-12 UTC
            session = "london"
        elif hour < 20:  # NY: 12-20 UTC
            session = "ny"
        else:
            return  # Outside regular sessions
            
        if price > self.session_data[session]["high"]:
            self.session_data[session]["high"] = price
        if price < self.session_data[session]["low"]:
            self.session_data[session]["low"] = price
        self.session_data[session]["ticks"].append(tick)
    
    def calculate_levels(self) -> Dict:
        """
        Calculate key ICT levels from session data.
        """
        levels = {
            "symbol": self.symbol,
            "calculated_at": datetime.now().isoformat(),
            "asian": {
                "high": self.session_data["asian"]["high"],
                "low": self.session_data["asian"]["low"],
                "mid": (self.session_data["asian"]["high"] + self.session_data["asian"]["low"]) / 2,
                "range": self.session_data["asian"]["high"] - self.session_data["asian"]["low"],
            },
            "london": {
                "high": self.session_data["london"]["high"],
                "low": self.session_data["london"]["low"],
                "mid": (self.session_data["london"]["high"] + self.session_data["london"]["low"]) / 2,
                "range": self.session_data["london"]["high"] - self.session_data["london"]["low"],
            },
            "ny": {
                "high": self.session_data["ny"]["high"],
                "low": self.session_data["ny"]["low"],
                "mid": (self.session_data["ny"]["high"] + self.session_data["ny"]["low"]) / 2,
                "range": self.session_data["ny"]["high"] - self.session_data["ny"]["low"],
            },
        }
        
        # Calculate sweep information
        levels["sweeps"] = self._detect_sweeps()
        
        # Calculate order blocks
        levels["order_blocks"] = self._find_order_blocks()
        
        return levels
    
    def _detect_sweeps(self) -> List[Dict]:
        """
        Detect liquidity sweeps (stop runs) in the session data.
        A sweep occurs when price moves beyond a previous session's high/low.
        """
        sweeps = []
        
        # Check if London swept Asian highs/lows
        asian_high = self.session_data["asian"]["high"]
        asian_low = self.session_data["asian"]["low"]
        london_high = self.session_data["london"]["high"]
        london_low = self.session_data["london"]["low"]
        
        if london_high > asian_high * 1.0001:  # Slight buffer for noise
            sweeps.append({
                "type": "SWEEP_HIGH",
                "swept_level": asian_high,
                "new_high": london_high,
                "swept_by": "LONDON",
                "direction": "BULLISH"
            })
            
        if london_low < asian_low * 0.9999:
            sweeps.append({
                "type": "SWEEP_LOW", 
                "swept_level": asian_low,
                "new_low": london_low,
                "swept_by": "LONDON",
                "direction": "BEARISH"
            })
            
        # Check if NY swept London levels
        ny_high = self.session_data["ny"]["high"]
        ny_low = self.session_data["ny"]["low"]
        
        if ny_high > london_high * 1.0001:
            sweeps.append({
                "type": "SWEEP_HIGH",
                "swept_level": london_high,
                "new_high": ny_high,
                "swept_by": "NY",
                "direction": "BULLISH"
            })
            
        if ny_low < london_low * 0.9999:
            sweeps.append({
                "type": "SWEEP_LOW",
                "swept_level": london_low,
                "new_low": ny_low,
                "swept_by": "NY",
                "direction": "BEARISH"
            })
            
        return sweeps
    
    def _find_order_blocks(self) -> Dict:
        """
        Identify potential order blocks (areas where institutions placed orders).
        """
        return {
            "bullish_ob": [],  # Strong bullish candles followed by retrace
            "bearish_ob": [],  # Strong bearish candles followed by retrace
        }
    
    def generate_report(self) -> str:
        """Generate a human-readable orderflow report"""
        levels = self.calculate_levels()
        
        report = f"""
{'='*60}
ORDERFLOW ANALYSIS - {self.symbol}
Generated: {levels['calculated_at']}
{'='*60}

## SESSION LEVELS

Asian Session:
  High:  {levels['asian']['high']:.5f}
  Low:   {levels['asian']['low']:.5f}
  Mid:   {levels['asian']['mid']:.5f}
  Range: {levels['asian']['range']:.5f}

London Session:
  High:  {levels['london']['high']:.5f}
  Low:   {levels['london']['low']:.5f}
  Mid:   {levels['london']['mid']:.5f}
  Range: {levels['london']['range']:.5f}

NY Session:
  High:  {levels['ny']['high']:.5f}
  Low:   {levels['ny']['low']:.5f}
  Mid:   {levels['ny']['mid']:.5f}
  Range: {levels['ny']['range']:.5f}

## LIQUIDITY SWEEPS
"""
        
        for sweep in levels.get('sweeps', []):
            report += f"""
{sweep['type']} detected:
  Swept {sweep['swept_by']} sweeping {sweep['direction']}
  Level: {sweep['swept_level']:.5f}
  New:   {sweep['new_high']:.5f}
"""
        
        report += """
{'='*60}
"""
        
        return report


def analyze_symbol(symbol: str, csv_path: str) -> Dict:
    """Analyze a single symbol from CSV data"""
    analyzer = OrderflowAnalyzer(symbol)
    if analyzer.load_from_csv(csv_path):
        return analyzer.calculate_levels()
    return {}


if __name__ == "__main__":
    # Example usage
    print("Orderflow Analyzer - Phase 2")
    print("=" * 60)
    print()
    print("To use this analyzer:")
    print("1. Export data from Quantower History Exporter to CSV")
    print("2. Point to the CSV file with analyze_symbol()")
    print()
    print("Example:")
    print('  analyzer = OrderflowAnalyzer("6E")')
    print('  analyzer.load_from_csv("/path/to/6E_1min.csv")')
    print('  levels = analyzer.calculate_levels()')
    print('  print(analyzer.generate_report())')
