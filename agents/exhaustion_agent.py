#!/usr/bin/env python3
"""
Exhaustion Agent
Measures: Buying without price movement, delta divergence

Score 0-1:
  0.0 = No exhaustion (strong directional movement)
  0.5 = Partial exhaustion (some stalling)
  1.0 = Full exhaustion (price flat despite high delta)
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

class ExhaustionAgent:
    """Measures exhaustion signals in orderflow data"""
    
    name = "exhaustion"
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Ensure database and tables exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        with open("/tmp/trading-desk/database/schema.sql") as f:
            conn.executescript(f.read())
        conn.close()
    
    def calculate_exhaustion(self, symbol: str, timeframe: str, bar_time: str) -> dict:
        """
        Calculate exhaustion score for a specific bar.
        
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
        prev_bars = self._get_previous_bars(conn, symbol, timeframe, bar_time, 5)
        
        # Calculate components
        components = {}
        
        # Component 1: Delta Divergence
        # Price flat but high delta = exhaustion
        delta_div = self._calc_delta_divergence(bar, prev_bars)
        components["delta_divergence"] = delta_div
        
        # Component 2: Volume vs Movement
        # High volume, low price change = exhaustion
        vol_movement = self._calc_volume_movement_ratio(bar, prev_bars)
        components["volume_movement_ratio"] = vol_movement
        
        # Component 3: Lingering (time at level)
        # Price stuck at same level = no follow-through
        lingering = self._calc_lingering(bar, prev_bars)
        components["lingering"] = lingering
        
        # Component 4: Delta Fade
        # High delta early, fading later = exhaustion
        delta_fade = self._calc_delta_fade(conn, bar)
        components["delta_fade"] = delta_fade
        
        # Weighted average
        weights = {
            "delta_divergence": 0.35,
            "volume_movement_ratio": 0.30,
            "lingering": 0.20,
            "delta_fade": 0.15
        }
        
        score = sum(components[k] * weights[k] for k in weights)
        score = round(min(1.0, max(0.0, score)), 3)
        
        conn.close()
        
        return {
            "score": score,
            "components": components,
            "interpretation": self._interpret(score)
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
    
    def _calc_delta_divergence(self, bar: dict, prev_bars: list) -> float:
        """
        Delta Divergence: Price change vs delta
        High delta, low price change = exhaustion
        """
        price_range = bar["high"] - bar["low"]
        if price_range == 0:
            price_range = 0.01
        
        price_change = abs(bar["close"] - bar["open"])
        price_change_pct = price_change / price_range if price_range > 0 else 0
        
        delta_abs = abs(bar["delta"]) if bar["delta"] else 0
        
        # Normalize: if delta is high but price didn't move much = high exhaustion
        # Scale delta by average volume to make it relative
        avg_vol = sum(b["volume"] for b in prev_bars) / len(prev_bars) if prev_bars else bar["volume"]
        if avg_vol == 0:
            avg_vol = 1
        
        delta_ratio = delta_abs / avg_vol if avg_vol > 0 else 0
        
        # If price moved < 30% of range but delta was significant = exhaustion
        if price_change_pct < 0.3 and delta_ratio > 0.1:
            exhaustion = min(1.0, delta_ratio * 5)
        else:
            exhaustion = 0.0
        
        return exhaustion
    
    def _calc_volume_movement_ratio(self, bar: dict, prev_bars: list) -> float:
        """
        Volume vs Movement: High volume, low movement = exhaustion
        """
        volume = bar["volume"]
        price_range = bar["high"] - bar["low"]
        
        if price_range == 0:
            price_range = 0.01
        
        # Get average volume and range for comparison
        avg_vol = sum(b["volume"] for b in prev_bars) / len(prev_bars) if prev_bars else volume
        avg_range = sum(b["high"] - b["low"] for b in prev_bars) / len(prev_bars) if prev_bars else price_range
        
        if avg_vol == 0 or avg_range == 0:
            return 0.0
        
        vol_ratio = volume / avg_vol
        range_ratio = price_range / avg_range
        
        # High volume (above avg) but low movement (below avg) = exhaustion
        if vol_ratio > 1.3 and range_ratio < 0.7:
            # Calculate how extreme
            vol_factor = min(vol_ratio / 2.0, 1.0)  # Cap at 2x avg vol
            range_factor = 1.0 - (range_ratio / 0.7)  # More exhaustion if range is very small
            return min(1.0, vol_factor * range_factor)
        
        return 0.0
    
    def _calc_lingering(self, bar: dict, prev_bars: list) -> float:
        """
        Lingering: Price stuck at same level despite effort
        """
        if not prev_bars:
            return 0.0
        
        # Check how similar current bar's close is to previous bars' closes
        current_close = bar["close"]
        prev_closes = [b["close"] for b in prev_bars[:3]]
        
        if not prev_closes:
            return 0.0
        
        avg_prev_close = sum(prev_closes) / len(prev_closes)
        price_stability = 1.0 - min(abs(current_close - avg_prev_close) / avg_prev_close, 1.0)
        
        # If price barely moved from last 3 bars = lingering
        return price_stability * 0.5
    
    def _calc_delta_fade(self, conn, bar: dict) -> float:
        """
        Delta Fade: Check if delta was high at open/close but faded
        (Requires footprint data for intra-bar analysis)
        For now, use bar-level as proxy
        """
        # Without intra-bar footprint, we use bar delta relative to volume
        if bar["volume"] == 0:
            return 0.0
        
        delta_intensity = abs(bar["delta"]) / bar["volume"]
        price_momentum = abs(bar["close"] - bar["open"]) / (bar["high"] - bar["low"] + 0.01)
        
        # High delta-to-volume but low price momentum = fade
        if delta_intensity > 0.3 and price_momentum < 0.3:
            return min(1.0, delta_intensity)
        
        return 0.0
    
    def _interpret(self, score: float) -> str:
        """Human-readable interpretation"""
        if score >= 0.8:
            return "STRONG EXHAUSTION - Reversal likely"
        elif score >= 0.6:
            return "MODERATE EXHAUSTION - Watch for reversal"
        elif score >= 0.4:
            return "MILD EXHAUSTION - Possible stalling"
        elif score >= 0.2:
            return "LOW EXHAUSTION - Some pressure but not extreme"
        else:
            return "NO EXHAUSTION - Directional move intact"
    
    def score_all_bars(self, symbol: str, timeframe: str) -> list:
        """Calculate exhaustion for all bars in database"""
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
            result = self.calculate_exhaustion(symbol, timeframe, bar_time)
            result["bar_time"] = bar_time
            result["symbol"] = symbol
            result["timeframe"] = timeframe
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
            json.dumps(result.get("components", {}))
        ))
        conn.commit()
        conn.close()
    
    def get_latest_score(self, symbol: str, timeframe: str) -> Optional[dict]:
        """Get most recent exhaustion score"""
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
        
        return {
            "bar_time": row[0],
            "score": row[1],
            "components": json.loads(row[2]) if row[2] else {}
        }
    
    def get_threshold_alert(self, symbol: str, timeframe: str, threshold: float = 0.7) -> Optional[dict]:
        """Get alert if threshold crossed"""
        latest = self.get_latest_score(symbol, timeframe)
        if latest and latest["score"] >= threshold:
            return latest
        return None


