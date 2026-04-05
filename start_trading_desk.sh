#!/bin/bash
# Trading Desk - OpenCode Launcher

echo "=============================================="
echo "  Trading Desk - AI Trading Assistant"
echo "=============================================="
echo ""

# Set API key
export OPENROUTER_API_KEY="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"

# Load trading tools
export OPENCODE_TOOLS="/tmp/trading-desk/opencode_tools"

echo "Models available:"
echo "  - minimax/minimax-m2.7 (complex analysis, 204K context)"
echo "  - google/gemma-4-26b-a4b-it (fast, cheap, 256K context)"
echo ""
echo "Starting OpenCode..."
echo ""

# Launch OpenCode with trading tools
opencode --tools "$OPENCODE_TOOLS"
