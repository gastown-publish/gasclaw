#!/bin/bash
# Show status of all Gastown agents
set -euo pipefail

echo "=== Gastown Agents ==="
echo ""

# List all gt agent sessions
SESSIONS=$(tmux list-sessions -F "#{session_name}" 2>/dev/null | grep "^hq-" || true)

if [ -z "$SESSIONS" ]; then
    echo "No active agent sessions found"
    exit 0
fi

printf "%-20s %-10s %-30s\n" "AGENT" "STATUS" "LAST ACTIVITY"
printf "%-20s %-10s %-30s\n" "-----" "------" "-------------"

for sess in $SESSIONS; do
    agent_name="${sess#hq-}"

    # Check if session is alive
    if tmux has-session -t "$sess" 2>/dev/null; then
        status="ALIVE"
        # Get last line of output
        last_line=$(tmux capture-pane -t "$sess" -p 2>/dev/null | grep -v '^$' | tail -1 || echo "no output")
    else
        status="DEAD"
        last_line="—"
    fi

    printf "%-20s %-10s %-30s\n" "$agent_name" "$status" "${last_line:0:30}"
done

echo ""
echo "Total: $(echo "$SESSIONS" | wc -l) agent(s)"
