#!/usr/bin/env python3
"""
Phase 3: Session Intelligence Module
=====================================
ICT methodology session analysis and liquidity detection.
"""

import json
import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Session(Enum):
    """Trading sessions."""
    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK = "new_york"
    PRE_NEW_YORK = "pre_new_york"

@dataclass
class SessionRange:
    """High/Low range for a session."""
    session: Session
    high: float
    low: float
    midpoint: float
    midpoint_price: float  # For ICT concepts
    
    @property
    def range_size(self) -> float:
        return self.high - self.low
    
    def is_broken(self, current_price: float) -> bool:
        """Check if range was broken (swept)."""
        return current_price > self.high or current_price < self.low
    
    def contains(self, price: float) -> bool:
        """Check if price is within range."""
        return self.low <= price <= self.high


@dataclass
class LiquidityZone:
    """Liquidity zone for sweeps."""
    level: float
    zone_type: str  # "buy_stop", "sell_stop", "accumulation", "distribution"
    broken: bool = False
    sweep_time: Optional[datetime] = None
    
    def was_swept(self, price: float) -> bool:
        """Check if this zone was swept."""
        if self.zone_type == "buy_stop":
            return price > self.level
        elif self.zone_type == "sell_stop":
            return price < self.level
        return False


@dataclass
class FairValueGap:
    """Fair Value Gap (imbalance) - ICT concept."""
    high: float
    low: float
    midpoint: float
    filled: bool = False
    fill_price: Optional[float] = None
    
    @property
    def size(self) -> float:
        return self.high - self.low
    
    def check_fill(self, current_price: float) -> bool:
        """Check if FVG has been filled."""
        if self.filled:
            return True
        
        # FVG fills when price comes back to it
        if self.high > current_price > self.low:
            self.filled = True
            self.fill_price = current_price
            return True
        return False


