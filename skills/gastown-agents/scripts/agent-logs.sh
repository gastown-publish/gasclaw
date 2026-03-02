#!/bin/bash
# View logs from a specific Gastown agent
set -euo pipefail

AGENT="${1:?Usage: agent-logs.sh <agent-name> [lines]}"
LINES="${2:-50}"
SESSION="hq-${AGENT}"

echo "=== Logs: $AGENT (last $LINES lines) ==="
echo ""

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session $SESSION not found"
    exit 1
fi

tmux capture-pane -t "$SESSION" -p -S "-${LINES}" 2>/dev/null || echo "Failed to capture pane"
