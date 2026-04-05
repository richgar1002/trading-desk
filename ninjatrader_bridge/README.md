# NinjaTrader 8 Bridge for TradingAgents

## Overview

This bridge connects TradingAgents multi-agent framework to **NinjaTrader 8 Order Flow Suite** (free with PA account).

## Two FREE Options

### Option 1: NinjaTrader Desktop API (Direct TCP)
**Cost: FREE** - Built into NinjaTrader 8

Uses NinjaTrader's native TCP API to connect directly:
- Market data streaming
- Order placement
- Position tracking

**Setup:**
1. Enable API in NinjaTrader: Tools > NinjaTrader Options > API > Enable
2. Note the port (default: 7899)
3. Run the bridge

**Pros:** No extra software, fully free
**Cons:** Requires exact protocol implementation

### Option 2: File-Based Data Export (Recommended)
**Cost: FREE** - Uses NinjaScript file export

Create a NinjaScript indicator that writes OHLCV/orderflow data to CSV files that Python reads.

**Pros:** Simple, reliable, full control
**Cons:** Slight delay (real-time to ~1sec)

### Option 3: CrossTrade API (Paid)
**Cost: $49/mo** - Only if you need TradingView integration

Uses CrossTrade WebSocket API for full automation.

## Quick Start (File-Based - Easiest)

### Step 1: Create NinjaScript Indicator in NinjaTrader

In NinjaTrader 8, create a new indicator:

```csharp
// ExportOrderFlow.cs
namespace NinjaTrader.NinjaScript.Indicators
{
    public class ExportOrderFlow : Indicator
    {
        private StreamWriter writer;
        
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ExportOrderFlow";
            }
            else if (State == State.DataLoaded)
            {
                string path = NinjaTrader.Core.Globals.UserDataFolder + "OrderFlowExport.csv";
                writer = new StreamWriter(path, false);
                writer.WriteLine("Time,Bid,Ask,Last,Volume,BidSize,AskSize");
            }
        }
        
        protected override void OnBarUpdate()
        {
            // Export current bar data
            if (writer != null)
            {
                writer.WriteLine($"{Time[0]},{GetCurrentBid()},{GetCurrentAsk()},{Close[0]},{Volume[0]},{BidSize[0]},{AskSize[0]}");
                writer.Flush();
            }
        }
        
        protected override void OnDestroy()
        {
            if (writer != null) writer.Close();
        }
    }
}
```

### Step 2: Python reads the CSV

```python
import pandas as pd
import time

def read_ninjatrader_export():
    while True:
        try:
            df = pd.read_csv("~/AppData/Roaming/NinjaTrader/logs/OrderFlowExport.csv")
            latest = df.iloc[-1]
            print(f"Bid: {latest['Bid']}, Ask: {latest['Ask']}")
        except:
            pass
        time.sleep(1)
```

## Integration with TradingAgents

```python
from tradingagents_integration import NinjaTraderTradingAgents

system = NinjaTraderTradingAgents()
await system.initialize()

# Run AI-powered analysis
result = await system.analyze_instrument("ES 06-26")
print(result["decision"])
```

## Available Instruments (NinjaTrader 8)

| Category | Symbols |
|----------|---------|
| Equity Index | ES, MES, MNQ, RTY |
| Treasury | ZN, ZF, ZB |
| Energy | CL, NG, QM |
| Metals | GC, SI, PL |
| Forex | 6E, 6J, 6B, 6A, 6N |

## Files

- `ninjatrader_desktop_api.py` - Free Desktop API bridge (TCP)
- `ninjatrader_bridge.py` - CrossTrade WebSocket bridge
- `ninjatrader_tools.py` - TradingAgents tool wrappers
- `tradingagents_integration.py` - Full integration system

## NinjaTrader Setup Checklist

1. ✅ Download NinjaTrader 8 (free with PA account)
2. ✅ Enable API: Tools > NinjaTrader Options > API
3. ✅ Configure data feed (Rithmic, CQG, etc.)
4. ✅ Add Order Flow Suite indicators
5. ✅ (Optional) Create file export indicator

## Cost Summary

| Component | Cost |
|-----------|------|
| NinjaTrader 8 | FREE (PA account) |
| Order Flow Suite | FREE (PA account) |
| Rithmic Data | FREE (via Apex) |
| Python/Ollama | FREE (local) |
| **TOTAL** | **$0/mo** ✅

Compare to original plan:
- Quantower: $50/mo
- Orderflow software: $300+/mo
- Rithmic API: $100+/mo

**Savings: $450+/month**
