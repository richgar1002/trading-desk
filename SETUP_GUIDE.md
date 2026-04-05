# Trading Desk - OpenCode Setup Guide

## Current Best Setup: Ollama Cloud

**$20/month** gives you access to the latest models:
- Gemma 4 (27B, fast MoE)
- GLM 5 (9B)
- Kimi k2.5 (20B)
- Qwen 3 (14B/32B)
- + full model library

---

## Setup Steps

### 1. Install OpenCode
```bash
npm install -g opencode-ai
```

### 2. Get Ollama Cloud API Key
1. Go to https://cloud.ollama.com/settings
2. Copy your API key

### 3. Set API Key
```bash
export OLLAMA_API_KEY="your_ollama_cloud_key"
```

### 4. Copy Trading Tools
```bash
mkdir -p ~/.config/opencode/tools
cp -r /tmp/trading-desk/opencode_tools/trading_tools.ts ~/.config/opencode/tools/
```

### 5. Launch OpenCode
```bash
opencode
```

Inside OpenCode:
- `/models` to see available models
- Search for `ollama-cloud:` to see Ollama models
- Select a model and start trading

---

## Alternative: MiniMax Direct

**$10/month** for 1500 calls per 5hr block

```bash
export MINIMAX_API_KEY="sk-cp-QoyOYMiLwnAI8_gbzubiBcChIBO4hQ2EKwSCqoDRFYNJaW3b2rCj98mkgvropZy9Pwpg5SmWz7CB7WH_kA9-EcVXdr1xmxZDJ7vQc8Nd0sJvuKjtFGibEFA"
opencode --model minimax:minimax-m2.7
```

---

## Trading Tools Available

### Execution
- `execute_order` - Send orders to NinjaTrader 8
- `get_connection_status` - Check NT8 connection
- `connect_nt8` / `disconnect_nt8` - Manage connection

### Order Flow
- `analyze_order_flow` - Analyze tick data for delta/absortion
- `get_order_flow_summary` - Current session summary
- `reset_order_flow` - Reset for new session

### Session Intelligence (ICT)
- `set_midnight_open` - Set midnight price
- `record_session_range` - Record Asian/London/NY H/L
- `add_liquidity_zone` - Track sweep zones
- `detect_fvg` - Find Fair Value Gaps
- `get_daily_bias` - Bullish/bearish/mixed bias
- `get_trade_setup` - Entry, stop, target, invalidation
- `check_sweeps` - Detect sweeps and FVG fills
- `get_current_session` - Current trading session
- `full_trade_analysis` - Complete analysis

---

## Example Prompts

```
# Check connection
"Check if NinjaTrader is connected"

# Get bias
"What's the daily bias for EUR/USD at 1.0850?"

# Long setup
"Give me a long setup if 6E breaks above London high"

# Execute trade
"Buy 1 lot of ES at market with 10 point stop"

# Full analysis
"Analyze 6E: price 1.0890, bid 1.0890, ask 1.0891"
```

---

## Ollama Cloud Models for Trading

| Model | Best For | Context |
|-------|----------|---------|
| `qwen3:14b` | Complex analysis, debates | 128K |
| `gemma3-27b-it:4b` | Fast tasks, summarization | 256K |
| `glm-5:9b` | General reasoning | 128K |
| `kimi-k2.5:20b` | Long context analysis | 200K |

---

## Files Location

| Component | Path |
|----------|------|
| Trading Tools (TS) | `/tmp/trading-desk/opencode_tools/trading_tools.ts` |
| Python Backend | `/tmp/trading-desk/tools/trading_tools.py` |
| OpenCode Config | `/tmp/trading-desk/opencode.json` |
| This Guide | `/tmp/trading-desk/SETUP_GUIDE.md` |
