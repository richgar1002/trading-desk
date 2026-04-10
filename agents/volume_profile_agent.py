#!/usr/bin/env python3
"""
Volume Profile Agent
Measures: POC (Point of Control), VAL (Value Area Low), VAH (Value Area High)
Tracks: Where volume concentrated, value area definition

Outputs volume profile data for each bar - not a score but a snapshot of 
volume distribution.
"""

import sqlite3
import json
import os
from typing import Optional

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

class VolumeProfileAgent:
    """Records volume profile data (POC, VAL, VAH)"""
    
    name = "volume_profile"
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
        self._ensure_table()
    
    def _ensure_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO agents (name, description) 
            VALUES ('volume_profile', 'Tracks POC, VAL, VAH')
        """)
        conn.commit()
        conn.close()
    
    def _ensure_table(self):
        """Create volume_profile table if not exists"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS volume_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                bar_time TEXT NOT NULL,
                poc REAL,
                val REAL,
                vah REAL,
                vah_poc REAL,
                val_poc REAL,
                total_volume INTEGER,
                details TEXT,
                UNIQUE(symbol, timeframe, bar_time)
            )
        """)
        conn.commit()
        conn.close()
    
    def calculate_profile(self, symbol: str, timeframe: str, bar_time: str) -> dict:
        """Calculate volume profile for a bar using footprint data"""
        conn = sqlite3.connect(self.db_path)
        
        # Get bar info
        bar = self._get_bar(conn, symbol, timeframe, bar_time)
        if not bar:
            conn.close()
            return {"error": "Bar not found"}
        
        # Get footprint data for this bar
        footprint_data = self._get_footprint(conn, symbol, timeframe, bar_time)
        conn.close()
        
        if not footprint_data:
            # No footprint, use rough estimate from OHLC
            return self._estimate_profile(bar)
        
        # Calculate actual profile from footprint
        return self._calculate_from_footprint(bar, footprint_data)
    
    def _get_bar(self, conn, symbol: str, timeframe: str, bar_time: str) -> Optional[dict]:
        cursor = conn.execute("""
            SELECT bar_time, open, high, low, close, volume, bid_vol, ask_vol, delta
            FROM bars WHERE symbol = ? AND timeframe = ? AND bar_time = ?
        """, (symbol, timeframe, bar_time))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "symbol": symbol, "timeframe": timeframe,
            "bar_time": row[0], "open": row[1], "high": row[2], "low": row[3],
            "close": row[4], "volume": row[5], "bid_vol": row[6], "ask_vol": row[7], "delta": row[8]
        }
    
    def _get_footprint(self, conn, symbol: str, timeframe: str, bar_time: str) -> list:
        """Get footprint rows for this bar"""
        cursor = conn.execute("""
            SELECT price, bid_vol, ask_vol, total_vol
            FROM raw_footprint
            WHERE symbol = ? AND timeframe = ? AND bar_time = ?
            ORDER BY price
        """, (symbol, timeframe, bar_time))
        return [{"price": r[0], "bid_vol": r[1], "ask_vol": r[2], "total_vol": r[3]} for r in cursor.fetchall()]
    
    def _calculate_from_footprint(self, bar: dict, footprint: list) -> dict:
        """Calculate POC, VAL, VAH from footprint"""
        if not footprint:
            return self._estimate_profile(bar)
        
        total_volume = sum(f["total_vol"] for f in footprint)
        
        # Find POC (price level with most volume)
        poc_level = max(footprint, key=lambda x: x["total_vol"])["price"]
        poc_volume = max(footprint, key=lambda x: x["total_vol"])["total_vol"]
        
        # Value area = 70% of volume centered around POC
        sorted_by_dist_from_poc = sorted(footprint, key=lambda x: abs(x["price"] - poc_level))
        
        target_vol = total_volume * 0.70
        accumulated = 0
        value_levels = []
        
        for level in sorted_by_dist_from_poc:
            accumulated += level["total_vol"]
            value_levels.append(level["price"])
            if accumulated >= target_vol:
                break
        
        val = min(value_levels)
        vah = max(value_levels)
        
        return {
            "symbol": bar["symbol"],
            "timeframe": bar["timeframe"],
            "bar_time": bar["bar_time"],
            "poc": round(poc_level, 2),
            "val": round(val, 2),
            "vah": round(vah, 2),
            "vah_poc": round(vah - poc_level, 2),
            "val_poc": round(poc_level - val, 2),
            "total_volume": total_volume,
            "interpretation": self._interpret(poc_level, val, vah, bar),
            "direction": "BULLISH" if bar["close"] > bar["open"] else "BEARISH"
        }
    
    def _estimate_profile(self, bar: dict) -> dict:
        """Estimate profile from OHLC when no footprint"""
        high = bar["high"]
        low = bar["low"]
        close = bar["close"]
        volume = bar["volume"] or 1
        
        # Rough estimate: POC near close, VAH/VAL based on range
        range_size = high - low
        if range_size == 0:
            range_size = 0.25
        
        poc = close
        vah = high - range_size * 0.2
        val = low + range_size * 0.2
        
        return {
            "symbol": bar.get("symbol", "ES"),
            "timeframe": bar.get("timeframe", "1min"),
            "bar_time": bar.get("bar_time"),
            "poc": round(poc, 2),
            "val": round(val, 2),
            "vah": round(vah, 2),
            "vah_poc": round(vah - poc, 2),
            "val_poc": round(poc - val, 2),
            "total_volume": volume,
            "interpretation": self._interpret(poc, val, vah, bar),
            "direction": "BULLISH" if close > bar["open"] else "BEARISH",
            "estimated": True
        }
    
    def _interpret(self, poc: float, val: float, vah: float, bar: dict) -> str:
        """Interpret the profile"""
        close = bar["close"]
        
        if close > vah:
            return "ABOVE VALUE - Bullish acceptance"
        elif close < val:
            return "BELOW VALUE - Bearish acceptance"
        elif close > poc:
            return "WITHIN VALUE - Bullish bias"
        else:
            return "WITHIN VALUE - Bearish bias"
    
    def score_all_bars(self, symbol: str, timeframe: str) -> list:
        """Calculate profile for all bars"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT DISTINCT bar_time FROM bars
            WHERE symbol = ? AND timeframe = ? ORDER BY bar_time
        """, (symbol, timeframe))
        bar_times = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        results = []
        for bar_time in bar_times:
            result = self.calculate_profile(symbol, timeframe, bar_time)
            result["symbol"] = symbol
            result["timeframe"] = timeframe
            result["bar_time"] = bar_time
            results.append(result)
            self._save_profile(result)
        
        return results
    
    def _save_profile(self, result: dict):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO volume_profile 
            (symbol, timeframe, bar_time, poc, val, vah, vah_poc, val_poc, total_volume, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.get("symbol"), result.get("timeframe"), result.get("bar_time"),
            result.get("poc"), result.get("val"), result.get("vah"),
            result.get("vah_poc"), result.get("val_poc"),
            result.get("total_volume", 0),
            json.dumps({"interpretation": result.get("interpretation"), "direction": result.get("direction", "NEUTRAL")})
        ))
        conn.commit()
        conn.close()
    
    def get_latest_profile(self, symbol: str, timeframe: str) -> Optional[dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT bar_time, poc, val, vah, vah_poc, val_poc, total_volume, details
            FROM volume_profile
            WHERE symbol = ? AND timeframe = ?
            ORDER BY bar_time DESC LIMIT 1
        """, (symbol, timeframe))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        details = json.loads(row[7]) if row[7] else {}
        return {
            "bar_time": row[0], "poc": row[1], "val": row[2], "vah": row[3],
            "vah_poc": row[4], "val_poc": row[5], "total_volume": row[6],
            "interpretation": details.get("interpretation", ""),
            "direction": details.get("direction", "NEUTRAL")
        }
    
    def get_range_profile(self, symbol: str, timeframe: str, start_time: str, end_time: str) -> Optional[dict]:
        """Get aggregated profile for a time range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT poc, val, vah, total_volume
            FROM volume_profile
            WHERE symbol = ? AND timeframe = ? AND bar_time BETWEEN ? AND ?
            ORDER BY bar_time
        """, (symbol, timeframe, start_time, end_time))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        # Average the levels
        avg_poc = sum(r[0] for r in rows) / len(rows)
        avg_val = sum(r[1] for r in rows) / len(rows)
        avg_vah = sum(r[2] for r in rows) / len(rows)
        total_vol = sum(r[3] for r in rows)
        
        return {
            "start_time": start_time,
            "end_time": end_time,
            "avg_poc": round(avg_poc, 2),
            "avg_val": round(avg_val, 2),
            "avg_vah": round(avg_vah, 2),
            "total_volume": total_vol,
            "bars": len(rows)
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Volume Profile Agent")
    parser.add_argument("--symbol", default="ES")
    parser.add_argument("--timeframe", default="1min")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--bar", help="Specific bar time")
    args = parser.parse_args()
    
    agent = VolumeProfileAgent()
    
    if args.scan:
        results = agent.score_all_bars(args.symbol, args.timeframe)
        print(f"\nVolume Profile: {args.symbol} {args.timeframe}")
        print("=" * 70)
        for r in results[-15:]:
            est = " (est)" if r.get("estimated") else ""
            print(f"{r['bar_time']}: POC={r['poc']} VAL={r['val']} VAH={r['vah']}{est}")
            print(f"  {r['interpretation']} | Vol={r.get('total_volume', 0)}")
    
    elif args.bar:
        result = agent.calculate_profile(args.symbol, args.timeframe, args.bar)
        print(f"\nVolume Profile: {args.bar}")
        print(f"POC: {result.get('poc')}")
        print(f"VAL: {result.get('val')}")
        print(f"VAH: {result.get('vah')}")
        print(f"VAH-POC: {result.get('vah_poc')}")
        print(f"VAL-POC: {result.get('val_poc')}")
        print(f"Interpretation: {result.get('interpretation')}")
    
    else:
        latest = agent.get_latest_profile(args.symbol, args.timeframe)
        if latest:
            print(f"\nLatest: {latest['bar_time']}")
            print(f"POC={latest['poc']} VAL={latest['val']} VAH={latest['vah']}")
            print(f"Interpretation: {latest['interpretation']}")
        else:
            print("No data. Use --scan")


if __name__ == "__main__":
    main()
