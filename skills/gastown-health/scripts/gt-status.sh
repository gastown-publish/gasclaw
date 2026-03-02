#!/bin/bash
# Quick Gastown status check
set -euo pipefail

DOLT_PORT=${DOLT_PORT:-3307}

echo "=== Gastown Status ==="
echo ""

# Dolt
echo -n "Dolt: "
if dolt sql --port "${DOLT_PORT}" -q "SELECT 1" &>/dev/null; then
    echo "HEALTHY"
else
    echo "DOWN"
fi

# Daemon
echo -n "Daemon: "
if gt daemon status &>/dev/null; then
    echo "RUNNING"
else
    echo "STOPPED"
fi

# Mayor
echo -n "Mayor: "
if tmux has-session -t hq-mayor 2>/dev/null; then
    echo "RUNNING"
else
    echo "STOPPED"
fi

# Agents
echo ""
echo "=== Active Agents ==="
gt status 2>/dev/null || echo "Unable to get agent status"

# Key Pool
echo ""
echo "=== Key Pool ==="
if [ -f ~/.gasclaw/key-rotation.json ]; then
    cat ~/.gasclaw/key-rotation.json
else
    echo "No rotation state file"
fi
