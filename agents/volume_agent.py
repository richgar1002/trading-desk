#!/usr/bin/env python3
"""
Volume Agent
Measures: Volume spikes, thin book conditions, abnormal volume

Score 0-1:
  0.0 = Normal volume
  0.5 = Elevated volume
  1.0 = Extreme volume spike

Volume spikes often precede:
  - Reversals (exhaustion)
  - Continuations (momentum)
  - Liquidity grabs (stop runs)
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

class VolumeAgent:
    """Measures volume signals in orderflow data"""
    
    name = "volume"
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Ensure database has this agent registered"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO agents (name, description) 
            VALUES ('volume', 'Measures volume spikes and thin book conditions')
        """)
        conn.commit()
        conn.close()
    
    def calculate_volume(self, symbol: str, timeframe: str, bar_time: str) -> dict:
        """
        Calculate volume score for a specific bar.
        """
        conn = sqlite3.connect(self.db_path)
        
        bar = self._get_bar(conn, symbol, timeframe, bar_time)
        if not bar:
            conn.close()
            return {"score": 0.0, "error": "Bar not found", "components": {}}
        
        prev_bars = self._get_previous_bars(conn, symbol, timeframe, bar_time, 20)
        
        components = {}
        
        # Component 1: Volume Spike
        # Current volume vs average
        vol_spike = self._calc_volume_spike(bar, prev_bars)
        components["volume_spike"] = vol_spike
        
        # Component 2: Thin Book Indicator
        # Low volume relative to range (thin market)
        thin_book = self._calc_thin_book(bar, prev_bars)
        components["thin_book"] = thin_book
        
        # Component 3: Volume Profile Imbalance
        # Volume concentrated in small range
        vol_profile = self._calc_volume_profile_imbalance(bar, prev_bars)
        components["vol_profile_imbalance"] = vol_profile
        
        # Component 4: Climactic Volume
        # Very high volume at end of move
        climactic = self._calc_climactic(bar, prev_bars)
        components["climactic"] = climactic
        
        weights = {
            "volume_spike": 0.35,
            "thin_book": 0.25,
            "vol_profile_imbalance": 0.20,
            "climactic": 0.20
        }
        
        score = sum(components[k] * weights[k] for k in weights)
        score = round(min(1.0, max(0.0, score)), 3)
        
        conn.close()
        
        return {
            "score": score,
            "components": components,
            "interpretation": self._interpret(score),
            "volume": bar.get("volume", 0)
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
    
    def _calc_volume_spike(self, bar: dict, prev_bars: list) -> float:
        """Volume relative to average"""
        vol = bar["volume"] if bar["volume"] > 0 else 1
        
        if not prev_bars:
            return 0.0
        
        avg_vol = sum(b["volume"] for b in prev_bars) / len(prev_bars)
        if avg_vol == 0:
            return 0.0
        
        ratio = vol / avg_vol
        
        # 1.5x average = mild spike, 3x+ = extreme
        if ratio >= 2.5:
            return min(1.0, (ratio - 2.0) / 2.0)
        elif ratio >= 1.5:
            return min(1.0, (ratio - 1.0) / 2.0)
        
        return 0.0
    
    def _calc_thin_book(self, bar: dict, prev_bars: list) -> float:
        """Low volume relative to price range (thin market)"""
        vol = bar["volume"] if bar["volume"] > 0 else 1
        price_range = bar["high"] - bar["low"]
        
        if price_range == 0:
            return 0.5
        
        # Points per contract
        ppc = price_range / vol
        
        if not prev_bars:
            return 0.0
        
        avg_ppc = sum((b["high"] - b["low"]) / (b["volume"] if b["volume"] > 0 else 1) for b in prev_bars) / len(prev_bars)
        
        if avg_ppc == 0:
            return 0.0
        
        # If ppc is much higher than average = thin book (not many contracts moving price)
        if ppc > avg_ppc * 1.5:
            return min(1.0, (ppc / avg_ppc - 1.0) / 2.0)
        
        return 0.0
    
    def _calc_volume_profile_imbalance(self, bar: dict, prev_bars: list) -> float:
        """Volume concentrated in narrow range vs normal distribution"""
        vol = bar["volume"] if bar["volume"] > 0 else 1
        price_range = bar["high"] - bar["low"]
        
        if price_range == 0 or vol < 10:
            return 0.0
        
        # Compare to previous bars' volume density
        if not prev_bars:
            return 0.0
        
        avg_vol_per_point = vol / price_range
        prev_densities = []
        for b in prev_bars:
            b_range = b["high"] - b["low"]
            if b_range > 0:
                prev_densities.append(b["volume"] / b_range)
        
        if not prev_densities:
            return 0.0
        
        avg_density = sum(prev_densities) / len(prev_densities)
        
        # Much higher density = volume concentrated
        if avg_density > 0 and avg_vol_per_point > avg_density * 2:
            return min(1.0, (avg_vol_per_point / avg_density - 1.0))
        
        return 0.0
    
    def _calc_climactic(self, bar: dict, prev_bars: list) -> float:
        """Very high volume at end of directional move"""
        vol = bar["volume"] if bar["volume"] > 0 else 0
        price_range = bar["high"] - bar["low"]
        
        if not prev_bars or len(prev_bars) < 5:
            return 0.0
        
        # Check if this bar has much higher volume than last 5
        recent_avg = sum(b["volume"] for b in prev_bars[:5]) / 5
        
        if recent_avg == 0:
            return 0.0
        
        # Check if price moved significantly
        price_change = abs(bar["close"] - bar["open"])
        direction = 1 if bar["delta"] > 0 else -1
        
        # Count how many recent bars went same direction
        same_direction = 0
        for b in prev_bars[:5]:
            b_dir = 1 if b["delta"] > 0 else -1
            if b_dir == direction:
                same_direction += 1
        
        ratio = vol / recent_avg
        
        # Climactic if: very high volume + price moved + was end of a run
        if ratio >= 2.5 and price_change > 0 and same_direction >= 3:
            return min(1.0, (ratio - 2.0) / 2.0)
        
        return 0.0
    
    def _interpret(self, score: float) -> str:
        if score >= 0.8:
            return "EXTREME VOLUME - Climactic move, reversal likely"
        elif score >= 0.6:
            return "HIGH VOLUME - Significant event, watch for resolution"
        elif score >= 0.4:
            return "ELEVATED VOLUME - Above average activity"
        elif score >= 0.2:
            return "MODERATE VOLUME - Some increase from normal"
        else:
            return "NORMAL VOLUME - No anomalies"
    
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
            result = self.calculate_volume(symbol, timeframe, bar_time)
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
            json.dumps({"components": result.get("components", {}), "volume": result.get("volume", 0)})
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
            "volume": details.get("volume", 0)
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Volume Agent")
    parser.add_argument("--symbol", default="ES")
    parser.add_argument("--timeframe", default="1min")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--bar", help="Specific bar time")
    args = parser.parse_args()
    
    agent = VolumeAgent()
    
    if args.scan:
        results = agent.score_all_bars(args.symbol, args.timeframe)
        print(f"\nVolume Analysis: {args.symbol} {args.timeframe}")
        print("=" * 60)
        for r in results[-15:]:
            print(f"{r['bar_time']}: {r['score']:.3f} - {r['interpretation']}")
            print(f"  Vol: {r.get('volume', 0)} | {r['components']}")
    
    elif args.bar:
        result = agent.calculate_volume(args.symbol, args.timeframe, args.bar)
        print(f"\nVolume Score: {args.bar}")
        print(f"Score: {result['score']:.3f}")
        print(f"Interpretation: {result['interpretation']}")
        print(f"Components: {result['components']}")
    
    else:
        latest = agent.get_latest_score(args.symbol, args.timeframe)
        if latest:
            print(f"\nLatest: {latest['bar_time']} - {latest['score']:.3f}")
            print(f"Volume: {latest.get('volume', 0)}")
        else:
            print("No data. Use --scan")


if __name__ == "__main__":
    main()
