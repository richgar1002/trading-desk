#!/usr/bin/env python3
"""
Absorption Agent
Measures: Large orders hitting, price stalling despite aggressive flow

Score 0-1:
  0.0 = No absorption (price moves with the flow)
  0.5 = Partial absorption (some stalling)
  1.0 = Full absorption (big orders hitting, price going nowhere)

Absorption vs Exhaustion:
  - Exhaustion: Buyers/sellers TRYING but can't move price (effort vs result)
  - Absorption: One side is GETTING HIT but price still doesn't move (passive is bigger)
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

class AbsorptionAgent:
    """Measures absorption signals in orderflow data"""
    
    name = "absorption"
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Ensure database and agents table has this agent"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO agents (name, description) 
            VALUES ('absorption', 'Measures large orders hitting, price stalling')
        """)
        conn.commit()
        conn.close()
    
    def calculate_absorption(self, symbol: str, timeframe: str, bar_time: str) -> dict:
        """
        Calculate absorption score for a specific bar.
        
        Returns dict with:
        - score: 0.0 to 1.0
        - components: breakdown of contributing factors
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get current bar data
        bar = self._get_bar(conn, symbol, timeframe, bar_time)
        if not bar:
            conn.close()
            return {"score": 0.0, "error": "Bar not found", "components": {}}
        
        # Get previous bars for comparison
        prev_bars = self._get_previous_bars(conn, symbol, timeframe, bar_time, 10)
        
        # Calculate components
        components = {}
        
        # Component 1: Delta Intensity vs Range
        # High delta but small range = absorption
        delta_intensity = self._calc_delta_intensity(bar, prev_bars)
        components["delta_intensity"] = delta_intensity
        
        # Component 2: Passive Volume Ratio
        # High passive volume (total - delta) vs active = wall absorbing
        passive_ratio = self._calc_passive_ratio(bar, prev_bars)
        components["passive_ratio"] = passive_ratio
        
        # Component 3: Price Stalling
        # Price stuck in narrow range despite volume
        stall_range = self._calc_stall_range(bar, prev_bars)
        components["stall_range"] = stall_range
        
        # Component 4: Consecutive Absorption
        # Multiple bars in a row of high delta, low movement
        consecutive = self._calc_consecutive_absorption(conn, symbol, timeframe, bar_time)
        components["consecutive_bars"] = consecutive
        
        # Weighted average
        weights = {
            "delta_intensity": 0.30,
            "passive_ratio": 0.25,
            "stall_range": 0.25,
            "consecutive_bars": 0.20
        }
        
        score = sum(components[k] * weights[k] for k in weights)
        score = round(min(1.0, max(0.0, score)), 3)
        
        conn.close()
        
        return {
            "score": score,
            "components": components,
            "interpretation": self._interpret(score),
            "direction": self._get_direction(bar)
        }
    
    def _get_bar(self, conn, symbol: str, timeframe: str, bar_time: str) -> Optional[dict]:
        """Get bar data"""
        cursor = conn.execute("""
            SELECT bar_time, open, high, low, close, volume, bid_vol, ask_vol, delta
            FROM bars
            WHERE symbol = ? AND timeframe = ? AND bar_time = ?
        """, (symbol, timeframe, bar_time))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "bar_time": row[0],
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
            "volume": row[5],
            "bid_vol": row[6],
            "ask_vol": row[7],
            "delta": row[8]
        }
    
    def _get_previous_bars(self, conn, symbol: str, timeframe: str, bar_time: str, count: int) -> list:
        """Get previous N bars"""
        cursor = conn.execute("""
            SELECT bar_time, open, high, low, close, volume, bid_vol, ask_vol, delta
            FROM bars
            WHERE symbol = ? AND timeframe = ? AND bar_time < ?
            ORDER BY bar_time DESC
            LIMIT ?
        """, (symbol, timeframe, bar_time, count))
        rows = cursor.fetchall()
        return [{
            "bar_time": r[0], "open": r[1], "high": r[2], "low": r[3],
            "close": r[4], "volume": r[5], "bid_vol": r[6], "ask_vol": r[7], "delta": r[8]
        } for r in rows]
    
    def _calc_delta_intensity(self, bar: dict, prev_bars: list) -> float:
        """
        Delta Intensity: How strong is the delta relative to range
        High delta / small range = absorption likely
        """
        delta = abs(bar["delta"]) if bar["delta"] else 0
        price_range = bar["high"] - bar["low"]
        
        if price_range == 0 or delta == 0:
            return 0.0
        
        # Get average delta and range
        avg_delta = sum(abs(b["delta"]) for b in prev_bars) / len(prev_bars) if prev_bars else delta
        avg_range = sum(b["high"] - b["low"] for b in prev_bars) / len(prev_bars) if prev_bars else price_range
        
        if avg_delta == 0 or avg_range == 0:
            return 0.0
        
        # Current bar's ratio
        current_ratio = (delta / price_range) if price_range > 0 else 0
        # Average ratio
        avg_ratio = (avg_delta / avg_range) if avg_range > 0 else 0
        
        # If current delta/range is much higher than average = absorption
        if current_ratio > 0 and avg_ratio > 0:
            ratio = current_ratio / avg_ratio
            if ratio > 1.5:  # 50% higher than average
                return min(1.0, (ratio - 1.0) / 2.0)
        
        return 0.0
    
    def _calc_passive_ratio(self, bar: dict, prev_bars: list) -> float:
        """
        Passive Ratio: passive volume vs active volume
        Passive = total - |delta|, Active = |delta|
        High passive ratio = big wall absorbing
        """
        volume = bar["volume"] if bar["volume"] > 0 else 1
        delta = abs(bar["delta"]) if bar["delta"] else 0
        
        # Passive volume (the wall)
        passive_vol = volume - delta
        passive_ratio = passive_vol / volume if volume > 0 else 0
        
        # Get average passive ratio
        avg_passive = 0.5  # baseline
        if prev_bars:
            ratios = []
            for b in prev_bars:
                vol = b["volume"] if b["volume"] > 0 else 1
                d = abs(b["delta"]) if b["delta"] else 0
                ratios.append((vol - d) / vol)
            avg_passive = sum(ratios) / len(ratios) if ratios else 0.5
        
        # If current passive ratio is significantly higher = absorption
        if passive_ratio > avg_passive + 0.1:
            excess = passive_ratio - avg_passive
            return min(1.0, excess * 3)
        
        return 0.0
    
    def _calc_stall_range(self, bar: dict, prev_bars: list) -> float:
        """
        Stall Range: How narrow is price range relative to volume
        High volume + narrow range = absorption
        """
        price_range = bar["high"] - bar["low"]
        volume = bar["volume"] if bar["volume"] > 0 else 1
        
        if price_range == 0:
            return 1.0  # Complete stall
        
        # Points per volume (should be higher if absorbing)
        ppv = price_range / volume
        
        # Compare to previous bars
        if prev_bars:
            avg_ppv = sum((b["high"] - b["low"]) / (b["volume"] if b["volume"] > 0 else 1) for b in prev_bars) / len(prev_bars)
            if avg_ppv > 0:
                ratio = avg_ppv / ppv if ppv > 0 else 0
                if ratio > 2.0:  # Range is less than half of average
                    return min(1.0, (ratio - 1.0) / 3.0)
        
        return 0.0
    
    def _calc_consecutive_absorption(self, conn, symbol: str, timeframe: str, bar_time: str) -> float:
        """
        Consecutive Bars: How many bars in a row show absorption signals
        Check last 5 bars for same direction delta
        """
        cursor = conn.execute("""
            SELECT bar_time, delta, high, low, volume
            FROM bars
            WHERE symbol = ? AND timeframe = ? AND bar_time <= ?
            ORDER BY bar_time DESC
            LIMIT 6
        """, (symbol, timeframe, bar_time))
        rows = cursor.fetchall()
        
        if len(rows) < 3:
            return 0.0
        
        # Check if deltas are all same sign (all buying or all selling)
        deltas = [r[1] for r in rows]
        first_sign = deltas[0] * deltas[1] if deltas[0] and deltas[1] else 0
        
        if first_sign <= 0:
            return 0.0  # Mixed directions
        
        # Count consecutive same-sign deltas
        consecutive = 0
        for i in range(len(deltas) - 1):
            if deltas[i] * deltas[i+1] > 0:
                consecutive += 1
            else:
                break
        
        # Also check they're not moving price much
        ranges = [r[3] - r[2] for r in rows[:consecutive+1]]
        avg_range = sum(ranges) / len(ranges) if ranges else 0
        
        if consecutive >= 3 and avg_range < 2.0:  # Tight ranges
            return min(1.0, consecutive / 5.0)
        
        return 0.0
    
    def _get_direction(self, bar: dict) -> str:
        """Get direction of absorption"""
        delta = bar["delta"] if bar["delta"] else 0
        if delta > 0:
            return "BUYING"
        elif delta < 0:
            return "SELLING"
        return "NEUTRAL"
    
    def _interpret(self, score: float) -> str:
        """Human-readable interpretation"""
        direction = ""
        if hasattr(self, '_last_direction'):
            direction = f" ({self._last_direction})"
        
        if score >= 0.8:
            return f"STRONG ABSORPTION - Large orders hitting{direction}, reversal likely"
        elif score >= 0.6:
            return f"MODERATE ABSORPTION - Price stalling{direction}, watch for move"
        elif score >= 0.4:
            return f"MILD ABSORPTION - Some pressure being absorbed"
        elif score >= 0.2:
            return f"LOW ABSORPTION - Some resistance but intact"
        else:
            return "NO ABSORPTION - Price following flow"
    
    def score_all_bars(self, symbol: str, timeframe: str) -> list:
        """Calculate absorption for all bars in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT DISTINCT bar_time FROM bars
            WHERE symbol = ? AND timeframe = ?
            ORDER BY bar_time
        """, (symbol, timeframe))
        bar_times = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        results = []
        for bar_time in bar_times:
            result = self.calculate_absorption(symbol, timeframe, bar_time)
            result["bar_time"] = bar_time
            result["symbol"] = symbol
            result["timeframe"] = timeframe
            self._last_direction = result.get("direction", "NEUTRAL")
            results.append(result)
            
            # Save to database
            self._save_score(result)
        
        return results
    
    def _save_score(self, result: dict):
        """Save score to database"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO agent_scores 
            (symbol, timeframe, bar_time, agent_name, score, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            result.get("symbol"),
            result.get("timeframe"),
            result.get("bar_time"),
            self.name,
            result.get("score"),
            json.dumps({
                "components": result.get("components", {}),
                "direction": result.get("direction", "NEUTRAL")
            })
        ))
        conn.commit()
        conn.close()
    
    def get_latest_score(self, symbol: str, timeframe: str) -> Optional[dict]:
        """Get most recent absorption score"""
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
            "bar_time": row[0],
            "score": row[1],
            "components": details.get("components", {}),
            "direction": details.get("direction", "NEUTRAL")
        }


