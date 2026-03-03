#!/bin/bash
set -euo pipefail

SECTION="${1:-all}"
REPO="gastown-publish/gasclaw"
WORKDIR="/workspace/gasclaw"

show_tests() {
    echo "=== Tests ==="
    if [ -f /workspace/logs/test-results.log ]; then
        tail -3 /workspace/logs/test-results.log
    else
        echo "No test results yet"
    fi
    echo ""
}

show_prs() {
    echo "=== Open PRs ==="
    gh pr list --repo "$REPO" --state open --json number,title --template '{{range .}}#{{.number}} {{.title}}{{"\n"}}{{end}}' 2>/dev/null || echo "Unable to fetch PRs"
    echo ""
    echo "=== Recent Merges (last 5) ==="
    gh pr list --repo "$REPO" --state merged --limit 5 --json number,title,mergedAt --template '{{range .}}#{{.number}} {{.title}} ({{.mergedAt}}){{"\n"}}{{end}}' 2>/dev/null || echo "Unable to fetch merges"
    echo ""
}

show_issues() {
    echo "=== Open Issues ==="
    gh issue list --repo "$REPO" --state open --json number,title --template '{{range .}}#{{.number}} {{.title}}{{"\n"}}{{end}}' 2>/dev/null || echo "Unable to fetch issues"
    echo ""
}

show_commits() {
    echo "=== Recent Commits (last 10) ==="
    git -C "$WORKDIR" log --oneline -10 2>/dev/null || echo "Repo not cloned yet"
    echo ""
}

show_agent() {
    echo "=== Claude Code Agent ==="
    if [ -f /workspace/state/claude.pid ]; then
        PID=$(cat /workspace/state/claude.pid)
        if kill -0 "$PID" 2>/dev/null; then
            echo "Status: RUNNING (PID $PID)"
        else
            echo "Status: STOPPED (stale PID $PID)"
        fi
    else
        echo "Status: UNKNOWN (no PID file)"
    fi

    if [ -f /workspace/state/maintenance.json ]; then
        echo "Last maintenance:"
        python3 -c "
import json
with open('/workspace/state/maintenance.json') as f:
    s = json.load(f)
print(f\"  Last run: {s.get('last_run', 'never')}\")
print(f\"  Status: {s.get('status', 'unknown')}\")
print(f\"  Total cycles: {s.get('total_cycles', 0)}\")
print(f\"  PRs merged: {s.get('total_prs_merged', 0)}\")
" 2>/dev/null || echo "  No maintenance data"
    fi

    if [ -f /workspace/state/paused ]; then
        echo "  ** PAUSED **"
    fi
    echo ""
}

show_system() {
    echo "=== System ==="
    echo "Uptime: $(uptime -p 2>/dev/null || uptime)"
    echo "Disk: $(df -h /workspace 2>/dev/null | tail -1 | awk '{print $3 "/" $2 " (" $5 " used)"}')"
    echo "Memory: $(free -h 2>/dev/null | grep Mem | awk '{print $3 "/" $2}')"

    echo ""
    echo "Gateway:"
    if [ -f /workspace/state/gateway.pid ]; then
        GPID=$(cat /workspace/state/gateway.pid)
        if kill -0 "$GPID" 2>/dev/null; then
            echo "  Status: RUNNING (PID $GPID)"
        else
            echo "  Status: STOPPED"
        fi
    else
        echo "  Status: UNKNOWN"
    fi
    echo ""
}

case "$SECTION" in
    all)
        echo "==============================="
        echo "  GASCLAW MAINTAINER DASHBOARD"
        echo "==============================="
        echo ""
        show_tests
        show_prs
        show_issues
        show_commits
        show_agent
        show_system
        ;;
    tests)   show_tests ;;
    prs)     show_prs ;;
    issues)  show_issues ;;
    commits) show_commits ;;
    agent)   show_agent ;;
    system)  show_system ;;
    *)
        echo "Unknown section: $SECTION"
        echo "Available: all, tests, prs, issues, commits, agent, system"
        exit 1
        ;;
esac
