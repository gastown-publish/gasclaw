#!/bin/bash
# Check current versions of all dependencies
set -euo pipefail

echo "=== Dependency Versions ==="
echo ""

for cmd_pair in "gt:gt --version" "claude:claude --version" "openclaw:openclaw --version" "dolt:dolt version" "kimigas:kimigas --version"; do
    name="${cmd_pair%%:*}"
    cmd="${cmd_pair#*:}"
    echo -n "$name: "
    eval "$cmd" 2>/dev/null || echo "not installed"
done
