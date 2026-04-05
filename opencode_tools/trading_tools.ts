import { tool } from "@opencode-ai/plugin"
import { exec } from "child_process"
import { promisify } from "util"

const execAsync = promisify(exec)

// Helper to run Python trading tools
async function runTradingTool(functionName: string, args: Record<string, any> = {}): Promise<any> {
  const pythonPath = "/tmp/trading-desk/tools/trading_tools.py"
  const argsStr = Object.entries(args)
    .filter(([_, v]) => v !== undefined && v !== null)
    .map(([k, v]) => `--${k}="${v}"`)
    .join(" ")
  
  try {
    const { stdout } = await execAsync(
      `python3 -c "import sys; sys.path.insert(0, '/tmp/trading-desk'); from tools.trading_tools import ${functionName}; print(${functionName}(${Object.keys(args).map(k => k + '=' + ('string' === typeof args[k] ? f'\"{args[k]}\"' : args[k])).join(', ')}))"`
    )
    return JSON.parse(stdout.trim())
  } catch (error) {
    return { error: String(error) }
  }
}

// =============================================================================
// EXECUTION TOOLS
// =============================================================================

export const executeOrder = tool({
  description: "Execute a trade order via NinjaTrader 8",
  args: {
    symbol: tool.schema.string().describe("Trading symbol (ES, 6E, GC, CL, etc.)"),
    action: tool.schema.enum(["BUY", "SELL"]).describe("Trade direction"),
    quantity: tool.schema.number().describe("Number of contracts"),
    orderType: tool.schema.string().optional().describe("Order type: MARKET, LIMIT, STOP"),
    price: tool.schema.number().optional().describe("Limit price for LIMIT orders"),
    stopPrice: tool.schema.number().optional().describe("Stop loss price"),
    targetPrice: tool.schema.number().optional().describe("Take profit price"),
  },
  async execute(args) {
    return await runTradingTool("execute_order", {
      symbol: args.symbol,
      action: args.action,
      quantity: args.quantity,
      order_type: args.orderType,
      price: args.price,
      stop_price: args.stopPrice,
      target_price: args.targetPrice,
    })
  },
})

export const getConnectionStatus = tool({
  description: "Check connection status to NinjaTrader 8",
  args: {},
  async execute() {
    return await runTradingTool("get_connection_status")
  },
})

export const connectNt8 = tool({
  description: "Connect to NinjaTrader 8 Desktop API",
  args: {
    host: tool.schema.string().optional().describe("Host (default: localhost)"),
    port: tool.schema.number().optional().describe("Port (default: 36973)"),
  },
  async execute(args) {
    return await runTradingTool("connect_nt8", {
      host: args.host,
      port: args.port,
    })
  },
})

export const disconnectNt8 = tool({
  description: "Disconnect from NinjaTrader 8",
  args: {},
  async execute() {
    return await runTradingTool("disconnect_nt8")
  },
})

// =============================================================================
// ORDER FLOW TOOLS
// =============================================================================

export const analyzeOrderFlow = tool({
  description: "Analyze a price tick for order flow signals (delta, absorption, institutional activity)",
  args: {
    price: tool.schema.number().describe("Current price"),
    volume: tool.schema.number().describe("Tick volume"),
    bid: tool.schema.number().describe("Current bid"),
    ask: tool.schema.number().describe("Current ask"),
  },
  async execute(args) {
    return await runTradingTool("analyze_order_flow", {
      price: args.price,
      volume: args.volume,
      bid: args.bid,
      ask: args.ask,
    })
  },
})

export const getOrderFlowSummary = tool({
  description: "Get summary of current order flow analysis",
  args: {},
  async execute() {
    return await runTradingTool("get_order_flow_summary")
  },
})

export const resetOrderFlow = tool({
  description: "Reset order flow analysis for new session",
  args: {},
  async execute() {
    return await runTradingTool("reset_order_flow")
  },
})

// =============================================================================
// SESSION INTELLIGENCE TOOLS
// =============================================================================

export const setMidnightOpen = tool({
  description: "Set midnight opening price for ICT analysis",
  args: {
    price: tool.schema.number().describe("Midnight open price"),
  },
  async execute(args) {
    return await runTradingTool("set_midnight_open", { price: args.price })
  },
})

