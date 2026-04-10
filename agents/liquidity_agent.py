#!/usr/bin/env python3
"""
Liquidity Agent
Measures: Stop runs, weak level sweeps, liquidity grabs

Score 0-1:
  0.0 = No liquidity grab detected
  0.5 = Potential liquidity grab
  1.0 = Clear stop run / liquidity grab

Liquidity = where stops are likely clustered
Stop runs = price moves quickly through levels where stops are likely
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

class LiquidityAgent:
    """Measures liquidity and stop run signals"""
    
    name = "liquidity"
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO agents (name, description) 
            VALUES ('liquidity', 'Measures stop runs and weak level sweeps')
        """)
        conn.commit()
        conn.close()
    
    def calculate_liquidity(self, symbol: str, timeframe: str, bar_time: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        
        bar = self._get_bar(conn, symbol, timeframe, bar_time)
        if not bar:
            conn.close()
            return {"score": 0.0, "error": "Bar not found", "components": {}}
        
        prev_bars = self._get_previous_bars(conn, symbol, timeframe, bar_time, 20)
        conn.close()
        
        components = {}
        
        # Component 1: Wick Penetration
        # Large wick that goes through prior levels
        wick_pen = self._calc_wick_penetration(bar, prev_bars)
        components["wick_penetration"] = wick_pen
        
        # Component 2: Velocity
        # Fast move through a level (stop run)
        velocity = self._calc_velocity(bar, prev_bars)
        components["velocity"] = velocity
        
        # Component 3: Weak Level Break
        # Price broke through a level that looked like support/resistance
        weak_break = self._calc_weak_level_break(bar, prev_bars)
        components["weak_level_break"] = weak_break
        
        # Component 4: Liquidity Grab Pattern
        # Bar closes back behind the level it broke
        liquidity_grab = self._calc_liquidity_grab(bar, prev_bars)
        components["liquidity_grab"] = liquidity_grab
        
        weights = {
            "wick_penetration": 0.25,
            "velocity": 0.30,
            "weak_level_break": 0.25,
            "liquidity_grab": 0.20
        }
        
        score = sum(components[k] * weights[k] for k in weights)
        score = round(min(1.0, max(0.0, score)), 3)
        
        return {
            "score": score,
            "components": components,
            "interpretation": self._interpret(score, bar, prev_bars),
            "direction": self._get_direction(bar)
        }
    
    def _get_bar(self, conn, symbol: str, timeframe: str, bar_time: str) -> Optional[dict]:
        cursor = conn.execute("""
            SELECT bar_time, open, high, low, close, volume, bid_vol, ask_vol, delta
            FROM bars WHERE symbol = ? AND timeframe = ? AND bar_time = ?
        """, (symbol, timeframe, bar_time))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "bar_time": row[0], "open": row[1], "high": row[2], "low": row[3],
            "close": row[4], "volume": row[5], "bid_vol": row[6], "ask_vol": row[7], "delta": row[8]
        }
    
    def _get_previous_bars(self, conn, symbol: str, timeframe: str, bar_time: str, count: int) -> list:
        cursor = conn.execute("""
            SELECT bar_time, open, high, low, close, volume, bid_vol, ask_vol, delta
            FROM bars WHERE symbol = ? AND timeframe = ? AND bar_time < ?
            ORDER BY bar_time DESC LIMIT ?
        """, (symbol, timeframe, bar_time, count))
        rows = cursor.fetchall()
        return [{
            "bar_time": r[0], "open": r[1], "high": r[2], "low": r[3],
            "close": r[4], "volume": r[5], "bid_vol": r[6], "ask_vol": r[7], "delta": r[8]
        } for r in rows]
    
    def _calc_wick_penetration(self, bar: dict, prev_bars: list) -> float:
        """
        Large wick that extends beyond prior bars' ranges
        Suggests a sweep of stops above/below
        """
        if len(prev_bars) < 3:
            return 0.0
        
        upper_wick = bar["high"] - max(bar["open"], bar["close"])
        lower_wick = min(bar["open"], bar["close"]) - bar["low"]
        
        # Get recent ranges
        recent_highs = [b["high"] for b in prev_bars[:5]]
        recent_lows = [b["low"] for b in prev_bars[:5]]
        
        max_recent_high = max(recent_highs)
        min_recent_low = min(recent_lows)
        
        # How far did wick extend beyond recent range?
        upper_exceed = bar["high"] - max_recent_high
        lower_exceed = min_recent_low - bar["low"]
        
        # Typical tick size for ES is 0.25
        tick = 0.25
        
        if upper_exceed > tick * 2:
            # Wick went above recent highs
            penetration_ratio = upper_exceed / (bar["high"] - bar["low"] + 0.01)
            return min(1.0, penetration_ratio)
        
        if lower_exceed > tick * 2:
            penetration_ratio = lower_exceed / (bar["high"] - bar["low"] + 0.01)
            return min(1.0, penetration_ratio)
        
        return 0.0
    
    def _calc_velocity(self, bar: dict, prev_bars: list) -> float:
        """
        Fast move relative to range
        Stop runs are characterized by quick, sharp moves
        """
        if len(prev_bars) < 3:
            return 0.0
        
        price_range = bar["high"] - bar["low"]
        if price_range == 0:
            return 0.0
        
        # Body as percentage of range
        body = abs(bar["close"] - bar["open"])
        if body == 0:
            body = price_range * 0.1  # Assume small body if no movement
        
        body_ratio = body / price_range
        
        # If body is >80% of range, it's a fast directional move
        # If body is <30% of range, lots of wick = slow grinding
        if body_ratio > 0.8:
            # Fast move - check if it exceeded prior ranges
            direction = 1 if bar["close"] > bar["open"] else -1
            
            if direction > 0:  # Up move
                recent_highs = [b["high"] for b in prev_bars[:3]]
                if bar["close"] > max(recent_highs) + 0.5:
                    return 0.7  # Fast break above
            else:  # Down move
                recent_lows = [b["low"] for b in prev_bars[:3]]
                if bar["close"] < min(recent_lows) - 0.5:
                    return 0.7  # Fast break below
            
            return 0.3  # Fast but not necessarily a stop run
        
        # Low body ratio = grinding, slow
        return 0.0
    
    def _calc_weak_level_break(self, bar: dict, prev_bars: list) -> float:
        """
        Broke through a level that had weak reaction before
        Weak level = price barely moved through it previously
        """
        if len(prev_bars) < 5:
            return 0.0
        
        direction = 1 if bar["delta"] > 0 else -1
        
        # Look for levels that were tested but held
        if direction > 0:  # Checking for upside break
            for b in prev_bars[:5]:
                if b["high"] > bar["high"]:
                    return 0.0  # Already broke above, not a weak break
        
        # Check if prior bars had small ranges (weak levels)
        small_range_bars = 0
        for b in prev_bars[3:8]:
            b_range = b["high"] - b["low"]
            if b_range < 1.0:  # Tight range = potential support/resistance
                small_range_bars += 1
        
        if small_range_bars >= 3:
            # Multiple small-range bars = weak zone
            # Now did price blast through it?
            if bar["high"] - bar["low"] > 3.0:  # Large range vs prior small ranges
                return 0.8
        
        return 0.0
    
    def _calc_liquidity_grab(self, bar: dict, prev_bars: list) -> float:
        """
        Liquidity grab = price sweeps a level, then reverses
        Classic stop run pattern: Wick extends, price closes back behind level
        """
        if len(prev_bars) < 2:
            return 0.0
        
        upper_wick = bar["high"] - max(bar["open"], bar["close"])
        lower_wick = min(bar["open"], bar["close"]) - bar["low"]
        body = abs(bar["close"] - bar["open"])
        
        if body == 0:
            return 0.0
        
        # Wick to body ratio
        wick_ratio = max(upper_wick, lower_wick) / body
        
        # Large wick vs body = potential grab
        if wick_ratio > 2.0:
            direction = 1 if bar["close"] > bar["open"] else -1
            
            if direction > 0:  # Bullish bar
                # Check if it grabbed below (lower wick was bigger)
                if lower_wick > upper_wick * 1.5:
                    # Grabbed below, reversed up
                    return min(1.0, wick_ratio / 4.0)
            else:  # Bearish bar
                # Check if it grabbed above (upper wick was bigger)
                if upper_wick > lower_wick * 1.5:
                    # Grabbed above, reversed down
                    return min(1.0, wick_ratio / 4.0)
        
        return 0.0
    
    def _get_direction(self, bar: dict) -> str:
        delta = bar["delta"] if bar["delta"] else 0
        if delta > 0:
            return "BUYING"
        elif delta < 0:
            return "SELLING"
        return "NEUTRAL"
    
    def _interpret(self, score: float, bar: dict, prev_bars: list) -> str:
        direction = self._get_direction(bar)
        
        if score >= 0.7:
            return f"LIQUIDITY GRAB - Stop run detected, potential reversal"
        elif score >= 0.5:
            return f"WEAK LEVEL BREAK - {'Above' if direction == 'BUYING' else 'Below'} liquidity taken"
        elif score >= 0.3:
            return f"SOME LIQUIDITY - {'Buying' if direction == 'BUYING' else 'Selling'} pressure"
        else:
            return "NO LIQUIDITY GRAB - No stop runs detected"
    
    def score_all_bars(self, symbol: str, timeframe: str) -> list:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT DISTINCT bar_time FROM bars
            WHERE symbol = ? AND timeframe = ? ORDER BY bar_time
        """, (symbol, timeframe))
        bar_times = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        results = []
        for bar_time in bar_times:
            result = self.calculate_liquidity(symbol, timeframe, bar_time)
            result["bar_time"] = bar_time
            result["symbol"] = symbol
            result["timeframe"] = timeframe
            results.append(result)
            self._save_score(result)
        
        return results
    
    def _save_score(self, result: dict):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO agent_scores 
            (symbol, timeframe, bar_time, agent_name, score, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            result.get("symbol"), result.get("timeframe"), result.get("bar_time"),
            self.name, result.get("score"),
            json.dumps({
                "components": result.get("components", {}),
                "direction": result.get("direction", "NEUTRAL")
            })
        ))
        conn.commit()
        conn.close()
    
    def get_latest_score(self, symbol: str, timeframe: str) -> Optional[dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT bar_time, score, details FROM agent_scores
            WHERE symbol = ? AND timeframe = ? AND agent_name = ?
            ORDER BY bar_time DESC LIMIT 1
        """, (symbol, timeframe, self.name))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        details = json.loads(row[2]) if row[2] else {}
        return {
            "bar_time": row[0], "score": row[1],
            "components": details.get("components", {}),
            "direction": details.get("direction", "NEUTRAL")
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Liquidity Agent")
    parser.add_argument("--symbol", default="ES")
    parser.add_argument("--timeframe", default="1min")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--bar", help="Specific bar time")
    args = parser.parse_args()
    
    agent = LiquidityAgent()
    
    if args.scan:
        results = agent.score_all_bars(args.symbol, args.timeframe)
        print(f"\nLiquidity Analysis: {args.symbol} {args.timeframe}")
        print("=" * 60)
        for r in results[-15:]:
            print(f"{r['bar_time']}: {r['score']:.3f} {r['direction']}")
            print(f"  {r['interpretation']}")
            if r['score'] > 0.3:
                print(f"  Components: {r['components']}")
    
    elif args.bar:
        result = agent.calculate_liquidity(args.symbol, args.timeframe, args.bar)
        print(f"\nLiquidity Score: {args.bar}")
        print(f"Score: {result['score']:.3f}")
        print(f"Direction: {result['direction']}")
        print(f"Interpretation: {result['interpretation']}")
        print(f"Components: {result['components']}")
    
    else:
        latest = agent.get_latest_score(args.symbol, args.timeframe)
        if latest:
            print(f"\nLatest: {latest['bar_time']} - {latest['score']:.3f} {latest['direction']}")
        else:
            print("No data. Use --scan")


if __name__ == "__main__":
    main()
