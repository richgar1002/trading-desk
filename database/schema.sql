-- Orderflow Database Schema
-- SQLite database for multi-agent orderflow analysis

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Raw footprint data from NinjaTrader CSV imports
CREATE TABLE IF NOT EXISTS raw_footprint (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_batch TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bar_time TEXT NOT NULL,
    price REAL NOT NULL,
    bid_vol INTEGER DEFAULT 0,
    ask_vol INTEGER DEFAULT 0,
    delta INTEGER DEFAULT 0,
    total_vol INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(import_batch, symbol, timeframe, bar_time, price)
);

-- Bar-level aggregated data (from raw footprint)
CREATE TABLE IF NOT EXISTS bars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bar_time TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER DEFAULT 0,
    bid_vol INTEGER DEFAULT 0,
    ask_vol INTEGER DEFAULT 0,
    delta INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(symbol, timeframe, bar_time)
);

-- Agent measurements (each agent writes here)
CREATE TABLE IF NOT EXISTS agent_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bar_time TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    score REAL DEFAULT 0.0,
    details TEXT,  -- JSON for additional context
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(symbol, timeframe, bar_time, agent_name)
);

-- Supported agents
CREATE TABLE IF NOT EXISTS agents (
    name TEXT PRIMARY KEY,
    description TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Insert default agents
INSERT OR IGNORE INTO agents (name, description) VALUES
    ('exhaustion', 'Measures buying without price movement, delta divergence'),
    ('absorption', 'Measures large orders hitting, price stalling'),
    ('volume', 'Measures volume spikes and thin book conditions'),
    ('delta', 'Measures aggressive buying vs selling balance'),
    ('liquidity', 'Measures stop runs and weak level sweeps'),
    ('trend', 'Measures directional flow strength'),
    ('footprint', 'Records volume at each price level'),
    ('volume_profile', 'Records POC, VAL, VAH from volume profile'),
    ('vwap', 'Records VWAP levels and deviations');

-- Import tracking
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    symbol TEXT,
    timeframe TEXT,
    rows_imported INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Sessions (for grouping trades/analysis)
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    session_type TEXT,  -- 'asian', 'london', 'ny'
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(date, session_type)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_raw_footprint_bar ON raw_footprint(bar_time);
CREATE INDEX IF NOT EXISTS idx_bars_time ON bars(bar_time);
CREATE INDEX IF NOT EXISTS idx_agent_scores_time ON agent_scores(bar_time);
CREATE INDEX IF NOT EXISTS idx_agent_scores_agent ON agent_scores(agent_name);