export const recordSessionRange = tool({
  description: "Record a trading session high/low range",
  args: {
    session: tool.schema.enum(["ASIAN", "LONDON", "NEW_YORK"]).describe("Session name"),
    high: tool.schema.number().describe("Session high"),
    low: tool.schema.number().describe("Session low"),
  },
  async execute(args) {
    return await runTradingTool("record_session_range", {
      session: args.session,
      high: args.high,
      low: args.low,
    })
  },
})

export const addLiquidityZone = tool({
  description: "Add a liquidity zone for sweep detection",
  args: {
    level: tool.schema.number().describe("Price level"),
    zoneType: tool.schema.enum(["buy_stop", "sell_stop", "accumulation", "distribution"]).describe("Zone type"),
  },
  async execute(args) {
    return await runTradingTool("add_liquidity_zone", {
      level: args.level,
      zone_type: args.zoneType,
    })
  },
})

export const detectFvg = tool({
  description: "Detect Fair Value Gap from 3 candles",
  args: {
    candle1Low: tool.schema.number().describe("Candle 1 low price"),
    candle1High: tool.schema.number().describe("Candle 1 high price"),
    candle2Low: tool.schema.number().describe("Candle 2 low price"),
    candle2High: tool.schema.number().describe("Candle 2 high price"),
    candle3Low: tool.schema.number().describe("Candle 3 low price"),
    candle3High: tool.schema.number().describe("Candle 3 high price"),
  },
  async execute(args) {
    return await runTradingTool("detect_fvg", {
      candle1_low: args.candle1Low,
      candle1_high: args.candle1High,
      candle2_low: args.candle2Low,
      candle2_high: args.candle2High,
      candle3_low: args.candle3Low,
      candle3_high: args.candle3High,
    })
  },
})

export const getDailyBias = tool({
  description: "Get daily bias based on ICT methodology (midnight open, session ranges)",
  args: {
    currentPrice: tool.schema.number().describe("Current market price"),
  },
  async execute(args) {
    return await runTradingTool("get_daily_bias", { current_price: args.currentPrice })
  },
})

export const getTradeSetup = tool({
  description: "Get ICT trade setup with entry, stop, target, and invalidation levels",
  args: {
    currentPrice: tool.schema.number().describe("Current price"),
    direction: tool.schema.enum(["long", "short"]).describe("Trade direction"),
  },
  async execute(args) {
    return await runTradingTool("get_trade_setup", {
      current_price: args.currentPrice,
      direction: args.direction,
    })
  },
})

export const checkSweeps = tool({
  description: "Check for liquidity sweeps and FVG fills at current price",
  args: {
    currentPrice: tool.schema.number().describe("Current price"),
  },
  async execute(args) {
    return await runTradingTool("check_sweeps", { current_price: args.currentPrice })
  },
})

export const getCurrentSession = tool({
  description: "Get current trading session (Asian, London, NY)",
  args: {},
  async execute() {
    return await runTradingTool("get_current_session")
  },
})

// =============================================================================
// COMBINED ANALYSIS
// =============================================================================

export const fullTradeAnalysis = tool({
  description: "Complete trade analysis combining order flow, daily bias, and levels",
  args: {
    symbol: tool.schema.string().describe("Trading symbol"),
    currentPrice: tool.schema.number().describe("Current price"),
    bid: tool.schema.number().describe("Bid price"),
    ask: tool.schema.number().describe("Ask price"),
    sessionHigh: tool.schema.number().optional().describe("Session high"),
    sessionLow: tool.schema.number().optional().describe("Session low"),
  },
  async execute(args) {
    return await runTradingTool("full_trade_analysis", {
      symbol: args.symbol,
      current_price: args.currentPrice,
      bid: args.bid,
      ask: args.ask,
      session_high: args.sessionHigh,
      session_low: args.sessionLow,
    })
  },
})

export const resetSessionIntel = tool({
  description: "Reset session intelligence for new trading day",
  args: {},
  async execute() {
    return await runTradingTool("reset_session_intel")
  },
})
