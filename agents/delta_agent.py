#!/usr/bin/env python3
"""
Delta Agent
Measures: Aggressive buying vs selling balance, directional flow strength

Score 0-1 (for one direction):
  0.0 = Balanced / neutral
  0.5 = Moderate imbalance
  1.0 = Extreme delta imbalance

Delta tells you:
  - Who's winning the battle (buyers vs sellers)
  - If moves are backed by real flow
  - Divergence between delta and price
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

class DeltaAgent:
    """Measures delta (directional flow) signals"""
    
    name = "delta"
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO agents (name, description) 
            VALUES ('delta', 'Measures aggressive buying vs selling balance')
        """)
        conn.commit()
        conn.close()
    
    def calculate_delta(self, symbol: str, timeframe: str, bar_time: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        
        bar = self._get_bar(conn, symbol, timeframe, bar_time)
        if not bar:
            conn.close()
            return {"score": 0.0, "error": "Bar not found", "components": {}}
        
        prev_bars = self._get_previous_bars(conn, symbol, timeframe, bar_time, 20)
        
        components = {}
        
        # Component 1: Delta Magnitude
        # How large is delta relative to volume
        delta_mag = self._calc_delta_magnitude(bar, prev_bars)
        components["delta_magnitude"] = delta_mag
        
        # Component 2: Delta Direction Strength
        # Cumulative delta in one direction
        direction_strength = self._calc_direction_strength(prev_bars)
        components["direction_strength"] = direction_strength
        
        # Component 3: Delta Divergence
        # Delta says buy but price didn't follow
        divergence = self._calc_delta_divergence(bar)
        components["divergence"] = divergence
        
        # Component 4: Delta Momentum
        # Is delta increasing or fading?
        momentum = self._calc_delta_momentum(conn, bar, prev_bars)
        components["momentum"] = momentum
        
        weights = {
            "delta_magnitude": 0.30,
            "direction_strength": 0.25,
            "divergence": 0.25,
            "momentum": 0.20
        }
        
        score = sum(components[k] * weights[k] for k in weights)
        score = round(min(1.0, max(0.0, score)), 3)
        
        conn.close()
        
        return {
            "score": score,
            "components": components,
            "interpretation": self._interpret(score, bar["delta"]),
            "direction": self._get_direction(bar["delta"]),
            "delta_value": bar["delta"]
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
    
    def _calc_delta_magnitude(self, bar: dict, prev_bars: list) -> float:
        """How large is delta relative to volume and average"""
        delta = abs(bar["delta"]) if bar["delta"] else 0
        volume = bar["volume"] if bar["volume"] > 0 else 1
        
        # Delta as percentage of volume
        delta_pct = delta / volume
        
        if not prev_bars:
            return min(1.0, delta_pct * 2)
        
        # Compare to average
        avg_delta = sum(abs(b["delta"]) for b in prev_bars) / len(prev_bars)
        avg_vol = sum(b["volume"] for b in prev_bars) / len(prev_bars)
        
        if avg_vol == 0:
            return 0.0
        
        avg_delta_pct = avg_delta / avg_vol
        
        # If current delta% is much higher than average
        if avg_delta_pct > 0:
            ratio = delta_pct / avg_delta_pct
            if ratio >= 2.0:
                return min(1.0, (ratio - 1.0) / 2.0)
            elif ratio >= 1.3:
                return min(1.0, (ratio - 1.0))
        
        return delta_pct * 2
    
    def _calc_direction_strength(self, prev_bars: list) -> float:
        """How many bars in a row have same direction delta"""
        if len(prev_bars) < 3:
            return 0.0
        
        deltas = [b["delta"] for b in prev_bars[:10]]
        
        # Count consecutive same-sign deltas
        first_sign = 1 if deltas[0] > 0 else -1 if deltas[0] < 0 else 0
        if first_sign == 0:
            return 0.0
        
        consecutive = 0
        for d in deltas:
            if (d > 0 and first_sign > 0) or (d < 0 and first_sign < 0):
                consecutive += 1
            else:
                break
        
        # 5+ consecutive = strong directional bias
        if consecutive >= 5:
            return min(1.0, consecutive / 7.0)
        
        return 0.0
    
    def _calc_delta_divergence(self, bar: dict) -> float:
        """
        Delta says buy/sell but price didn't follow
        High delta divergence = potential reversal
        """
        delta = bar["delta"] if bar["delta"] else 0
        price_change = bar["close"] - bar["open"]
        
        if delta == 0 or price_change == 0:
            return 0.0
        
        # Same sign = no divergence
        if (delta > 0 and price_change > 0) or (delta < 0 and price_change < 0):
            return 0.0
        
        # Divergence: delta and price disagree
        delta_abs = abs(delta)
        price_move_abs = abs(price_change)
        
        # How big is the disagreement?
        if price_move_abs > 0:
            divergence_ratio = delta_abs / price_move_abs
            
            # 3x delta vs price move = strong divergence
            if divergence_ratio >= 3.0:
                return min(1.0, (divergence_ratio - 2.0) / 3.0)
            elif divergence_ratio >= 1.5:
                return min(1.0, (divergence_ratio - 1.0) / 2.0)
        
        return 0.0
    
    def _calc_delta_momentum(self, conn, bar: dict, prev_bars: list) -> float:
        """Is delta increasing (momentum building) or fading?"""
        if len(prev_bars) < 3:
            return 0.0
        
        current_delta = abs(bar["delta"]) if bar["delta"] else 0
        
        # Average of last 3 vs average of previous 5
        recent = [abs(b["delta"]) for b in prev_bars[:3] if b["delta"]]
        older = [abs(b["delta"]) for b in prev_bars[3:8] if b["delta"]]
        
        if not recent or not older:
            return 0.0
        
        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)
        
        if avg_older == 0:
            return 0.0
        
        ratio = avg_recent / avg_older
        
        # Momentum building (increasing delta over time)
        if ratio >= 1.5:
            return min(1.0, (ratio - 1.0))
        # Momentum fading
        elif ratio < 0.7:
            return min(1.0, (0.7 - ratio) / 0.7)
        
        return 0.0
    
    def _get_direction(self, delta: int) -> str:
        if delta > 0:
            return "BUYING"
        elif delta < 0:
            return "SELLING"
        return "BALANCED"
    
    def _interpret(self, score: float, delta: int) -> str:
        direction = self._get_direction(delta)
        
        if score >= 0.7:
            return f"STRONG {direction} DELTA - Momentum {'building' if delta * (score - 0.5) > 0 else 'fading'}"
        elif score >= 0.5:
            return f"MODERATE {direction} IMBALANCE"
        elif score >= 0.3:
            return f"WEAK {direction} BIAS"
        else:
            return "BALANCED DELTA FLOW"
    
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
            result = self.calculate_delta(symbol, timeframe, bar_time)
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
                "direction": result.get("direction", "BALANCED"),
                "delta_value": result.get("delta_value", 0)
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
            "direction": details.get("direction", "BALANCED"),
            "delta_value": details.get("delta_value", 0)
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Delta Agent")
    parser.add_argument("--symbol", default="ES")
    parser.add_argument("--timeframe", default="1min")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--bar", help="Specific bar time")
    args = parser.parse_args()
    
    agent = DeltaAgent()
    
    if args.scan:
        results = agent.score_all_bars(args.symbol, args.timeframe)
        print(f"\nDelta Analysis: {args.symbol} {args.timeframe}")
        print("=" * 60)
        for r in results[-15:]:
            print(f"{r['bar_time']}: {r['score']:.3f} {r['direction']} | Delta: {r.get('delta_value', 0)}")
            print(f"  {r['interpretation']}")
    
    elif args.bar:
        result = agent.calculate_delta(args.symbol, args.timeframe, args.bar)
        print(f"\nDelta Score: {args.bar}")
        print(f"Score: {result['score']:.3f}")
        print(f"Direction: {result['direction']}")
        print(f"Delta: {result.get('delta_value', 0)}")
        print(f"Components: {result['components']}")
    
    else:
        latest = agent.get_latest_score(args.symbol, args.timeframe)
        if latest:
            print(f"\nLatest: {latest['bar_time']} - {latest['score']:.3f} {latest['direction']}")
        else:
            print("No data. Use --scan")


if __name__ == "__main__":
    main()
