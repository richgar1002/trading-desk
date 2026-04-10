# Orderflow Dashboard - Multi-Agent System

## Overview

Multi-agent orderflow analysis system that measures various aspects of market microstructure and combines them for actionable signals.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  DATA INPUT                                             │
│  NinjaTrader CSV → SQLite Database                     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  AGENT LAYER                                           │
│  • Exhaustion Agent (measures buying without movement) │
│  • Absorption Agent (measures large orders stalling)  │
│  • Volume Agent (measures volume spikes)               │
│  • Delta Agent (measures directional flow)             │
│  • Liquidity Agent (measures stop runs)               │
│  • Trend Agent (measures flow strength)               │
│  • Footprint Agent (records volume at price levels)    │
│  • Volume Profile Agent (records POC, VAL, VAH)      │
│  • VWAP Agent (records VWAP deviations)               │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  SHARED DATABASE (SQLite)                              │
│  All agents write scores with timestamps              │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  DASHBOARD                                             │
│  Real-time HTML dashboard with alerts                  │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Setup

```bash
# Create sample data for testing
cd /tmp/trading-desk
python3 setup_sample_data.py

# Start the dashboard
cd dashboard
python3 api_server.py
```

Open http://localhost:8080

### 2. Import Your Data

```bash
# Import NinjaTrader CSV
python3 agents/csv_importer.py /path/to/your/data.csv --symbol ES --timeframe 5min

# Detect format first (dry run)
python3 agents/csv_importer.py /path/to/your/data.csv --detect
```

### 3. Run Agents

```bash
# Calculate exhaustion for all bars
python3 agents/exhaustion_agent.py --symbol ES --timeframe 5min --scan

# Check specific bar
python3 agents/exhaustion_agent.py --symbol ES --timeframe 5min --bar "2024-04-10 09:30"
```

### 4. View Dashboard

Dashboard auto-refreshes every 10 seconds.

Alerts trigger when exhaustion score >= 0.7

## File Structure

```
/tmp/trading-desk/
├── agents/
│   ├── exhaustion_agent.py    # Exhaustion measurement
│   ├── csv_importer.py        # NinjaTrader CSV import
│   └── (future agents)
├── database/
│   ├── schema.sql             # Database structure
│   └── orderflow.db           # SQLite database
├── dashboard/
│   ├── exhaustion_dashboard.html  # Main dashboard
│   └── api_server.py          # REST API server
├── data/
│   └── sample/                # Sample data folder
└── README.md
```

## Database Schema

### Tables

- **bars** - OHLCV + bid/ask/delta per bar
- **raw_footprint** - Raw price-level data from CSV
- **agent_scores** - Agent measurements (agent_name, score, details)
- **agents** - Registry of available agents
- **imports** - Import tracking
- **sessions** - Trading sessions

## NinjaTrader CSV Format

Expected columns:
- Time (required)
- Price or Open/High/Low/Close
- Bid Vol, Ask Vol (for footprint)
- Delta (optional)
- Total Volume

Example export from NinjaTrader:
```
Time,Price,Bid Vol,Ask Vol,Delta,Total Vol
2024-04-10 09:30:00,5800.00,150,200,50,350
...
```

## Exhaustion Agent

### What it measures

**Score 0-1** (0 = directional move, 1 = full exhaustion)

Components:
- **Delta Divergence (35%)** - Price flat but high delta
- **Volume/Movement Ratio (30%)** - High volume, low movement
- **Lingering (20%)** - Price stuck at same level
- **Delta Fade (15%)** - Delta high early, fading later

### Interpretation

| Score | Signal |
|-------|--------|
| 0.0-0.2 | NO EXHAUSTION - Directional intact |
| 0.2-0.4 | LOW EXHAUSTION - Some pressure |
| 0.4-0.6 | MILD EXHAUSTION - Watch for stalling |
| 0.6-0.8 | MODERATE EXHAUSTION - Reversal possible |
| 0.8-1.0 | STRONG EXHAUSTION - Reversal likely |

## Adding More Agents

Future agents follow the same pattern:

```python
class NewAgent:
    name = "new_agent"
    
    def calculate_score(self, symbol, timeframe, bar_time) -> dict:
        # Calculate score
        return {"score": 0.5, "details": {...}}
    
    def score_all_bars(self, symbol, timeframe) -> list:
        # Score all bars
        return results
```

## Next Steps

1. Build Absorption Agent
2. Add more data connectors (direct API)
3. Build AI suggestion layer
4. Add Supabase for cloud sync
5. Build pattern correlation engine

## Notes

- Dashboard is HTML/JS, works in any browser
- SQLite is file-based, portable
- Agents run independently, can be parallelized
- Scores stored with timestamps for historical analysis
