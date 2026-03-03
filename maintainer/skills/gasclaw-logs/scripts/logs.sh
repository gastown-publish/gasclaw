#!/bin/bash
set -euo pipefail

SOURCE="${1:-all}"
LINES="${2:-50}"
LOG_DIR="/workspace/logs"

show_log() {
    local name="$1"
    local file="$2"
    echo "=== $name ==="
    if [ -f "$file" ]; then
        tail -"$LINES" "$file"
    else
        echo "(no log file yet)"
    fi
    echo ""
}

case "$SOURCE" in
    startup)  show_log "Startup"  "$LOG_DIR/startup.log" ;;
    claude)   show_log "Claude Code" "$LOG_DIR/claude-code.log" ;;
    gateway)  show_log "OpenClaw Gateway" "$LOG_DIR/openclaw-gateway.log" ;;
    tests)    show_log "Test Results" "$LOG_DIR/test-results.log" ;;
    all)
        show_log "Startup"  "$LOG_DIR/startup.log"
        show_log "Claude Code" "$LOG_DIR/claude-code.log"
        show_log "OpenClaw Gateway" "$LOG_DIR/openclaw-gateway.log"
        show_log "Test Results" "$LOG_DIR/test-results.log"
        ;;
    *)
        echo "Unknown source: $SOURCE"
        echo "Available: startup, claude, gateway, tests, all"
        exit 1
        ;;
esac
