#!/usr/bin/env python3
"""
Phase 1: Execution Module
=========================
Handles order execution via NinjaTrader 8 Desktop API.
"""

import json
import socket
import logging
from datetime import datetime
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OrderExecutor:
    """
    Executes orders via NinjaTrader 8 Desktop API.
    Uses TCP connection to NT8's Desktop API (default port 36973).
    """
    
    def __init__(self, host: str = "localhost", port: int = 36973):
        self.host = host
        self.port = port
        self.socket = None
        self._connected = False
        
    def connect(self) -> bool:
        """Connect to NinjaTrader Desktop API."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            self._connected = True
            logger.info(f"Connected to NT8 at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to NT8: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Disconnect from NinjaTrader."""
        if self.socket:
            self.socket.close()
            self._connected = False
            logger.info("Disconnected from NT8")
    
    def is_connected(self) -> bool:
        """Check if connected to NT8."""
        return self._connected
    
    def send_order(self, order: dict) -> dict:
        """
        Send order to NinjaTrader.
        
        Args:
            order: dict with keys:
                - symbol: str (e.g., "ES", "6E", "GC")
                - action: str ("BUY" or "SELL")
                - quantity: int (contracts)
                - order_type: str ("MARKET", "LIMIT", "STOP")
                - price: float (optional, for LIMIT/STOP)
                - stop_price: float (optional, for stop loss)
                - target_price: float (optional, for take profit)
        
        Returns:
            dict with order confirmation or error
        """
        if not self._connected:
            if not self.connect():
                return {"status": "error", "message": "Not connected to NT8"}
        
        try:
            # Format order for NT8
            nt8_order = self._format_nt8_order(order)
            
            # Send order
            self.socket.sendall((json.dumps(nt8_order) + "\n").encode())
            
            # Wait for response
            response = self.socket.recv(4096).decode()
            result = json.loads(response)
            
            logger.info(f"Order sent: {order.get('symbol')} {order.get('action')} {order.get('quantity')}")
            
            return {
                "status": "filled" if result.get("status") == "filled" else "pending",
                "order_id": result.get("order_id", ""),
                "message": f"{order.get('symbol')} {order.get('action')} {order.get('quantity')} @ {order.get('price', 'MARKET')}",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def _format_nt8_order(self, order: dict) -> dict:
        """Format order for NinjaTrader API."""
        return {
            "action": order.get("action", "BUY").upper(),
            "symbol": order.get("symbol", "").upper(),
            "quantity": order.get("quantity", 1),
            "orderType": order.get("order_type", "MARKET").upper(),
            "price": order.get("price"),
            "stopPrice": order.get("stop_price"),
            "targetPrice": order.get("target_price"),
            "tif": order.get("tif", "GTC"),  # Time in force: GTC, DAY, IOC
        }
    
    def cancel_order(self, order_id: str) -> dict:
        """Cancel an existing order."""
        if not self._connected:
            return {"status": "error", "message": "Not connected to NT8"}
        
        try:
            cancel_req = {"action": "CANCEL", "order_id": order_id}
            self.socket.sendall((json.dumps(cancel_req) + "\n").encode())
            response = self.socket.recv(4096).decode()
            return json.loads(response)
        except Exception as e:
            return {"status": "error", "message": str(e)}


class RiskManager:
    """
    Validates orders against risk management rules.
    """
    
    def __init__(self, max_risk_per_trade: float = 100.0, max_daily_loss: float = 500.0):
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.daily_pnl = 0.0
        self.open_positions = []
    
    def validate_order(self, order: dict, account_balance: float = 10000.0) -> dict:
        """
        Validate order against risk rules.
        
        Returns:
            dict with validation result and reason if rejected
        """
        # Check daily loss limit
        if self.daily_pnl <= -self.max_daily_loss:
            return {
                "valid": False,
                "reason": f"Daily loss limit reached (${self.max_daily_loss})"
            }
        
        # Check order has required fields
        required = ["symbol", "action", "quantity"]
        for field in required:
            if field not in order or not order[field]:
                return {"valid": False, "reason": f"Missing required field: {field}"}
        
        # Validate quantity
        if order["quantity"] < 1:
            return {"valid": False, "reason": "Quantity must be at least 1"}
        
        # Validate action
        if order["action"].upper() not in ["BUY", "SELL"]:
            return {"valid": False, "reason": "Action must be BUY or SELL"}
        
        # Check position size against account
        estimated_risk = self._estimate_risk(order, account_balance)
        if estimated_risk > self.max_risk_per_trade:
            return {
                "valid": False,
                "reason": f"Risk ${estimated_risk:.2f} exceeds max ${self.max_risk_per_trade}"
            }
        
        return {"valid": True}
    
    def _estimate_risk(self, order: dict, account_balance: float) -> float:
        """Estimate risk for an order."""
        # Simplified - uses 1% of account as risk baseline
        # Real implementation would calculate based on stop distance
        risk_pct = 0.01
        return account_balance * risk_pct
    
    def update_daily_pnl(self, pnl: float):
        """Update daily P&L tracking."""
        self.daily_pnl += pnl
    
    def add_position(self, position: dict):
        """Track an open position."""
        self.open_positions.append(position)
    
    def remove_position(self, symbol: str):
        """Remove a closed position."""
        self.open_positions = [p for p in self.open_positions if p.get("symbol") != symbol]


# Global instances
_executor = None
_risk_manager = None

def get_executor() -> OrderExecutor:
    """Get or create global executor instance."""
    global _executor
    if _executor is None:
        _executor = OrderExecutor()
    return _executor

def get_risk_manager() -> RiskManager:
    """Get or create global risk manager instance."""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager


if __name__ == "__main__":
    # Test connection
    executor = get_executor()
    print(f"NT8 Connected: {executor.connect()}")