class SessionIntelligence:
    """
    ICT-based session analysis.
    Tracks session ranges, liquidity zones, and fair value gaps.
    """
    
    def __init__(self):
        self.sessions: Dict[Session, SessionRange] = {}
        self.liquidity_zones: List[LiquidityZone] = []
        self.fair_value_gaps: List[FairValueGap] = []
        self.midnight_open: Optional[float] = None
        self.current_session: Optional[Session] = None
        
        # Session times (UTC - adjust for your timezone)
        self.session_times = {
            Session.ASIAN: (time(0, 0), time(9, 0)),
            Session.LONDON: (time(8, 0), time(11, 0)),
            Session.PRE_NEW_YORK: (time(11, 0), time(15, 30)),
            Session.NEW_YORK: (time(15, 30), time(21, 0)),
        }
    
    def set_midnight_open(self, price: float):
        """Set the midnight opening price (ICT concept)."""
        self.midnight_open = price
        logger.info(f"Midnight open set: {price}")
    
    def record_session_range(self, session: Session, high: float, low: float):
        """Record a session's high/low range."""
        self.sessions[session] = SessionRange(
            session=session,
            high=high,
            low=low,
            midpoint=(high + low) / 2,
            midpoint_price=high - (high - low) / 2  # ICT midpoint calculation
        )
        logger.info(f"{session.value} range: H={high}, L={low}, Range={high-low}")
    
    def add_liquidity_zone(self, level: float, zone_type: str):
        """Add a liquidity zone (sweep target)."""
        zone = LiquidityZone(level=level, zone_type=zone_type)
        self.liquidity_zones.append(zone)
        logger.info(f"Liquidity zone added: {zone_type} @ {level}")
    
    def detect_fair_value_gap(self, candle1: dict, candle2: dict, candle3: dict) -> Optional[FairValueGap]:
        """
        Detect Fair Value Gap from 3 candles.
        FVG forms when: candle1 closes above/below candle3's wick with gap
        """
        # Bullish FVG: candle3 low > candle1 high
        if candle3.get('low', 0) > candle1.get('high', 0):
            gap = FairValueGap(
                high=candle3.get('low', 0),
                low=candle1.get('high', 0),
                midpoint=((candle3.get('low', 0) + candle1.get('high', 0)) / 2)
            )
            self.fair_value_gaps.append(gap)
            logger.info(f"Bullish FVG detected: {gap.high} - {gap.low}")
            return gap
        
        # Bearish FVG: candle1 low > candle3 high
        if candle1.get('low', 0) > candle3.get('high', 0):
            gap = FairValueGap(
                high=candle1.get('low', 0),
                low=candle3.get('high', 0),
                midpoint=((candle1.get('low', 0) + candle3.get('high', 0)) / 2)
            )
            self.fair_value_gaps.append(gap)
            logger.info(f"Bearish FVG detected: {gap.high} - {gap.low}")
            return gap
        
        return None
    
    def get_current_session(self) -> Session:
        """Get current trading session based on time."""
        now = datetime.utcnow().time()
        for session, (start, end) in self.session_times.items():
            if start <= now < end:
                return session
        return Session.NEW_YORK  # Default to NY if not in a session
    
    def analyze_displacement(self, current_price: float, trigger_price: float) -> Dict:
        """
        ICT Displacement concept - when price moves aggressively through a level.
        Returns analysis of displacement strength.
        """
        if self.midnight_open is None:
            return {"displaced": False, "reason": "No midnight open set"}
        
        # Calculate displacement from midnight open
        displacement = current_price - self.midnight_open
        displacement_pct = (displacement / self.midnight_open) * 100 if self.midnight_open else 0
        
        return {
            "displaced": abs(displacement_pct) > 0.5,  # >0.5% considered displacement
            "displacement": displacement,
            "displacement_pct": displacement_pct,
            "direction": "up" if displacement > 0 else "down"
        }
    
    def get_daily_bias(self, current_price: float) -> Dict:
        """
        Calculate daily bias based on ICT concepts.
        """
        bias = {
            "bias": "neutral",
            "reason": [],
            "levels": {}
        }
        
        # Check against midnight open
        if self.midnight_open:
            if current_price > self.midnight_open:
                bias["bias"] = "bullish"
                bias["reason"].append(f"Above midnight open ({self.midnight_open})")
            else:
                bias["bias"] = "bearish"
                bias["reason"].append(f"Below midnight open ({self.midnight_open})")
        
        # Check today's session ranges
        ny_session = self.sessions.get(Session.NEW_YORK)
        if ny_session:
            if current_price > ny_session.midpoint:
                bias["reason"].append("Above NY midday midpoint")
                if bias["bias"] == "bearish":
                    bias["bias"] = "mixed"
            else:
                bias["reason"].append("Below NY midday midpoint")
        
        bias["levels"]["midnight_open"] = self.midnight_open
        bias["levels"]["ny_high"] = ny_session.high if ny_session else None
        bias["levels"]["ny_low"] = ny_session.low if ny_session else None
        
        return bias
    
    def check_liquidity_sweeps(self, current_price: float) -> List[Dict]:
        """Check if any liquidity zones were swept."""
        sweeps = []
        for zone in self.liquidity_zones:
            if not zone.broken and zone.was_swept(current_price):
                zone.broken = True
                zone.sweep_time = datetime.now()
                sweeps.append({
                    "type": "sweep",
                    "zone_type": zone.zone_type,
                    "level": zone.level,
                    "time": zone.sweep_time.isoformat()
                })
        return sweeps
    
    def check_fvg_fills(self, current_price: float) -> List[Dict]:
        """Check if any FVGs were filled."""
        fills = []
        for gap in self.fair_value_gaps:
            if not gap.filled and gap.check_fill(current_price):
                fills.append({
                    "type": "fvg_fill",
                    "gap": {"high": gap.high, "low": gap.low},
                    "fill_price": gap.fill_price
                })
        return fills
    
    def get_trade_setup(self, current_price: float, direction: str) -> Dict:
        """
        Get ICT trade setup based on current context.
        """
        setup = {
            "direction": direction,
            "entry": None,
            "stop": None,
            "target": None,
            "invalidiation": None,
            "notes": []
        }
        
        ny_session = self.sessions.get(Session.NEW_YORK)
        london_session = self.sessions.get(Session.LONDON)
        
        if direction == "long":
            # Look for buy setups
            if london_session:
                setup["notes"].append(f"London range: {london_session.high} - {london_session.low}")
            
            if ny_session:
                # NY Session Range short (Inducement)
                if current_price < ny_session.low:
                    setup["entry"] = ny_session.low
                    setup["stop"] = ny_session.low - 10
                    setup["target"] = ny_session.midpoint
                    setup["invalidiation"] = ny_session.low - 20
                    setup["notes"].append("NY Range Short (Inducement)")
        
        elif direction == "short":
            # Look for sell setups
            if london_session:
                setup["notes"].append(f"London range: {london_session.high} - {london_session.low}")
            
            if ny_session:
                # NY Session Range long (Inducement)
                if current_price > ny_session.high:
                    setup["entry"] = ny_session.high
                    setup["stop"] = ny_session.high + 10
                    setup["target"] = ny_session.midpoint
                    setup["invalidiation"] = ny_session.high + 20
                    setup["notes"].append("NY Range Long (Inducement)")
        
        return setup
    
    def reset(self):
        """Reset for new trading day."""
        self.sessions.clear()
        self.liquidity_zones.clear()
        self.fair_value_gaps.clear()
        self.midnight_open = None
        logger.info("Session intelligence reset for new day")


# Global instance
_session_intel = None

def get_session_intelligence() -> SessionIntelligence:
    global _session_intel
    if _session_intel is None:
        _session_intel = SessionIntelligence()
    return _session_intel


if __name__ == "__main__":
    # Test
    si = get_session_intelligence()
    si.set_midnight_open(1.0850)
    si.record_session_range(Session.LONDON, 1.0900, 1.0800)
    si.record_session_range(Session.NEW_YORK, 1.0920, 1.0820)
    
    print(f"Current session: {si.get_current_session()}")
    print(f"Daily bias @ 1.0850: {si.get_daily_bias(1.0850)}")
    print(f"Daily bias @ 1.0910: {si.get_daily_bias(1.0910)}")
