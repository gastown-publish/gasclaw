#!/bin/bash
# Check Kimi API key pool status
set -euo pipefail

echo "=== Key Pool Status ==="
echo ""

# Use gasclaw CLI for consistent output
if command -v gasclaw &> /dev/null; then
    gasclaw keys
else
    echo "Error: gasclaw CLI not found"
    exit 1
fi
