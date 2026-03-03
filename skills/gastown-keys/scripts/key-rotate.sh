#!/bin/bash
# Force key rotation by marking current key as rate-limited
set -euo pipefail

echo "=== Force Key Rotation ==="

# Use gasclaw CLI for consistent behavior
if command -v gasclaw &> /dev/null; then
    gasclaw keys --rotate
else
    echo "Error: gasclaw CLI not found"
    exit 1
fi
