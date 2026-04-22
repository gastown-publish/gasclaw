#!/bin/bash
# Apply updates to all dependencies
# Each command has a 120s timeout to prevent cron hangs
set -euo pipefail

apply_with_timeout() {
    local name="$1"
    shift
    local cmd=("$@")
    echo -n "Updating $name... "
    local out
    local rc
    out=$(timeout 120 "${cmd[@]}" 2>&1) && rc=0 || rc=$?
    if [ $rc -eq 0 ]; then
        echo "ok"
    elif [ $rc -eq 124 ]; then
        echo "TIMEOUT (>120s) — skipped"
    else
        echo "failed — $out"
    fi
}

echo "=== Applying Updates ==="
echo ""

apply_with_timeout "gt" gt self-update
apply_with_timeout "Claude Code" npm update -g @anthropic-ai/claude-code
apply_with_timeout "OpenClaw" npm update -g openclaw
apply_with_timeout "KimiGas" pip install --upgrade kimi-cli

echo ""
echo "=== Update Complete ==="