#!/usr/bin/env python3
"""
VWAP Agent
Measures: VWAP deviations, session VWAP, cross Overs/unders

Score 0-1:
  0.0 = At VWAP
  0.5 = Moderate deviation
  1.0 = Extreme deviation from VWAP

Also tracks: VWAP cross direction, deviation magnitude
"""

import sqlite3
import json
import os
from typing import Optional
from datetime import datetime

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

class VWAPAgent:
    """Measures VWAP deviations and crossovers"""
    
    name = "vwap"
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
        self._ensure_table()
    
    def _ensure_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO agents (name, description) 
            VALUES ('vwap', 'Measures VWAP deviations')
        """)
        conn.commit()
        conn.close()
    
    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vwap_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                bar_time TEXT NOT NULL,
                vwap REAL,
                deviation_points REAL,
                deviation_pct REAL,
                vwap_distance REAL,
                direction TEXT,
                details TEXT,
                UNIQUE(symbol, timeframe, bar_time)
            )
        """)
        conn.commit()
        conn.close()
    
    def calculate_vwap(self, symbol: str, timeframe: str, bar_time: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        
        bar = self._get_bar(conn, symbol, timeframe, bar_time)
        if not bar:
            conn.close()
            return {"error": "Bar not found"}
        
        # Get previous bars for VWAP calculation
        prev_bars = self._get_previous_bars(conn, symbol, timeframe, bar_time, 100)
        conn.close()
        
        # Calculate VWAP from scratch using all available data
        vwap, total_pv = self._calculate_vwap(bar, prev_bars)
        
        # Calculate deviation
        close = bar["close"]
        deviation_points = close - vwap
        deviation_pct = (deviation_points / vwap * 100) if vwap != 0 else 0
        
        # Determine direction
        if deviation_points > 0:
            direction = "ABOVE_VWAP"
        elif deviation_points < 0:
            direction = "BELOW_VWAP"
        else:
            direction = "AT_VWAP"
        
        # Score based on deviation magnitude
        # Typical ES deviation thresholds
        score = self._calc_score(deviation_pct)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "bar_time": bar_time,
            "vwap": round(vwap, 2),
            "close": close,
            "deviation_points": round(deviation_points, 2),
            "deviation_pct": round(deviation_pct, 4),
            "direction": direction,
            "score": score,
            "interpretation": self._interpret(score, deviation_pct, direction)
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
    
    def _calculate_vwap(self, current_bar: dict, prev_bars: list) -> tuple:
        """Calculate VWAP using typical price * volume"""
        all_bars = prev_bars + [current_bar]
        
        total_pv = 0  # Price * Volume sum
        total_vol = 0  # Volume sum
        
        for bar in all_bars:
            # Typical price = (H+L+C)/3 or just use close
            typical_price = (bar["high"] + bar["low"] + bar["close"]) / 3
            vol = bar["volume"] or 0
            
            total_pv += typical_price * vol
            total_vol += vol
        
        if total_vol == 0:
            return current_bar["close"], 0
        
        vwap = total_pv / total_vol
        return vwap, total_pv
    
    def _calc_score(self, deviation_pct: float) -> float:
        """Convert deviation % to score 0-1"""
        # For ES, 0.1% deviation = ~6 points on 5800
        # Typical max deviation we care about = 0.5% (30 points)
        
        abs_dev = abs(deviation_pct)
        
        if abs_dev < 0.05:
            return abs_dev * 4  # 0 to 0.2
        elif abs_dev < 0.15:
            return 0.2 + (abs_dev - 0.05) * 4  # 0.2 to 0.6
        elif abs_dev < 0.3:
            return 0.6 + (abs_dev - 0.15) * 2  # 0.6 to 0.9
        else:
            return min(1.0, 0.9 + (abs_dev - 0.3))
    
    def _interpret(self, score: float, deviation_pct: float, direction: str) -> str:
        abs_dev = abs(deviation_pct)
        
        if score >= 0.7:
            return f"EXTREME DEVIATION - {abs_dev:.3f}% {'above' if deviation_pct > 0 else 'below'} VWAP"
        elif score >= 0.5:
            return f"SIGNIFICANT DEVIATION - {abs_dev:.3f}% {'above' if deviation_pct > 0 else 'below'} VWAP"
        elif score >= 0.3:
            return f"MODERATE DEVIATION - {abs_dev:.3f}% {'above' if deviation_pct > 0 else 'below'} VWAP"
        else:
            return f"NEAR VWAP - {abs_dev:.3f}% {'above' if deviation_pct > 0 else 'below'} VWAP"
    
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
            result = self.calculate_vwap(symbol, timeframe, bar_time)
            results.append(result)
            self._save_vwap(result)
        
        return results
    
    def _save_vwap(self, result: dict):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO vwap_data 
            (symbol, timeframe, bar_time, vwap, deviation_points, deviation_pct, direction, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.get("symbol"), result.get("timeframe"), result.get("bar_time"),
            result.get("vwap"), result.get("deviation_points"), result.get("deviation_pct"),
            result.get("direction"),
            json.dumps({"interpretation": result.get("interpretation"), "score": result.get("score")})
        ))
        conn.commit()
        conn.close()
    
    def get_latest_vwap(self, symbol: str, timeframe: str) -> Optional[dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT bar_time, vwap, deviation_points, deviation_pct, direction, details
            FROM vwap_data WHERE symbol = ? AND timeframe = ?
            ORDER BY bar_time DESC LIMIT 1
        """, (symbol, timeframe))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        details = json.loads(row[5]) if row[5] else {}
        return {
            "bar_time": row[0], "vwap": row[1], "deviation_points": row[2],
            "deviation_pct": row[3], "direction": row[4],
            "interpretation": details.get("interpretation", ""),
            "score": details.get("score", 0)
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="VWAP Agent")
    parser.add_argument("--symbol", default="ES")
    parser.add_argument("--timeframe", default="1min")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--bar", help="Specific bar time")
    args = parser.parse_args()
    
    agent = VWAPAgent()
    
    if args.scan:
        results = agent.score_all_bars(args.symbol, args.timeframe)
        print(f"\nVWAP Analysis: {args.symbol} {args.timeframe}")
        print("=" * 80)
        for r in results[-15:]:
            print(f"{r['bar_time']}: VWAP={r['vwap']} Close={r['close']} Dev={r['deviation_points']} ({r['deviation_pct']:.3f}%) {r['direction']}")
            print(f"  Score={r['score']:.2f} - {r['interpretation']}")
    
    elif args.bar:
        result = agent.calculate_vwap(args.symbol, args.timeframe, args.bar)
        print(f"\nVWAP: {args.bar}")
        print(f"VWAP: {result.get('vwap')}")
        print(f"Close: {result.get('close')}")
        print(f"Deviation: {result.get('deviation_points')} points ({result.get('deviation_pct'):.3f}%)")
        print(f"Direction: {result.get('direction')}")
        print(f"Score: {result.get('score'):.3f}")
        print(f"Interpretation: {result.get('interpretation')}")
    
    else:
        latest = agent.get_latest_vwap(args.symbol, args.timeframe)
        if latest:
            print(f"\nLatest: {latest['bar_time']}")
            print(f"VWAP={latest['vwap']} Dev={latest['deviation_points']} ({latest['deviation_pct']:.3f}%)")
            print(f"{latest['direction']} - {latest['interpretation']}")
        else:
            print("No data. Use --scan")


if __name__ == "__main__":
    main()
