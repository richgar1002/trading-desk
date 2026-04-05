#!/usr/bin/env python3
"""
Phase 2: Order Flow Module
==========================
Analyzes tape data from NinjaTrader for institutional flow signals.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TickData:
    """Single tick of market data."""
    timestamp: datetime
    price: float
    volume: int
    bid: float
    ask: float
    is_buy_tick: bool = False  # True if uptick (buy pressure), False if downtick (sell pressure)

@dataclass
class OrderFlowMetrics:
    """Order flow analysis results."""
    delta: int = 0              # Net buying/selling pressure
    cumulative_delta: int = 0   # Running delta
    buy_volume: int = 0         # Total buy volume
    sell_volume: int = 0        # Total sell volume
    absorption_score: float = 0.0  # 0-100, higher = more absorption
    imbalance_ratio: float = 0.0   # Buy/sell ratio
    
    # Imbalances
    bid_ask_imbalance: float = 0.0  # Current order book imbalance
    volume_imbalance: float = 0.0    # Recent volume imbalance
    
    # Signals
    is_absorption: bool = False  # Absorption detected
    is_institutional: bool = False  # Likely institutional activity
    direction_bias: str = "neutral"  # "bullish", "bearish", "neutral"


class OrderFlowAnalyzer:
    """
    Analyzes order flow and tape to detect institutional activity.
    """
    
    def __init__(self, lookback_ticks: int = 1000):
        self.lookback_ticks = lookback_ticks
        self.ticks: deque = deque(maxlen=lookback_ticks)
        self.deltas: deque = deque(maxlen=100)
        self.cumulative_delta = 0
        self.session_buy_volume = 0
        self.session_sell_volume = 0
        
    def add_tick(self, price: float, volume: int, bid: float, ask: float) -> OrderFlowMetrics:
        """Add a tick and return updated metrics."""
        is_buy = price > 0  # Simplified - real implementation compares to previous price
        is_uptick = price >= (self.ticks[-1].price if self.ticks else price)
        
        tick = TickData(
            timestamp=datetime.now(),
            price=price,
            volume=volume,
            bid=bid,
            ask=ask,
            is_buy_tick=is_uptick
        )
        self.ticks.append(tick)
        
        # Update volumes
        if is_uptick:
            self.session_buy_volume += volume
        else:
            self.session_sell_volume += volume
        
        # Update delta (positive = buying, negative = selling)
        delta = volume if is_uptick else -volume
        self.cumulative_delta += delta
        self.deltas.append(delta)
        
        return self._calculate_metrics()
    
    def _calculate_metrics(self) -> OrderFlowMetrics:
        """Calculate current order flow metrics."""
        metrics = OrderFlowMetrics()
        
        # Delta calculations
        metrics.delta = self.deltas[-1] if self.deltas else 0
        metrics.cumulative_delta = self.cumulative_delta
        metrics.buy_volume = self.session_buy_volume
        metrics.sell_volume = self.session_sell_volume
        
        # Volume imbalance
        total_vol = self.session_buy_volume + self.session_sell_volume
        if total_vol > 0:
            metrics.volume_imbalance = (self.session_buy_volume - self.session_sell_volume) / total_vol
            metrics.imbalance_ratio = self.session_buy_volume / self.session_sell_volume if self.session_sell_volume > 0 else float('inf')
        
        # Bid/Ask imbalance
        if self.ticks:
            last = self.ticks[-1]
            spread = last.ask - last.bid
            if spread > 0:
                metrics.bid_ask_imbalance = (last.price - last.bid) / spread
        
        # Absorption detection
        metrics.absorption_score = self._detect_absorption()
        metrics.is_absorption = metrics.absorption_score > 70
        
        # Institutional activity detection
        metrics.is_institutional = self._detect_institutional()
        
        # Direction bias
        if metrics.cumulative_delta > 500:
            metrics.direction_bias = "bullish"
        elif metrics.cumulative_delta < -500:
            metrics.direction_bias = "bearish"
        else:
            metrics.direction_bias = "neutral"
        
        return metrics
    
    def _detect_absorption(self) -> float:
        """Detect absorption - when large orders hit but price doesn't move much."""
        if len(self.ticks) < 10:
            return 0.0
        
        # Look at recent ticks
        recent = list(self.ticks)[-10:]
        
        # Calculate volume-weighted price change
        total_volume = sum(t.volume for t in recent)
        if total_volume == 0:
            return 0.0
        
        price_range = max(t.price for t in recent) - min(t.price for t in recent)
        
        # High volume, low price movement = absorption
        avg_volume = total_volume / len(recent)
        volume_ratio = avg_volume / (price_range + 0.0001)
        
        # Score 0-100
        score = min(volume_ratio * 10, 100)
        return score
    
    def _detect_institutional(self) -> bool:
        """Detect likely institutional activity."""
        if len(self.ticks) < 50:
            return False
        
        # Large orders in one direction
        recent_deltas = list(self.deltas)[-20:]
        large_deltas = [d for d in recent_deltas if abs(d) > 100]
        
        if len(large_deltas) >= 3:
            # All in same direction?
            sign = sum(large_deltas) / abs(sum(large_deltas))
            if sign > 0.8:  # 80%+ in one direction
                return True
        
        return False
    
    def get_level_recording(self) -> Dict:
        """Record volume at price levels for identifying stops/ranges."""
        levels = {}
        for tick in self.ticks:
            level = round(tick.price, 2)  # Round to tick value
            if level not in levels:
                levels[level] = {"buy": 0, "sell": 0}
            if tick.is_buy_tick:
                levels[level]["buy"] += tick.volume
            else:
                levels[level]["sell"] += tick.volume
        return levels
    
    def reset(self):
        """Reset for new session."""
        self.ticks.clear()
        self.deltas.clear()
        self.cumulative_delta = 0
        self.session_buy_volume = 0
        self.session_sell_volume = 0


# Global instance
_analyzer = None

def get_analyzer() -> OrderFlowAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = OrderFlowAnalyzer()
    return _analyzer


if __name__ == "__main__":
    # Test
    analyzer = get_analyzer()
    print("OrderFlow analyzer initialized")
