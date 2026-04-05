# Quantower Data Export Setup Guide

## Step 1: Enable History Exporter
1. Open Quantower
2. Go to: Menu > Miscellaneous Panels > History Exporter
3. The panel will open

## Step 2: Create Export Task
1. Click "Create a New Task"
2. For each symbol, configure:
   - **Instrument**: Search and select your symbol (e.g., 6E, GC, MCL)
   - **Timeframe**: 1 minute (1min) for orderflow analysis
   - **Data Type**: Last (price trades)
   - **Date Range**: Set to include all available history

## Step 3: Add Your Symbols
For Richard's watchlist:

### Forex Futures
- 6E (EUR) - CME
- 6B (GBP) - CME
- 6J (JPY) - CME
- 6A (AUD) - CME
- 6N (NZD) - CME

### Index Futures
- MES (S&P 500 E-mini) - CME
- MNQ (Nasdaq E-mini) - CME
- MYM (Micro Dow) - CBOT

### Energy Futures
- MCL (Crude Oil WTI) - NYMEX
- NG (Natural Gas) - NYMEX
- BZ (Brent Crude) - ICE

### Metals Futures
- GC (Gold) - COMEX
- MGC (Micro Gold) - COMEX
- SI (Silver) - COMEX

## Step 4: Configure Export Location
1. In History Exporter, click the folder icon
2. Set export directory to: ~/Quantower/Exports
3. Data will be saved as: {SYMBOL}_{TIMEFRAME}.csv

## Step 5: Verify
Check the files are being created:
```bash
ls -la ~/Quantower/Exports/
```

## Automating Updates
You can set up a cron job to:
1. Trigger Quantower to export new data
2. Copy files to your trading desk data directory
3. Process the data for your session prep

---
Generated for Richard's Trading Desk