def main():
    """CLI for testing"""
    agent = AbsorptionAgent()
    
    import argparse
    parser = argparse.ArgumentParser(description="Absorption Agent")
    parser.add_argument("--symbol", default="ES", help="Symbol")
    parser.add_argument("--timeframe", default="5min", help="Timeframe")
    parser.add_argument("--bar", help="Specific bar time (YYYY-MM-DD HH:MM)")
    parser.add_argument("--scan", action="store_true", help="Scan all bars")
    args = parser.parse_args()
    
    if args.scan:
        results = agent.score_all_bars(args.symbol, args.timeframe)
        print(f"\nAbsorption Analysis: {args.symbol} {args.timeframe}")
        print("=" * 60)
        for r in results[-20:]:  # Last 20 bars
            print(f"{r['bar_time']}: {r['score']:.3f} {r['direction']} - {r['interpretation']}")
            print(f"  Components: {r['components']}")
            print()
    
    elif args.bar:
        result = agent.calculate_absorption(args.symbol, args.timeframe, args.bar)
        print(f"\nAbsorption Score for {args.bar}")
        print("=" * 40)
        print(f"Score: {result['score']:.3f}")
        print(f"Direction: {result['direction']}")
        print(f"Interpretation: {result['interpretation']}")
        print("\nComponents:")
        for k, v in result['components'].items():
            print(f"  {k}: {v:.3f}")
    
    else:
        latest = agent.get_latest_score(args.symbol, args.timeframe)
        if latest:
            print(f"\nLatest Absorption: {latest['bar_time']}")
            print(f"Score: {latest['score']:.3f}")
            print(f"Direction: {latest['direction']}")
            print(f"Components: {latest['components']}")
        else:
            print("No data. Import CSV first or use --scan")


if __name__ == "__main__":
    main()
