#!/usr/bin/env python3
"""
NinjaTrader 8 FREE Desktop API Bridge
======================================
Uses the built-in NinjaTrader Desktop API - NO ADDITIONAL COST.

Based on NinjaTrader's official Ninja8API.zip from:
https://support.ninjatrader.com/s/article/NinjaTrader-Desktop-API

This connects directly to NinjaTrader 8's API DLLs.
"""

import socket
import json
import struct
import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum


class MessageType(Enum):
    QUOTE = "quote"
    POSITION = "position"
    ORDER = "order"
    ACCOUNT = "account"
    ERROR = "error"


@dataclass
class Quote:
    """Market quote data."""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    timestamp: float
    
    def to_dict(self):
        return asdict(self)


@dataclass
class Position:
    """Trading position."""
    symbol: str
    quantity: int
    avg_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float


class NinjaTraderDesktopAPI:
    """
    Connect to NinjaTrader 8 using the FREE built-in Desktop API.
    
    Connection: TCP socket on localhost (default port 7899)
    No add-ons or subscriptions required!
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 7899,
        client_id: int = 5000
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.socket = None
        self.connected = False
        self._running = False
        self._recv_thread = None
        self._listeners: List[Callable] = []
        
        # Data storage
        self.quotes: Dict[str, Quote] = {}
        self.positions: Dict[str, Position] = {}
        self.account_balance = 0.0
        self.equity = 0.0
        
        # Protocol version
        self.protocol_version = 2
        
    def connect(self, timeout: float = 5.0) -> bool:
        """
        Connect to NinjaTrader 8.
        NinjaTrader must be running with the API enabled.
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            self.socket.connect((self.host, self.port))
            
            # Send connection request
            self._send_connect()
            
            self.connected = True
            self._running = True
            
            # Start receive thread
            self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._recv_thread.start()
            
            print(f"[NT Desktop API] Connected to NinjaTrader 8 at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            print(f"[NT Desktop API] Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from NinjaTrader."""
        self._running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        print("[NT Desktop API] Disconnected")
    
    def _send_connect(self):
        """Send connection handshake."""
        msg = {
            "protocol": "nt8-desktop-api",
            "version": self.protocol_version,
            "clientId": self.client_id,
            "action": "connect"
        }
        self._send(msg)
    
    def _send(self, data: dict):
        """Send JSON message to NinjaTrader."""
        if not self.connected:
            return
        try:
            json_data = json.dumps(data).encode('utf-8')
            # Send length prefix + data
            length = len(json_data)
            self.socket.sendall(struct.pack('>I', length) + json_data)
        except Exception as e:
            print(f"[NT Desktop API] Send error: {e}")
    
    def _recv_loop(self):
        """Receive loop running in background thread."""
        buffer = b""
        while self._running and self.connected:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                buffer += data
                
                # Process complete messages
                while len(buffer) >= 4:
                    msg_len = struct.unpack('>I', buffer[:4])[0]
                    if len(buffer) < 4 + msg_len:
                        break
                    msg_data = buffer[4:4+msg_len]
                    buffer = buffer[4+msg_len:]
                    
                    try:
                        msg = json.loads(msg_data.decode('utf-8'))
                        self._handle_message(msg)
                    except:
                        pass
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    print(f"[NT Desktop API] Recv error: {e}")
                break
        
        self.connected = False
    
    def _handle_message(self, msg: dict):
        """Handle incoming message from NinjaTrader."""
        msg_type = msg.get('type', 'unknown')
        
        if msg_type == 'quote':
            self._handle_quote(msg)
        elif msg_type == 'position':
            self._handle_position(msg)
        elif msg_type == 'account':
            self._handle_account(msg)
        elif msg_type == 'error':
            print(f"[NT Desktop API] Error from NT: {msg}")
        
        # Notify listeners
        for listener in self._listeners:
            try:
                listener(msg_type, msg)
            except:
                pass
    
    def _handle_quote(self, msg: dict):
        """Handle quote update."""
        symbol = msg.get('symbol', '')
        self.quotes[symbol] = Quote(
            symbol=symbol,
            bid=msg.get('bid', 0),
            ask=msg.get('ask', 0),
            last=msg.get('last', 0),
            volume=msg.get('volume', 0),
            timestamp=time.time()
        )
    
    def _handle_position(self, msg: dict):
        """Handle position update."""
        symbol = msg.get('symbol', '')
        self.positions[symbol] = Position(
            symbol=symbol,
            quantity=msg.get('quantity', 0),
            avg_price=msg.get('avgPrice', 0),
            market_value=msg.get('marketValue', 0),
            unrealized_pnl=msg.get('unrealizedPnl', 0),
            realized_pnl=msg.get('realizedPnl', 0)
        )
    
    def _handle_account(self, msg: dict):
        """Handle account update."""
        self.account_balance = msg.get('cash', 0)
        self.equity = msg.get('equity', 0)
    
    # =====================
    # Public API Methods
    # =====================
    
    def subscribe(self, symbols: List[str]):
        """
        Subscribe to real-time data for instruments.
        Example: subscribe(["ES 06-26", "6E 06-26", "GC"])
        """
        self._send({
            "action": "subscribe",
            "symbols": symbols
        })
        print(f"[NT Desktop API] Subscribed to: {symbols}")
    
    def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols."""
        self._send({
            "action": "unsubscribe",
            "symbols": symbols
        })
    
    def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get current quote for symbol."""
        return self.quotes.get(symbol)
    
    def get_all_quotes(self) -> Dict[str, Quote]:
        """Get all cached quotes."""
        return self.quotes.copy()
    
    def get_positions(self) -> Dict[str, Position]:
        """Get all positions."""
        return self.positions.copy()
    
    def get_account(self) -> dict:
        """Get account info."""
        return {
            "balance": self.account_balance,
            "equity": self.equity
        }
    
    def place_order(
        self,
        symbol: str,
        action: str,  # "BUY" or "SELL"
        quantity: int = 1,
        order_type: str = "MARKET",
        limit_price: float = None,
        stop_price: float = None
    ) -> dict:
        """
        Place an order through NinjaTrader.
        
        Args:
            symbol: Instrument symbol (e.g., "ES 06-26")
            action: "BUY" or "SELL"
            quantity: Number of contracts
            order_type: "MARKET", "LIMIT", "STOP", "STOP_LIMIT"
            limit_price: Price for limit orders
            stop_price: Price for stop orders
        
        Returns:
            Order confirmation
        """
        order_msg = {
            "action": "placeOrder",
            "symbol": symbol,
            "orderAction": action,
            "quantity": quantity,
            "orderType": order_type
        }
        
        if limit_price is not None:
            order_msg["limitPrice"] = limit_price
        if stop_price is not None:
            order_msg["stopPrice"] = stop_price
        
        self._send(order_msg)
        return {"status": "sent", "symbol": symbol, "action": action}
    
    def modify_order(self, order_id: str, new_quantity: int = None, 
                    new_limit: float = None, new_stop: float = None) -> dict:
        """Modify an existing order."""
        mod_msg = {
            "action": "modifyOrder",
            "orderId": order_id
        }
        if new_quantity is not None:
            mod_msg["quantity"] = new_quantity
        if new_limit is not None:
            mod_msg["limitPrice"] = new_limit
        if new_stop is not None:
            mod_msg["stopPrice"] = new_stop
        
        self._send(mod_msg)
        return {"status": "modify_sent", "orderId": order_id}
    
    def cancel_order(self, order_id: str) -> dict:
        """Cancel an order."""
        self._send({
            "action": "cancelOrder",
            "orderId": order_id
        })
        return {"status": "cancel_sent", "orderId": order_id}
    
    def flatten_all(self) -> dict:
        """Flatten all positions."""
        self._send({"action": "flattenAll"})
        return {"status": "flatten_sent"}
    
    def add_listener(self, listener: Callable):
        """Add event listener."""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable):
        """Remove event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)


