#!/usr/bin/env python3
"""
NinjaTrader CSV Importer
Imports orderflow/footprint data from NinjaTrader exports into SQLite
"""

import sqlite3
import csv
import os
import re
from datetime import datetime
from typing import Optional, Tuple

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

class CSVImporter:
    """Import NinjaTrader orderflow CSV into database"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Ensure database exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        with open("/tmp/trading-desk/database/schema.sql") as f:
            conn.executescript(f.read())
        conn.close()
    
    def detect_format(self, filepath: str) -> dict:
        """
        Detect CSV format from NinjaTrader export.
        Returns format info dict.
        """
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader, [])
            
        # Normalize headers
        headers_lower = [h.lower().strip() for h in headers]
        
        format_info = {
            "type": "unknown",
            "symbol": "UNKNOWN",
            "timeframe": "1min",
            "has_footprint": False,
            "column_map": {}
        }
        
        # Map common column names
        column_mapping = {
            "time": ["time", "datetime", "date", "timestamp", "bar time"],
            "price": ["price", "last", "close"],
            "bid_vol": ["bid vol", "bid volume", "sell vol", "selling volume"],
            "ask_vol": ["ask vol", "ask volume", "buy vol", "buying volume"],
            "delta": ["delta", "net delta", "cum delta"],
            "total_vol": ["total vol", "total volume", "volume", "vol"],
            "open": ["open", "o"],
            "high": ["high", "h"],
            "low": ["low", "l"],
            "close": ["close", "c"]
        }
        
        for standard_name, aliases in column_mapping.items():
            for i, h in enumerate(headers_lower):
                if h in aliases:
                    format_info["column_map"][standard_name] = i
                    break
        
        # Detect if footprint (has price level data) or bar data
        if "price" in format_info["column_map"] and "bid_vol" in format_info["column_map"]:
            format_info["has_footprint"] = True
            format_info["type"] = "footprint"
        elif "open" in format_info["column_map"] and "close" in format_info["column_map"]:
            format_info["type"] = "bars"
        
        return format_info
    
    def import_csv(self, filepath: str, symbol: str = None, timeframe: str = None) -> dict:
        """
        Import CSV file into database.
        Returns import statistics.
        """
        if not os.path.exists(filepath):
            return {"error": f"File not found: {filepath}"}
        
        # Detect format
        fmt = self.detect_format(filepath)
        
        # Override symbol/timeframe if provided
        if symbol:
            fmt["symbol"] = symbol
        if timeframe:
            fmt["timeframe"] = timeframe
        
        # Generate import batch ID
        batch_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.path.basename(filepath)}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Log import
        cursor.execute("""
            INSERT INTO imports (filename, symbol, timeframe, status)
            VALUES (?, ?, ?, 'processing')
        """, (os.path.basename(filepath), fmt.get("symbol"), fmt.get("timeframe")))
        import_id = cursor.lastrowid
        
        try:
            rows_imported = 0
            
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                
                if fmt["type"] == "footprint":
                    rows_imported = self._import_footprint(conn, cursor, reader, headers, fmt, batch_id)
                elif fmt["type"] == "bars":
                    rows_imported = self._import_bars(conn, cursor, reader, headers, fmt, batch_id)
                else:
                    raise ValueError(f"Unknown CSV format: {headers}")
            
            # Mark import complete
            cursor.execute("""
                UPDATE imports SET rows_imported = ?, status = 'complete'
                WHERE id = ?
            """, (rows_imported, import_id))
            
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "batch_id": batch_id,
                "rows_imported": rows_imported,
                "type": fmt["type"],
                "symbol": fmt["symbol"],
                "timeframe": fmt["timeframe"]
            }
            
        except Exception as e:
            cursor.execute("""
                UPDATE imports SET status = 'error', error = ?
                WHERE id = ?
            """, (str(e), import_id))
            conn.commit()
            conn.close()
            return {"error": str(e)}
    
    def _import_footprint(self, conn, cursor, reader, headers: list, fmt: dict, batch_id: str) -> int:
        """Import footprint (price-level) data"""
        col_map = fmt["column_map"]
        rows = 0
        
        # Get column indices
        time_idx = col_map.get("time", 0)
        price_idx = col_map.get("price", 1)
        bid_idx = col_map.get("bid_vol", 2)
        ask_idx = col_map.get("ask_vol", 3)
        delta_idx = col_map.get("delta")
        total_idx = col_map.get("total_vol")
        
        for row in reader:
            if len(row) <= max(time_idx, price_idx, bid_idx, ask_idx):
                continue
            
            try:
                bar_time = self._parse_time(row[time_idx])
                price = float(row[price_idx])
                bid_vol = int(float(row[bid_idx])) if row[bid_idx] else 0
                ask_vol = int(float(row[ask_idx])) if row[ask_idx] else 0
                delta = int(float(row[delta_idx])) if delta_idx is not None and row[delta_idx] else (ask_vol - bid_vol)
                total_vol = int(float(row[total_idx])) if total_idx is not None and row[total_idx] else (bid_vol + ask_vol)
                
                cursor.execute("""
                    INSERT OR IGNORE INTO raw_footprint
                    (import_batch, symbol, timeframe, bar_time, price, bid_vol, ask_vol, delta, total_vol)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (batch_id, fmt["symbol"], fmt["timeframe"], bar_time, price, bid_vol, ask_vol, delta, total_vol))
                rows += 1
                
            except (ValueError, IndexError):
                continue
        
        return rows
    
    def _import_bars(self, conn, cursor, reader, headers: list, fmt: dict, batch_id: str) -> int:
        """Import bar-level data"""
        col_map = fmt["column_map"]
        rows = 0
        
        time_idx = col_map.get("time", 0)
        open_idx = col_map.get("open", 1)
        high_idx = col_map.get("high", 2)
        low_idx = col_map.get("low", 3)
        close_idx = col_map.get("close", 4)
        vol_idx = col_map.get("total_vol", 5)
        bid_idx = col_map.get("bid_vol")
        ask_idx = col_map.get("ask_vol")
        delta_idx = col_map.get("delta")
        
        for row in reader:
            if len(row) <= max(time_idx, close_idx):
                continue
            
            try:
                bar_time = self._parse_time(row[time_idx])
                open_price = float(row[open_idx])
                high = float(row[high_idx])
                low = float(row[low_idx])
                close = float(row[close_idx])
                volume = int(float(row[vol_idx])) if vol_idx is not None and row[vol_idx] else 0
                bid_vol = int(float(row[bid_idx])) if bid_idx is not None and row[bid_idx] else 0
                ask_vol = int(float(row[ask_idx])) if ask_idx is not None and row[ask_idx] else 0
                delta = int(float(row[delta_idx])) if delta_idx is not None and row[delta_idx] else (ask_vol - bid_vol)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO bars
                    (symbol, timeframe, bar_time, open, high, low, close, volume, bid_vol, ask_vol, delta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (fmt["symbol"], fmt["timeframe"], bar_time, open_price, high, low, close, volume, bid_vol, ask_vol, delta))
                rows += 1
                
            except (ValueError, IndexError):
                continue
        
        return rows
    
    def _parse_time(self, time_str: str) -> str:
        """Parse various time formats to ISO string"""
        time_str = time_str.strip()
        
        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        
        # Return as-is if no format matched
        return time_str


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import NinjaTrader CSV")
    parser.add_argument("file", help="CSV file path")
    parser.add_argument("--symbol", "-s", default="ES", help="Symbol (default: ES)")
    parser.add_argument("--timeframe", "-t", default="5min", help="Timeframe (default: 5min)")
    parser.add_argument("--detect", "-d", action="store_true", help="Detect format only")
    args = parser.parse_args()
    
    importer = CSVImporter()
    
    if args.detect:
        fmt = importer.detect_format(args.file)
        print(f"Detected format: {fmt['type']}")
        print(f"Symbol: {fmt['symbol']}")
        print(f"Timeframe: {fmt['timeframe']}")
        print(f"Has footprint: {fmt['has_footprint']}")
        print(f"Column map: {fmt['column_map']}")
        return
    
    result = importer.import_csv(args.file, args.symbol, args.timeframe)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Success! Imported {result['rows_imported']} rows")
        print(f"Batch: {result['batch_id']}")
        print(f"Type: {result['type']}")
        print(f"Symbol: {result['symbol']}")
        print(f"Timeframe: {result['timeframe']}")


if __name__ == "__main__":
    main()
