#!/usr/bin/env python3
"""
NinjaTrader Tools for TradingAgents
=====================================
Custom tools that allow TradingAgents to interact with NinjaTrader 8.
These tools provide market data, position tracking, and order execution.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from tradingagents.agents.utils.agent_utils import tool

# Global bridge instance (set by initialize_bridge)
_bridge = None


def initialize_bridge(bridge):
    """Initialize the global bridge instance."""
    global _bridge
    _bridge = bridge


def is_bridge_connected() -> bool:
    """Check if bridge is connected."""
    return _bridge is not None and _bridge.connected


@tool
def get_quote(symbol: str) -> str:
    """
    Get the current quote for a forex or futures instrument.
    
    Args:
        symbol: Instrument symbol (e.g., "ES 06-26", "6E 06-26", "MNQ 06-26", "GC 06-26")
    
    Returns:
        JSON string with bid, ask, last, volume
    """
    if not is_bridge_connected():
        return '{"error": "NinjaTrader not connected"}'
    
    quote = _bridge.get_quote(symbol)
    if quote:
        return f'{{"symbol": "{quote.symbol}", "bid": {quote.bid}, "ask": {quote.ask}, "last": {quote.last}, "volume": {quote.volume}}}'
    return f'{{"error": "No quote for {symbol}"}}'


@tool
def get_quotes(symbols: List[str]) -> str:
    """
    Get current quotes for multiple instruments.
    
    Args:
        symbols: List of instrument symbols
    
    Returns:
        JSON string with quotes for all instruments
    """
    if not is_bridge_connected():
        return '{"error": "NinjaTrader not connected"}'
    
    quotes = {}
    for symbol in symbols:
        quote = _bridge.get_quote(symbol)
        if quote:
            quotes[symbol] = {
                "bid": quote.bid,
                "ask": quote.ask,
                "last": quote.last,
                "volume": quote.volume
            }
    return json.dumps(quotes)


@tool
def subscribe_instruments(instruments: List[str]) -> str:
    """
    Subscribe to real-time data for instruments.
    
    Args:
        instruments: List of instrument symbols to subscribe to
    
    Returns:
        JSON string with subscription status
    """
    if not is_bridge_connected():
        return '{"error": "NinjaTrader not connected"}'
    
    asyncio.create_task(_bridge.subscribe(instruments))
    return f'{{"status": "subscribing", "instruments": {instruments}}}'


@tool
def get_positions(account: str = "Sim101") -> str:
    """
    Get current positions for an account.
    
    Args:
        account: Account ID (default: "Sim101")
    
    Returns:
        JSON string with positions
    """
    if not is_bridge_connected():
        return '{"error": "NinjaTrader not connected"}'
    
    asyncio.create_task(_bridge.rpc("ListPositions", {"account": account}))
    return f'{{"status": "requested", "account": "{account}"}}'


@tool
def place_order(
    symbol: str,
    quantity: int,
    action: str,
    order_type: str = "MARKET",
    limit_price: float = None,
    stop_price: float = None,
    account: str = "Sim101"
) -> str:
    """
    Place a trading order through NinjaTrader.
    
    Args:
        symbol: Instrument symbol (e.g., "ES 06-26", "6E 06-26")
        quantity: Number of contracts
        action: "BUY" or "SELL"
        order_type: "MARKET", "LIMIT", or "STOP"
        limit_price: Limit price (for LIMIT orders)
        stop_price: Stop price (for STOP orders)
        account: Account ID
    
    Returns:
        JSON string with order status
    """
    if not is_bridge_connected():
        return '{"error": "NinjaTrader not connected"}'
    
    asyncio.create_task(_bridge.place_order(
        symbol=symbol,
        quantity=quantity,
        action=action,
        order_type=order_type,
        limit_price=limit_price,
        stop_price=stop_price,
        account=account
    ))
    return f'{{"status": "order_placed", "symbol": "{symbol}", "quantity": {quantity}, "action": "{action}"}}'


@tool
def get_account_info(account: str = "Sim101") -> str:
    """
    Get account information.
    
    Args:
        account: Account ID
    
    Returns:
        JSON string with account info
    """
    if not is_bridge_connected():
        return '{"error": "NinjaTrader not connected"}'
    
    asyncio.create_task(_bridge.rpc("GetAccountInfo", {"account": account}))
    return f'{{"status": "requested", "account": "{account}"}}'


@tool
def stream_pnl(enabled: bool = True) -> str:
    """
    Enable or disable P&L streaming.
    
    Args:
        enabled: True to enable, False to disable
    
    Returns:
        JSON string with status
    """
    if not is_bridge_connected():
        return '{"error": "NinjaTrader not connected"}'
    
    asyncio.create_task(_bridge.stream_pnl(enabled))
    return f'{{"status": "pnl_streaming", "enabled": {enabled}}}'


@tool
def get_available_instruments() -> str:
    """
    Get list of commonly traded futures and forex instruments.
    
    Returns:
        JSON string with instrument categories
    """
    instruments = {
        "futures": {
            "equity_index": ["ES 06-26", "MES 06-26", "MNQ 06-26", "RTY 06-26"],
            "treasury": ["ZN 06-26", "ZF 06-26", "ZB 06-26"],
            "energy": ["CL 06-26", "NG 06-26", "QM 06-26"],
            "metals": ["GC 06-26", "SI 06-26", "PL 06-26"],
            "forex": ["6E 06-26", "6J 06-26", "6B 06-26", "6A 06-26", "6N 06-26"]
        },
        "note": "Format: 'SYMBOL MM-YY' for futures"
    }
    return json.dumps(instruments, indent=2)


import json
