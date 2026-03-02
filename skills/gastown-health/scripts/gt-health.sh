#!/bin/bash
# Deep Gastown health check with activity compliance
set -euo pipefail

DEADLINE=${ACTIVITY_DEADLINE:-3600}

echo "=== Deep Health Check ==="
echo ""

# Service checks
for svc in "dolt sql --port 3307 -q 'SELECT 1'" "gt daemon status" "gt mayor status"; do
    name=$(echo "$svc" | awk '{print $1}')
    echo -n "$name: "
    if eval "$svc" &>/dev/null; then
        echo "OK"
    else
        echo "FAILED"
    fi
done

# Activity compliance
echo ""
echo "=== Activity Compliance (deadline: ${DEADLINE}s) ==="
if [ -d /project/.git ]; then
    LAST_TS=$(git -C /project log -1 --format=%ct 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE=$((NOW - LAST_TS))
    echo "Last commit age: ${AGE}s"
    if [ "$AGE" -le "$DEADLINE" ]; then
        echo "Status: COMPLIANT"
    else
        echo "Status: NOT COMPLIANT — action required!"
    fi
else
    echo "No git repo at /project"
fi

# Agent process check
echo ""
echo "=== Agent Processes ==="
ps aux | grep -E "(claude|kimi|gt)" | grep -v grep || echo "No agent processes found"