def main():
    """CLI for testing"""
    agent = ExhaustionAgent()
    
    import argparse
    parser = argparse.ArgumentParser(description="Exhaustion Agent")
    parser.add_argument("--symbol", default="ES", help="Symbol")
    parser.add_argument("--timeframe", default="5min", help="Timeframe")
    parser.add_argument("--bar", help="Specific bar time (YYYY-MM-DD HH:MM)")
    parser.add_argument("--scan", action="store_true", help="Scan all bars")
    args = parser.parse_args()
    
    if args.scan:
        results = agent.score_all_bars(args.symbol, args.timeframe)
        print(f"\nExhaustion Analysis: {args.symbol} {args.timeframe}")
        print("=" * 60)
        for r in results[-10:]:  # Last 10 bars
            print(f"{r['bar_time']}: {r['score']:.3f} - {r['interpretation']}")
            print(f"  Components: {r['components']}")
            print()
    
    elif args.bar:
        result = agent.calculate_exhaustion(args.symbol, args.timeframe, args.bar)
        print(f"\nExhaustion Score for {args.bar}")
        print("=" * 40)
        print(f"Score: {result['score']:.3f}")
        print(f"Interpretation: {result['interpretation']}")
        print("\nComponents:")
        for k, v in result['components'].items():
            print(f"  {k}: {v:.3f}")
    
    else:
        # Show latest
        latest = agent.get_latest_score(args.symbol, args.timeframe)
        if latest:
            print(f"\nLatest Exhaustion: {latest['bar_time']}")
            print(f"Score: {latest['score']:.3f}")
            print(f"Components: {latest['components']}")
        else:
            print("No data. Import CSV first or use --scan")


if __name__ == "__main__":
    main()
