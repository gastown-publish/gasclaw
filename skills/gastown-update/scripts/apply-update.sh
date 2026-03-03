#!/bin/bash
# Apply updates to all dependencies
set -euo pipefail

echo "=== Applying Updates ==="
echo ""

echo "Updating gt..."
gt self-update 2>&1 || echo "gt update failed"

echo ""
echo "Updating Claude Code..."
npm update -g @anthropic-ai/claude-code 2>&1 || echo "claude update failed"

echo ""
echo "Updating OpenClaw..."
npm update -g openclaw 2>&1 || echo "openclaw update failed"

echo ""
echo "Updating KimiGas..."
pip install --upgrade kimi-cli 2>&1 || echo "kimigas update failed"

echo ""
echo "=== Update Complete ==="
