#!/bin/bash
# Check current versions of all dependencies
# Each command has a 30s timeout to prevent cron job hangs
set -euo pipefail

# timeout_wrapper name cmd [args...]
# Runs cmd with 30s timeout, prints name + version or "not available"
timeout_wrapper() {
    local name="$1"
    shift
    local cmd=("$@")
    echo -n "$name: "
    local out
    local rc
    out=$(timeout 30 "${cmd[@]}" 2>&1) && rc=0 || rc=$?
    if [ $rc -eq 0 ]; then
        echo "$out" | head -1  # first line only
    elif [ $rc -eq 124 ]; then
        echo "timeout (>30s)"
    else
        echo "not available"
    fi
}

echo "=== Dependency Versions ==="
echo ""

timeout_wrapper "gt" gt --version
timeout_wrapper "claude" claude --version
timeout_wrapper "openclaw" openclaw --version
timeout_wrapper "dolt" dolt version
timeout_wrapper "kimigas" kimigas --version