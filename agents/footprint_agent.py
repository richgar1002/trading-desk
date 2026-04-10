#!/usr/bin/env python3
"""
Footprint Agent
Records and analyzes: Volume at price levels, bid/ask distribution
Not a score but a snapshot of the orderbook imbalance per bar

Key metrics:
- Bid/Ask ratio at each level
- Imbalance magnitude
- Large orders detected
"""

import sqlite3
import json
import os
from typing import Optional

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

class FootprintAgent:
    """Analyzes footprint (price-level volume) data"""
    
    name = "footprint"
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO agents (name, description) 
            VALUES ('footprint', 'Analyzes volume at price levels')
        """)
        conn.commit()
        conn.close()
    
    def analyze_footprint(self, symbol: str, timeframe: str, bar_time: str) -> dict:
        """Analyze footprint for a specific bar"""
        conn = sqlite3.connect(self.db_path)
        
        # Get footprint data
        cursor = conn.execute("""
            SELECT price, bid_vol, ask_vol, total_vol
            FROM raw_footprint
            WHERE symbol = ? AND timeframe = ? AND bar_time = ?
            ORDER BY price
        """, (symbol, timeframe, bar_time))
        rows = cursor.fetchall()
        
        # Get bar info
        bar_cursor = conn.execute("""
            SELECT bar_time, open, high, low, close, volume, delta
            FROM bars WHERE symbol = ? AND timeframe = ? AND bar_time = ?
        """, (symbol, timeframe, bar_time))
        bar_row = bar_cursor.fetchone()
        conn.close()
        
        if not rows and not bar_row:
            return {"error": "No data found"}
        
        if not rows:
            # No footprint, estimate from bar
            return self._estimate_from_bar(bar_row)
        
        # Analyze actual footprint
        return self._analyze(rows, bar_row)
    
    def _analyze(self, footprint_rows: list, bar_row: tuple) -> dict:
        """Analyze footprint data"""
        bar_time, open_, high, low, close, volume, delta = bar_row
        
        # Convert to dict
        footprint = [{"price": r[0], "bid_vol": r[1], "ask_vol": r[2], "total_vol": r[3]} for r in footprint_rows]
        
        # Find key levels
        max_bid_level = max(footprint, key=lambda x: x["bid_vol"])["price"]
        max_ask_level = max(footprint, key=lambda x: x["ask_vol"])["price"]
        max_total_level = max(footprint, key=lambda x: x["total_vol"])["price"]
        
        # Calculate imbalance
        total_bid = sum(f["bid_vol"] for f in footprint)
        total_ask = sum(f["ask_vol"] for f in footprint)
        
        imbalance = self._calc_imbalance(total_bid, total_ask)
        
        # Check for large orders (levels with >20% of total volume)
        threshold = sum(f["total_vol"] for f in footprint) * 0.20
        large_levels = [f for f in footprint if f["total_vol"] > threshold]
        
        # Delta at key levels
        delta_at_max_bid = next((f["bid_vol"] - f["ask_vol"] for f in footprint if f["price"] == max_bid_level), 0)
        delta_at_max_ask = next((f["bid_vol"] - f["ask_vol"] for f in footprint if f["price"] == max_ask_level), 0)
        
        # Direction
        direction = "BULLISH" if (delta or 0) > 0 else "BEARISH" if (delta or 0) < 0 else "NEUTRAL"
        
        return {
            "symbol": "ES",
            "timeframe": "1min",
            "bar_time": bar_time,
            "imbalance": round(imbalance, 3),
            "imbalance_direction": "BID" if total_bid > total_ask else "ASK" if total_ask > total_bid else "BALANCED",
            "max_bid_level": max_bid_level,
            "max_ask_level": max_ask_level,
            "max_volume_level": max_total_level,
            "delta_at_max_bid": delta_at_max_bid,
            "delta_at_max_ask": delta_at_max_ask,
            "large_levels_count": len(large_levels),
            "total_volume": sum(f["total_vol"] for f in footprint),
            "direction": direction,
            "interpretation": self._interpret(imbalance, direction, large_levels),
            "components": {
                "bid_dominance": round(total_bid / (total_bid + total_ask), 3) if (total_bid + total_ask) > 0 else 0.5,
                "ask_dominance": round(total_ask / (total_bid + total_ask), 3) if (total_bid + total_ask) > 0 else 0.5,
                "large_orders": len(large_levels)
            }
        }
    
    def _estimate_from_bar(self, bar_row: tuple) -> dict:
        """Estimate footprint metrics from bar when no raw footprint"""
        bar_time, open_, high, low, close, volume, delta = bar_row
        
        # Can't do real footprint analysis without raw data
        return {
            "symbol": "ES",
            "timeframe": "1min",
            "bar_time": bar_time,
            "imbalance": 0.0,
            "imbalance_direction": "NO_DATA",
            "max_bid_level": high,
            "max_ask_level": low,
            "max_volume_level": close,
            "delta_at_max_bid": 0,
            "delta_at_max_ask": 0,
            "large_levels_count": 0,
            "total_volume": volume or 0,
            "direction": "BULLISH" if (delta or 0) > 0 else "BEARISH" if (delta or 0) < 0 else "NEUTRAL",
            "interpretation": "No footprint data - import levels CSV for detailed analysis",
            "estimated": True,
            "components": {}
        }
    
    def _calc_imbalance(self, total_bid: int, total_ask: int) -> float:
        """Calculate imbalance ratio -1 to 1"""
        if total_bid + total_ask == 0:
            return 0.0
        
        # (Bid - Ask) / (Bid + Ask)
        return (total_bid - total_ask) / (total_bid + total_ask)
    
    def _interpret(self, imbalance: float, direction: str, large_levels: list) -> str:
        abs_imb = abs(imbalance)
        
        if abs_imb > 0.7:
            strength = "EXTREME"
        elif abs_imb > 0.5:
            strength = "STRONG"
        elif abs_imb > 0.3:
            strength = "MODERATE"
        else:
            strength = "SLIGHT"
        
        side = "BID" if imbalance > 0 else "ASK"
        
        if large_levels:
            return f"{strength} {side} IMBALANCE - Large orders at {len(large_levels)} levels"
        
        return f"{strength} {side} IMBALANCE - {side} {'absorption' if direction == 'BULLISH' and side == 'ASK' else 'selling' if direction == 'BEARISH' and side == 'BID' else 'pressure'}"
    
    def score_all_bars(self, symbol: str, timeframe: str) -> list:
        """Analyze all bars with footprint data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT DISTINCT bar_time FROM raw_footprint
            WHERE symbol = ? AND timeframe = ? ORDER BY bar_time
        """, (symbol, timeframe))
        bar_times = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        results = []
        for bar_time in bar_times:
            result = self.analyze_footprint(symbol, timeframe, bar_time)
            results.append(result)
        
        return results
    
    def get_latest_footprint(self, symbol: str, timeframe: str) -> Optional[dict]:
        """Get most recent footprint analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT bar_time FROM raw_footprint
            WHERE symbol = ? AND timeframe = ?
            ORDER BY bar_time DESC LIMIT 1
        """, (symbol, timeframe))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self.analyze_footprint(symbol, timeframe, row[0])


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Footprint Agent")
    parser.add_argument("--symbol", default="ES")
    parser.add_argument("--timeframe", default="1min")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--bar", help="Specific bar time")
    args = parser.parse_args()
    
    agent = FootprintAgent()
    
    if args.scan:
        results = agent.score_all_bars(args.symbol, args.timeframe)
        print(f"\nFootprint Analysis: {args.symbol} {args.timeframe}")
        print("=" * 80)
        for r in results[-15:]:
            est = " (est)" if r.get("estimated") else ""
            print(f"{r['bar_time']}: Imb={r['imbalance']:.2f} {r['imbalance_direction']} {r['direction']}{est}")
            print(f"  MaxVol={r['max_volume_level']} LargeLvl={r['large_levels_count']}")
            print(f"  {r['interpretation']}")
    
    elif args.bar:
        result = agent.analyze_footprint(args.symbol, args.timeframe, args.bar)
        print(f"\nFootprint: {args.bar}")
        print(f"Imbalance: {result.get('imbalance')} ({result.get('imbalance_direction')})")
        print(f"Direction: {result.get('direction')}")
        print(f"Max Volume Level: {result.get('max_volume_level')}")
        print(f"Max Bid Level: {result.get('max_bid_level')}")
        print(f"Max Ask Level: {result.get('max_ask_level')}")
        print(f"Large Orders: {result.get('large_levels_count')} levels")
        print(f"Interpretation: {result.get('interpretation')}")
    
    else:
        latest = agent.get_latest_footprint(args.symbol, args.timeframe)
        if latest:
            print(f"\nLatest: {latest['bar_time']}")
            print(f"Imbalance: {latest['imbalance']:.2f} {latest['imbalance_direction']}")
            print(f"Direction: {latest['direction']}")
            print(f"Interpretation: {latest['interpretation']}")
        else:
            print("No footprint data. Import levels CSV.")


if __name__ == "__main__":
    main()
