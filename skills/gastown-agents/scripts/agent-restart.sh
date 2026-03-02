#!/bin/bash
# Restart a specific Gastown agent
set -euo pipefail

AGENT="${1:?Usage: agent-restart.sh <agent-name>}"

echo "=== Restarting Agent: $AGENT ==="

case "$AGENT" in
    mayor)
        echo "Stopping mayor..."
        gt mayor stop 2>/dev/null || true
        echo "Starting mayor..."
        gt mayor start --agent kimi-claude
        echo "Mayor restarted."
        ;;
    daemon)
        echo "Stopping daemon..."
        gt daemon stop 2>/dev/null || true
        echo "Starting daemon..."
        gt daemon start
        echo "Daemon restarted."
        ;;
    *)
        # Generic agent restart via gt
        echo "Restarting $AGENT via gt handoff..."
        gt handoff "$AGENT" 2>/dev/null || echo "Failed to restart $AGENT"
        ;;
esac
