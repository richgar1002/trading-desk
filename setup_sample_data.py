#!/usr/bin/env python3
"""
Setup Script - Creates sample test data for exhaustion agent
"""

import sqlite3
import os
import json
from datetime import datetime, timedelta

DB_PATH = "/tmp/trading-desk/database/orderflow.db"

def create_sample_data():
    """Create sample bar data for testing"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    with open("/tmp/trading-desk/database/schema.sql") as f:
        conn.executescript(f.read())
    
    # Generate 50 bars of sample ES data
    base_price = 5800.00
    now = datetime.now()
    
    bars = []
    for i in range(50):
        bar_time = now - timedelta(minutes=(50 - i) * 5)
        
        # Simulate some exhaustion patterns
        if i % 10 == 5:  # Every 10th bar at position 5 = exhaustion
            open_p = base_price + 2.0
            high = base_price + 2.25
            low = base_price + 1.75
            close = base_price + 1.90  # Stayed high but didn't move much
            volume = 2500  # High volume
            delta = 1800  # High delta (buyers) but price flat
        elif i % 10 == 6:  # Follow through after exhaustion attempt
            open_p = base_price + 1.9
            high = base_price + 3.0
            low = base_price + 1.5
            close = base_price + 2.8  # Big move down
            volume = 3200
            delta = -2200  # Sellers in control
        else:
            open_p = base_price + (i % 5) * 0.5
            high = open_p + 1.5
            low = open_p - 1.0
            close = open_p + (0.5 if i % 3 == 0 else -0.3)
            volume = 1500 + (i % 10) * 100
            delta = (volume // 3) if i % 2 == 0 else -(volume // 3)
        
        bars.append({
            'bar_time': bar_time.strftime("%Y-%m-%d %H:%M:%S"),
            'open': open_p,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'bid_vol': (volume // 2) - delta // 4,
            'ask_vol': (volume // 2) + delta // 4,
            'delta': delta
        })
        
        base_price = close
    
    # Insert bars
    for bar in bars:
        conn.execute("""
            INSERT OR REPLACE INTO bars
            (symbol, timeframe, bar_time, open, high, low, close, volume, bid_vol, ask_vol, delta)
            VALUES ('ES', '5min', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (bar['bar_time'], bar['open'], bar['high'], bar['low'], bar['close'],
              bar['volume'], bar['bid_vol'], bar['ask_vol'], bar['delta']))
    
    conn.commit()
    print(f"Created {len(bars)} sample bars")
    
    # Calculate exhaustion for all bars
    from agents.exhaustion_agent import ExhaustionAgent
    agent = ExhaustionAgent(DB_PATH)
    results = agent.score_all_bars('ES', '5min')
    print(f"Calculated exhaustion for {len(results)} bars")
    
    conn.close()
    return len(bars)

if __name__ == "__main__":
    count = create_sample_data()
    print(f"\nSample data ready. {count} bars in database.")
    print("\nTo start dashboard:")
    print("  cd /tmp/trading-desk/dashboard")
    print("  python3 api_server.py")
    print("\nThen open: http://localhost:8080")
