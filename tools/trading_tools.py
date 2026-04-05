#!/usr/bin/env python3
"""
Trading Desk Tools
==================
Function tools for OpenCode to interact with trading system.
Integrates Execution, Order Flow, and Session Intelligence.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# Import our modules
from execution.execution import OrderExecutor, RiskManager, get_executor, get_risk_manager
from orderflow.orderflow import OrderFlowAnalyzer, get_analyzer
from session_intel.session_intel import SessionIntelligence, Session, get_session_intelligence

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# EXECUTION TOOLS
# =============================================================================

def execute_order(symbol: str, action: str, quantity: int, 
                  order_type: str = "MARKET",
                  price: float = None, 
                  stop_price: float = None,
                  target_price: float = None) -> Dict:
    """
    Execute a trade order via NinjaTrader 8.
    
    Args:
        symbol: Trading symbol (e.g., "ES", "6E", "GC", "CL")
        action: "BUY" or "SELL"
        quantity: Number of contracts
        order_type: "MARKET", "LIMIT", or "STOP"
        price: Limit price (required for LIMIT orders)
        stop_price: Stop loss price
        target_price: Take profit price
    
    Returns:
        dict with execution status and details
    """
    order = {
        "symbol": symbol.upper(),
        "action": action.upper(),
        "quantity": quantity,
        "order_type": order_type.upper(),
    }
    
    if price:
        order["price"] = price
    if stop_price:
        order["stop_price"] = stop_price
    if target_price:
        order["target_price"] = target_price
    
    # Validate with risk manager
    risk_mgr = get_risk_manager()
    validation = risk_mgr.validate_order(order)
    
    if not validation.get("valid"):
        return {
            "success": False,
            "error": validation.get("reason"),
            "order": order
        }
    
    # Execute
    executor = get_executor()
    result = executor.send_order(order)
    
    if result.get("status") == "filled":
        risk_mgr.add_position(order)
        return {
            "success": True,
            "order_id": result.get("order_id"),
            "message": result.get("message"),
            "timestamp": result.get("timestamp"),
            "risk_manager_warning": None
        }
    else:
        return {
            "success": False,
            "error": result.get("message"),
            "order": order
        }


def get_connection_status() -> Dict:
    """Check connection status to NinjaTrader."""
    executor = get_executor()
    connected = executor.is_connected()
    
    return {
        "nt8_connected": connected,
        "timestamp": datetime.now().isoformat(),
        "message": "Connected to NinjaTrader" if connected else "Not connected to NinjaTrader"
    }


def connect_nt8(host: str = "localhost", port: int = 36973) -> Dict:
    """Connect to NinjaTrader 8 Desktop API."""
    executor = get_executor()
    success = executor.connect()
    
    return {
        "success": success,
        "host": host,
        "port": port,
        "message": f"Connected to NT8 at {host}:{port}" if success else "Failed to connect"
    }


def disconnect_nt8() -> Dict:
    """Disconnect from NinjaTrader."""
    executor = get_executor()
    executor.disconnect()
    
    return {
        "success": True,
        "message": "Disconnected from NinjaTrader"
    }


# =============================================================================
# ORDER FLOW TOOLS
# =============================================================================

def analyze_order_flow(price: float, volume: int, bid: float, ask: float) -> Dict:
    """
    Analyze a tick for order flow signals.
    
    Args:
        price: Current price
        volume: Tick volume
        bid: Current bid
        ask: Current ask
    
    Returns:
        dict with order flow metrics and signals
    """
    analyzer = get_analyzer()
    metrics = analyzer.add_tick(price, volume, bid, ask)
    
    return {
        "delta": metrics.delta,
        "cumulative_delta": metrics.cumulative_delta,
        "buy_volume": metrics.buy_volume,
        "sell_volume": metrics.sell_volume,
        "volume_imbalance": round(metrics.volume_imbalance, 3),
        "absorption_detected": metrics.is_absorption,
        "institutional_activity": metrics.is_institutional,
        "direction_bias": metrics.direction_bias,
        "timestamp": datetime.now().isoformat()
    }


def get_order_flow_summary() -> Dict:
    """Get summary of current order flow."""
    analyzer = get_analyzer()
    
    return {
        "cumulative_delta": analyzer.cumulative_delta,
        "buy_volume": analyzer.session_buy_volume,
        "sell_volume": analyzer.session_sell_volume,
        "ticks_analyzed": len(analyzer.ticks),
        "session_active": len(analyzer.ticks) > 0
    }


def reset_order_flow() -> Dict:
    """Reset order flow analysis for new session."""
    analyzer = get_analyzer()
    analyzer.reset()
    
    return {
        "success": True,
        "message": "Order flow reset"
    }


# =============================================================================
# SESSION INTELLIGENCE TOOLS
# =============================================================================

def set_midnight_open(price: float) -> Dict:
    """Set the midnight opening price for ICT analysis."""
    si = get_session_intelligence()
    si.set_midnight_open(price)
    
    return {
        "success": True,
        "midnight_open": price,
        "message": f"Midnight open set to {price}"
    }


def record_session_range(session: str, high: float, low: float) -> Dict:
    """
    Record a session's high/low range.
    
    Args:
        session: "ASIAN", "LONDON", or "NEW_YORK"
        high: Session high
        low: Session low
    """
    si = get_session_intelligence()
    
    # Convert string to Session enum
    session_enum = Session(session.upper().replace("_", "_"))
    
    si.record_session_range(session_enum, high, low)
    
    return {
        "success": True,
        "session": session.upper(),
        "high": high,
        "low": low,
        "range": high - low,
        "midpoint": (high + low) / 2
    }


def add_liquidity_zone(level: float, zone_type: str) -> Dict:
    """
    Add a liquidity zone for sweep detection.
    
    Args:
        level: Price level
        zone_type: "buy_stop", "sell_stop", "accumulation", "distribution"
    """
    si = get_session_intelligence()
    si.add_liquidity_zone(level, zone_type)
    
    return {
        "success": True,
        "level": level,
        "zone_type": zone_type,
        "message": f"Liquidity zone added: {zone_type} @ {level}"
    }


def detect_fvg(candle1_low: float, candle1_high: float,
               candle2_low: float, candle2_high: float,
               candle3_low: float, candle3_high: float) -> Dict:
    """
    Detect Fair Value Gap from 3 candles.
    
    Args:
        candle1: First candle (oldest)
        candle2: Second candle (middle)
        candle3: Third candle (most recent)
    """
    si = get_session_intelligence()
    
    c1 = {"low": candle1_low, "high": candle1_high}
    c2 = {"low": candle2_low, "high": candle2_high}
    c3 = {"low": candle3_low, "high": candle3_high}
    
    gap = si.detect_fair_value_gap(c1, c2, c3)
    
    if gap:
        return {
            "fvg_detected": True,
            "type": "bullish" if gap.high > gap.low else "bearish",
            "high": gap.high,
            "low": gap.low,
            "midpoint": gap.midpoint,
            "size": gap.size
        }
    else:
        return {
            "fvg_detected": False,
            "message": "No FVG detected in these candles"
        }


def get_daily_bias(current_price: float) -> Dict:
    """Get daily bias based on ICT methodology."""
    si = get_session_intelligence()
    bias = si.get_daily_bias(current_price)
    
    return {
        "bias": bias["bias"],
        "reasons": bias["reason"],
        "levels": bias["levels"],
        "timestamp": datetime.now().isoformat()
    }


def check_sweeps(current_price: float) -> Dict:
    """Check for liquidity sweeps and FVG fills at current price."""
    si = get_session_intelligence()
    
    sweeps = si.check_liquidity_sweeps(current_price)
    fills = si.check_fvg_fills(current_price)
    
    return {
        "sweeps": sweeps,
        "fvg_fills": fills,
        "timestamp": datetime.now().isoformat()
    }


def get_trade_setup(current_price: float, direction: str) -> Dict:
    """
    Get ICT trade setup.
    
    Args:
        current_price: Current market price
        direction: "long" or "short"
    """
    si = get_session_intelligence()
    setup = si.get_trade_setup(current_price, direction)
    
    return {
        "direction": setup["direction"],
        "entry": setup["entry"],
        "stop": setup["stop"],
        "target": setup["target"],
        "invalidation": setup["invalidiation"],
        "notes": setup["notes"],
        "timestamp": datetime.now().isoformat()
    }


def get_current_session() -> Dict:
    """Get current trading session."""
    si = get_session_intelligence()
    session = si.get_current_session()
    
    return {
        "current_session": session.value,
        "timestamp": datetime.now().isoformat()
    }


def reset_session_intel() -> Dict:
    """Reset session intelligence for new day."""
    si = get_session_intelligence()
    si.reset()
    
    return {
        "success": True,
        "message": "Session intelligence reset for new day"
    }


# =============================================================================
# COMBINED ANALYSIS
# =============================================================================

def full_trade_analysis(symbol: str, current_price: float,
                        bid: float, ask: float,
                        session_high: float = None,
                        session_low: float = None) -> Dict:
    """
    Complete trade analysis combining all modules.
    
    Args:
        symbol: Trading symbol
        current_price: Current price
        bid: Current bid
        ask: Current ask
        session_high: Optional session high
        session_low: Optional session low
    """
    si = get_session_intelligence()
    analyzer = get_analyzer()
    
    # Get order flow
    of_summary = analyzer.get_order_flow_summary()
    
    # Get bias
    bias = si.get_daily_bias(current_price)
    
    # Check sweeps
    sweeps = si.check_liquidity_sweeps(current_price)
    fills = si.check_fvg_fills(current_price)
    
    # Calculate spread
    spread = ask - bid
    
    return {
        "symbol": symbol.upper(),
        "price": current_price,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "order_flow": of_summary,
        "bias": bias["bias"],
        "bias_reasons": bias["reason"],
        "levels": bias["levels"],
        "sweeps": sweeps,
        "fvg_fills": fills,
        "session_high": session_high,
        "session_low": session_low,
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# TOOL REGISTRY (for OpenCode)
# =============================================================================

TOOLS = [
    {
        "name": "execute_order",
        "description": "Execute a trade order via NinjaTrader 8",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading symbol (ES, 6E, GC, CL)"},
                "action": {"type": "string", "enum": ["BUY", "SELL"], "description": "Trade direction"},
                "quantity": {"type": "integer", "description": "Number of contracts"},
                "order_type": {"type": "string", "enum": ["MARKET", "LIMIT", "STOP"], "default": "MARKET"},
                "price": {"type": "number", "description": "Limit price (for LIMIT orders)"},
                "stop_price": {"type": "number", "description": "Stop loss price"},
                "target_price": {"type": "number", "description": "Take profit price"}
            },
            "required": ["symbol", "action", "quantity"]
        }
    },
    {
        "name": "get_connection_status",
        "description": "Check connection status to NinjaTrader 8",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "analyze_order_flow",
        "description": "Analyze a price tick for order flow signals",
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {"type": "number", "description": "Current price"},
                "volume": {"type": "integer", "description": "Tick volume"},
                "bid": {"type": "number", "description": "Current bid"},
                "ask": {"type": "number", "description": "Current ask"}
            },
            "required": ["price", "volume", "bid", "ask"]
        }
    },
    {
        "name": "get_daily_bias",
        "description": "Get daily bias based on ICT methodology",
        "input_schema": {
            "type": "object",
            "properties": {
                "current_price": {"type": "number", "description": "Current market price"}
            },
            "required": ["current_price"]
        }
    },
    {
        "name": "get_trade_setup",
        "description": "Get ICT trade setup for long or short",
        "input_schema": {
            "type": "object",
            "properties": {
                "current_price": {"type": "number"},
                "direction": {"type": "string", "enum": ["long", "short"]}
            },
            "required": ["current_price", "direction"]
        }
    },
    {
        "name": "set_midnight_open",
        "description": "Set midnight opening price for ICT analysis",
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {"type": "number", "description": "Midnight open price"}
            },
            "required": ["price"]
        }
    },
    {
        "name": "record_session_range",
        "description": "Record a session's high/low range",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "enum": ["ASIAN", "LONDON", "NEW_YORK"]},
                "high": {"type": "number"},
                "low": {"type": "number"}
            },
            "required": ["session", "high", "low"]
        }
    },
    {
        "name": "full_trade_analysis",
        "description": "Complete analysis combining order flow, bias, and levels",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "current_price": {"type": "number"},
                "bid": {"type": "number"},
                "ask": {"type": "number"},
                "session_high": {"type": "number"},
                "session_low": {"type": "number"}
            },
            "required": ["symbol", "current_price", "bid", "ask"]
        }
    }
]


if __name__ == "__main__":
    # Test
    print("Testing Trading Tools...")
    print(f"Connection status: {get_connection_status()}")
    print(f"Session: {get_current_session()}")
    print(f"Order flow summary: {get_order_flow_summary()}")
