#!/usr/bin/env python3
"""
Trend Agent
Measures: Trend strength, flow confirmation, momentum persistence

Score 0-1:
  0.0 = No trend / ranging
  0.5 = Mild trend
  1.0 = Strong trend with confirmed flow
"""

import sqlite3
import json
import os
from typing import Optional

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

class TrendAgent:
    """Measures trend strength and flow confirmation"""
    
    name = "trend"
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO agents (name, description) 
            VALUES ('trend', 'Measures trend strength and momentum')
        """)
        conn.commit()
        conn.close()
    
    def calculate_trend(self, symbol: str, timeframe: str, bar_time: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        
        bar = self._get_bar(conn, symbol, timeframe, bar_time)
        if not bar:
            conn.close()
            return {"score": 0.0, "error": "Bar not found", "components": {}}
        
        prev_bars = self._get_previous_bars(conn, symbol, timeframe, bar_time, 30)
        conn.close()
        
        components = {}
        
        # Component 1: Direction Consistency
        # How many bars in same direction
        direction_consistency = self._calc_direction_consistency(prev_bars)
        components["direction_consistency"] = direction_consistency
        
        # Component 2: Range Expansion
        # Are ranges expanding in trend direction?
        range_expansion = self._calc_range_expansion(bar, prev_bars)
        components["range_expansion"] = range_expansion
        
        # Component 3: Delta Alignment
        # Delta consistent with price direction?
        delta_alignment = self._calc_delta_alignment(bar, prev_bars)
        components["delta_alignment"] = delta_alignment
        
        # Component 4: Momentum Persistence
        # Higher highs / lower lows or steady drift?
        momentum = self._calc_momentum_persistence(prev_bars)
        components["momentum_persistence"] = momentum
        
        weights = {
            "direction_consistency": 0.30,
            "range_expansion": 0.25,
            "delta_alignment": 0.25,
            "momentum_persistence": 0.20
        }
        
        score = sum(components[k] * weights[k] for k in weights)
        score = round(min(1.0, max(0.0, score)), 3)
        
        return {
            "score": score,
            "components": components,
            "interpretation": self._interpret(score, bar, prev_bars),
            "direction": self._get_direction(bar, prev_bars)
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
    
    def _calc_direction_consistency(self, prev_bars: list) -> float:
        """What % of recent bars move in same direction?"""
        if len(prev_bars) < 5:
            return 0.0
        
        # Look at last 10 bars
        recent = prev_bars[:10]
        directions = [1 if b["close"] > b["open"] else -1 for b in recent]
        
        # Count majority direction
        bullish = sum(1 for d in directions if d > 0)
        bearish = sum(1 for d in directions if d < 0)
        
        if bullish > bearish:
            consistency = bullish / len(directions)
            direction = "BULL"
        elif bearish > bullish:
            consistency = bearish / len(directions)
            direction = "BEAR"
        else:
            return 0.0
        
        # 70%+ same direction = strong
        if consistency >= 0.7:
            return consistency
        
        return 0.0
    
    def _calc_range_expansion(self, bar: dict, prev_bars: list) -> float:
        """Are ranges expanding (trend) or contracting (range)??"""
        if len(prev_bars) < 5:
            return 0.0
        
        current_range = bar["high"] - bar["low"]
        recent_ranges = [b["high"] - b["low"] for b in prev_bars[:5]]
        older_ranges = [b["high"] - b["low"] for b in prev_bars[5:15]]
        
        if not recent_ranges or not older_ranges:
            return 0.0
        
        avg_recent = sum(recent_ranges) / len(recent_ranges)
        avg_older = sum(older_ranges) / len(older_ranges)
        
        # Trend: ranges expanding
        if avg_recent > avg_older * 1.3:
            return min(1.0, (avg_recent / avg_older - 1.0))
        
        # Range: ranges contracting
        return 0.0
    
    def _calc_delta_alignment(self, bar: dict, prev_bars: list) -> float:
        """Is delta confirming price direction?"""
        if len(prev_bars) < 3:
            return 0.0
        
        price_dir = 1 if bar["close"] > bar["open"] else -1
        delta_dir = 1 if (bar["delta"] or 0) > 0 else -1
        
        # Same direction = confirmed
        if price_dir == delta_dir:
            # Check consistency over last 5 bars
            aligned = 0
            for b in prev_bars[:5]:
                b_price_dir = 1 if b["close"] > b["open"] else -1
                b_delta_dir = 1 if (b["delta"] or 0) > 0 else -1
                if b_price_dir == b_delta_dir:
                    aligned += 1
            
            return aligned / 5.0
        
        return 0.0
    
    def _calc_momentum_persistence(self, prev_bars: list) -> float:
        """Higher highs/lows or steady drift?"""
        if len(prev_bars) < 5:
            return 0.0
        
        recent = prev_bars[:5]
        
        # Check for higher highs (uptrend) or lower lows (downtrend)
        highs = [b["high"] for b in recent]
        lows = [b["low"] for b in recent]
        
        # Uptrend: each high higher than previous
        higher_highs = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        lower_lows = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])
        
        if higher_highs >= 3:
            return higher_highs / 5.0
        elif lower_lows >= 3:
            return lower_lows / 5.0
        
        return 0.0
    
    def _get_direction(self, bar: dict, prev_bars: list) -> str:
        if len(prev_bars) < 5:
            return "NEUTRAL"
        
        recent = prev_bars[:5]
        bullish = sum(1 for b in recent if b["close"] > b["open"])
        
        if bullish >= 4:
            return "BULLISH"
        elif bullish <= 1:
            return "BEARISH"
        return "NEUTRAL"
    
    def _interpret(self, score: float, bar: dict, prev_bars: list) -> str:
        direction = self._get_direction(bar, prev_bars)
        
        if score >= 0.7:
            return f"STRONG {direction} TREND - Momentum confirmed"
        elif score >= 0.5:
            return f"{direction} TREND - Some momentum"
        elif score >= 0.3:
            return f"WEAK {direction} BIAS"
        else:
            return "RANGING - No trend"
    
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
            result = self.calculate_trend(symbol, timeframe, bar_time)
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
    parser = argparse.ArgumentParser(description="Trend Agent")
    parser.add_argument("--symbol", default="ES")
    parser.add_argument("--timeframe", default="1min")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--bar", help="Specific bar time")
    args = parser.parse_args()
    
    agent = TrendAgent()
    
    if args.scan:
        results = agent.score_all_bars(args.symbol, args.timeframe)
        print(f"\nTrend Analysis: {args.symbol} {args.timeframe}")
        print("=" * 60)
        for r in results[-15:]:
            print(f"{r['bar_time']}: {r['score']:.3f} {r['direction']}")
            print(f"  {r['interpretation']}")
    
    elif args.bar:
        result = agent.calculate_trend(args.symbol, args.timeframe, args.bar)
        print(f"\nTrend Score: {args.bar}")
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