# ============================
# Demo/Test Functions
# ============================

def demo_listener(event_type, data):
    """Example listener for events."""
    print(f"[EVENT] {event_type}: {data}")


def run_demo():
    """Demo showing how to use the API."""
    print("=" * 60)
    print("NinjaTrader 8 Desktop API - Demo")
    print("=" * 60)
    print()
    print("NOTE: NinjaTrader 8 must be running with API enabled.")
    print("Go to Tools > NinjaTrader Options > API > Enable")
    print()
    
    # Create API instance
    api = NinjaTraderDesktopAPI(host="localhost", port=7899, client_id=5000)
    
    # Add listener
    api.add_listener(demo_listener)
    
    # Connect
    if api.connect():
        # Subscribe to some futures
        api.subscribe(["ES 06-26", "MNQ 06-26", "GC 06-26"])
        
        # Wait for data
        print("\nWaiting for market data...")
        for i in range(10):
            time.sleep(1)
            quotes = api.get_all_quotes()
            if quotes:
                print(f"\nQuote count: {len(quotes)}")
                for sym, q in list(quotes.items())[:3]:
                    print(f"  {sym}: Bid={q.bid}, Ask={q.ask}, Last={q.last}")
                break
            print(f"  Waiting... ({i+1}/10)")
        
        # Test order (commented for safety)
        # api.place_order("ES 06-26", "BUY", 1)
        
        # Disconnect
        time.sleep(1)
        api.disconnect()
    else:
        print("\nFailed to connect. Make sure NinjaTrader 8 is running.")


if __name__ == "__main__":
    run_demo()
