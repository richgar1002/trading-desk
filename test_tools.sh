#!/bin/bash
# Test Trading Desk Tools

cd /tmp/trading-desk

echo "=== Testing Trading Desk Tools ==="
echo ""

# Test 1: Connection status
echo "[1] Connection Status:"
python3 -c "from tools.trading_tools import get_connection_status; print(get_connection_status())"

# Test 2: Session info
echo ""
echo "[2] Current Session:"
python3 -c "from tools.trading_tools import get_current_session; print(get_current_session())"

# Test 3: Set midnight open
echo ""
echo "[3] Set Midnight Open:"
python3 -c "from tools.trading_tools import set_midnight_open; print(set_midnight_open(1.0850))"

# Test 4: Record session range
echo ""
echo "[4] Record London Session:"
python3 -c "from tools.trading_tools import record_session_range; print(record_session_range('LONDON', 1.0900, 1.0800))"

# Test 5: Get daily bias
echo ""
echo "[5] Daily Bias at 1.0850:"
python3 -c "from tools.trading_tools import get_daily_bias; print(get_daily_bias(1.0850))"

# Test 6: Get trade setup
echo ""
echo "[6] Long Setup at 1.0920:"
python3 -c "from tools.trading_tools import get_trade_setup; print(get_trade_setup(1.0920, 'long'))"

echo ""
echo "=== All Tests Complete ==="
