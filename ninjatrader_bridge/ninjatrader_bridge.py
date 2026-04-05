#!/usr/bin/env python3
"""
NinjaTrader 8 Bridge for TradingAgents
========================================
Connects TradingAgents multi-agent framework to NinjaTrader 8 via CrossTrade WebSocket API.
Provides real-time market data, order execution, and position tracking.
"""

import asyncio
import json
import websockets
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import time

class MessageType(Enum):
    MARKET_DATA = "marketData"
    PNL_UPDATE = "pnlUpdate"
    RPC_RESPONSE = "rpc"
    STATUS = "status"
    ERROR = "error"


@dataclass
class Quote:
    """Represents a market quote."""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    timestamp: datetime
    
    def to_dict(self):
        return asdict(self)


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    quantity: int
    avg_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float


class NinjaTraderBridge:
    """
    Bridge class connecting Python trading systems to NinjaTrader 8.
    Uses CrossTrade WebSocket API for real-time data and order execution.
    """
    
    def __init__(
        self,
        api_token: str,
        endpoint: str = "wss://app.crosstrade.io/ws/stream",
        auto_reconnect: bool = True,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 30.0
    ):
        self.api_token = api_token
        self.endpoint = endpoint
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        
        self.ws = None
        self.connected = False
        self.subscribed_instruments: List[str] = []
        self.last_quote: Dict[str, Quote] = {}
        self.positions: Dict[str, Position] = {}
        self.pnl: Dict[str, float] = {}
        
        self._listeners: List[Callable] = []
        self._running = False
        
    async def connect(self) -> bool:
        """Establish WebSocket connection to NinjaTrader."""
        try:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            self.ws = await websockets.connect(
                self.endpoint,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            self.connected = True
            print(f"[NinjaTrader] Connected to {self.endpoint}")
            await self._notify_listeners("connected", {})
            return True
        except Exception as e:
            print(f"[NinjaTrader] Connection failed: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Close the WebSocket connection."""
        self._running = False
        if self.ws:
            await self.ws.close()
        self.connected = False
        print("[NinjaTrader] Disconnected")
    
    async def subscribe(self, instruments: List[str]) -> bool:
        """
        Subscribe to market data for given instruments.
        Example: ["ES 06-26", "MNQ 06-26", "6E 06-26"]
        """
        if not self.connected:
            print("[NinjaTrader] Not connected, cannot subscribe")
            return False
        
        try:
            msg = {
                "action": "subscribe",
                "instruments": instruments
            }
            await self.ws.send(json.dumps(msg))
            self.subscribed_instruments.extend(instruments)
            print(f"[NinjaTrader] Subscribed to: {instruments}")
            return True
        except Exception as e:
            print(f"[NinjaTrader] Subscribe failed: {e}")
            return False
    
    async def unsubscribe(self, instruments: List[str]) -> bool:
        """Unsubscribe from market data for given instruments."""
        if not self.connected:
            return False
        
        try:
            msg = {
                "action": "unsubscribe",
                "instruments": instruments
            }
            await self.ws.send(json.dumps(msg))
            for inst in instruments:
                if inst in self.subscribed_instruments:
                    self.subscribed_instruments.remove(inst)
            print(f"[NinjaTrader] Unsubscribed from: {instruments}")
            return True
        except Exception as e:
            print(f"[NinjaTrader] Unsubscribe failed: {e}")
            return False
    
    async def stream_pnl(self, enabled: bool = True):
        """Enable or disable P&L streaming."""
        if not self.connected:
            return
        
        msg = {"action": "streamPnl", "enabled": enabled}
        await self.ws.send(json.dumps(msg))
        print(f"[NinjaTrader] P&L streaming: {enabled}")
    
    async def rpc(self, api: str, args: Dict = None, request_id: str = None) -> Optional[Dict]:
        """
        Make an RPC call to NinjaTrader.
        Examples:
            - ListPositions: {"account": "Sim101"}
            - PlaceOrder: {"symbol": "ES 06-26", "quantity": 1, "action": "BUY", "orderType": "MARKET"}
            - GetAccountInfo: {}
        """
        if not self.connected:
            print("[NinjaTrader] Not connected, cannot make RPC call")
            return None
        
        if args is None:
            args = {}
        if request_id is None:
            request_id = f"rpc-{int(time.time())}"
        
        msg = {
            "action": "rpc",
            "id": request_id,
            "api": api,
            "args": args
        }
        
        try:
            await self.ws.send(json.dumps(msg))
            return {"request_id": request_id, "api": api, "sent": True}
        except Exception as e:
            print(f"[NinjaTrader] RPC failed: {e}")
            return None
    
    async def place_order(
        self,
        symbol: str,
        quantity: int,
        action: str,  # "BUY" or "SELL"
        order_type: str = "MARKET",  # "MARKET", "LIMIT", "STOP"
        limit_price: float = None,
        stop_price: float = None,
        account: str = "Sim101"
    ) -> Optional[Dict]:
        """Place a trading order through NinjaTrader."""
        args = {
            "account": account,
            "symbol": symbol,
            "quantity": quantity,
            "action": action,
            "orderType": order_type
        }
        if limit_price:
            args["limitPrice"] = limit_price
        if stop_price:
            args["stopPrice"] = stop_price
        
        return await self.rpc("PlaceOrder", args)
    
    async def listen(self):
        """
        Main listen loop. Must be called while connected.
        Processes incoming messages and notifies listeners.
        """
        self._running = True
        print("[NinjaTrader] Starting listen loop...")
        
        while self._running and self.connected:
            try:
                response = await asyncio.wait_for(self.ws.recv(), timeout=60)
                data = json.loads(response)
                await self._process_message(data)
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                print("[NinjaTrader] Connection closed")
                break
            except Exception as e:
                print(f"[NinjaTrader] Listen error: {e}")
                break
        
        if self.auto_reconnect:
            await self._reconnect()
    
    async def _process_message(self, data: Dict):
        """Process incoming WebSocket message."""
        msg_type = data.get('type')
        
        if msg_type == MessageType.MARKET_DATA.value:
            await self._handle_market_data(data)
        elif msg_type == MessageType.PNL_UPDATE.value:
            await self._handle_pnl_update(data)
        elif 'id' in data and 'data' in data:
            await self._handle_rpc_response(data)
        elif msg_type == MessageType.STATUS.value:
            print(f"[NinjaTrader] Status: {data}")
        
        await self._notify_listeners(msg_type, data)
    
    async def _handle_market_data(self, data: Dict):
        """Handle incoming market data."""
        quotes = data.get('quotes', [])
        for q in quotes:
            symbol = q.get('symbol', 'UNKNOWN')
            self.last_quote[symbol] = Quote(
                symbol=symbol,
                bid=q.get('bid', 0),
                ask=q.get('ask', 0),
                last=q.get('last', 0),
                volume=q.get('volume', 0),
                timestamp=datetime.now()
            )
    
    async def _handle_pnl_update(self, data: Dict):
        """Handle P&L update."""
        accounts = data.get('accounts', {})
        for account_id, pnl_data in accounts.items():
            self.pnl[account_id] = pnl_data.get('unrealizedPnl', 0)
    
    async def _handle_rpc_response(self, data: Dict):
        """Handle RPC response."""
        print(f"[NinjaTrader] RPC Response [{data.get('id')}]: {data.get('data')}")
    
    async def _notify_listeners(self, event_type: str, data: Dict):
        """Notify all registered listeners of events."""
        for listener in self._listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                print(f"[NinjaTrader] Listener error: {e}")
    
    async def _reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        delay = self.reconnect_delay
        print(f"[NinjaTrader] Reconnecting in {delay}s...")
        
        while self.auto_reconnect and not self.connected:
            await asyncio.sleep(delay)
            if await self.connect():
                # Resubscribe to instruments
                if self.subscribed_instruments:
                    await self.subscribe(self.subscribed_instruments)
                break
            delay = min(delay * 2, self.max_reconnect_delay)
    
    def add_listener(self, listener: Callable):
        """Register a listener callback for events."""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable):
        """Remove a listener callback."""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get the last quote for a symbol."""
        return self.last_quote.get(symbol)
    
    def get_all_quotes(self) -> Dict[str, Quote]:
        """Get all current quotes."""
        return self.last_quote.copy()


async def run_demo():
    """Demo function showing basic usage."""
    # Note: Replace with your actual API token
    API_TOKEN = "YOUR_CROSSTRADE_API_TOKEN"
    
    bridge = NinjaTraderBridge(api_token=API_TOKEN)
    
    # Add a listener
    def on_event(event_type, data):
        print(f"[EVENT] {event_type}: {data}")
    
    bridge.add_listener(on_event)
    
    # Connect and subscribe
    if await bridge.connect():
        await bridge.subscribe(["ES 06-26", "MNQ 06-26"])
        await bridge.stream_pnl(True)
        
        # Make some RPC calls
        await bridge.rpc("ListPositions", {"account": "Sim101"})
        await bridge.rpc("GetAccountInfo", {})
        
        # Listen for 60 seconds
        await asyncio.sleep(60)
        
        # Place a test order (commented out for safety)
        # await bridge.place_order("ES 06-26", 1, "BUY")
        
        await bridge.disconnect()


if __name__ == "__main__":
    print("NinjaTrader Bridge - TradingAgents Connector")
    print("=" * 50)
    print("Note: This module requires the CrossTrade NT8 add-on")
    print("and a valid API token from crosstrade.io")
    asyncio.run(run_demo())
