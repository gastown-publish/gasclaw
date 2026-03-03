#!/bin/bash
set -euo pipefail

ACTION="${1:-status}"
STATE_DIR="/workspace/state"

case "$ACTION" in
    status)
        echo "=== Maintenance Status ==="
        if [ -f "$STATE_DIR/paused" ]; then
            echo "Mode: PAUSED"
        else
            echo "Mode: ACTIVE"
        fi

        if [ -f "$STATE_DIR/claude.pid" ]; then
            PID=$(cat "$STATE_DIR/claude.pid")
            if kill -0 "$PID" 2>/dev/null; then
                echo "Agent: RUNNING (PID $PID)"
            else
                echo "Agent: STOPPED (stale PID $PID)"
            fi
        else
            echo "Agent: NO PID FILE"
        fi

        if [ -f "$STATE_DIR/maintenance.json" ]; then
            python3 -c "
import json
with open('$STATE_DIR/maintenance.json') as f:
    s = json.load(f)
print(f\"Last run: {s.get('last_run', 'never')}\")
print(f\"Result: {s.get('last_result', 'unknown')}\")
print(f\"Total cycles: {s.get('total_cycles', 0)}\")
print(f\"PRs merged: {s.get('total_prs_merged', 0)}\")
"
        else
            echo "No maintenance history yet"
        fi

        INTERVAL=$(python3 /opt/scripts/config-loader.py --get maintenance.loop_interval 2>/dev/null || echo "300")
        echo "Interval: ${INTERVAL}s"
        ;;

    trigger)
        touch "$STATE_DIR/trigger-now"
        echo "Maintenance cycle triggered. Will run on next check."
        ;;

    pause)
        touch "$STATE_DIR/paused"
        echo "Maintenance paused. Use 'resume' to continue."
        ;;

    resume)
        rm -f "$STATE_DIR/paused"
        echo "Maintenance resumed."
        ;;

    frequency)
        INTERVAL="${2:?Usage: maintenance.sh frequency <seconds>}"
        python3 /opt/scripts/config-loader.py --set maintenance.loop_interval "$INTERVAL"
        echo "Maintenance interval set to ${INTERVAL}s"
        ;;

    restart)
        if [ -f "$STATE_DIR/claude.pid" ]; then
            PID=$(cat "$STATE_DIR/claude.pid")
            if kill -0 "$PID" 2>/dev/null; then
                kill "$PID" 2>/dev/null || true
                echo "Killed Claude Code agent (PID $PID)"
            fi
            rm -f "$STATE_DIR/claude.pid"
        fi
        # The maintenance loop in entrypoint.sh will restart it
        echo "Agent will restart on next cycle."
        ;;

    *)
        echo "Unknown action: $ACTION"
        echo "Available: status, trigger, pause, resume, frequency, restart"
        exit 1
        ;;
esac
