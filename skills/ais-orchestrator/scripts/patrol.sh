#!/bin/bash
# patrol.sh — monitor all ais-managed agent sessions
# Run periodically or as a one-shot check

set -uo pipefail

RATE_LIMIT_PATTERN='rate.?limit|429|overloaded|quota.?exceeded|too many requests|credit balance is too low|insufficient_quota|hit your limit'

echo "=== AIS Patrol $(date +%Y-%m-%dT%H:%M:%S) ==="
echo ""

sessions=$(ais ls 2>/dev/null | tail -n +3 | awk '{print $1}')
if [[ -z "$sessions" ]]; then
  echo "No managed sessions running."
  exit 0
fi

total=0 done_count=0 rate_limited=0 dead=0 active=0

while IFS= read -r sess; do
  [[ -z "$sess" ]] && continue
  total=$((total + 1))

  if ! tmux has-session -t "$sess" 2>/dev/null; then
    echo "  $sess: DEAD"
    dead=$((dead + 1))
    continue
  fi

  output=$(ais inspect "$sess" -n 50 2>/dev/null)

  if echo "$output" | grep -qiE "$RATE_LIMIT_PATTERN"; then
    account=$(tmux show-environment -t "$sess" AIS_ACCOUNT 2>/dev/null | cut -d= -f2)
    echo "  $sess: RATE LIMITED (account: ${account:-?}) — needs rotation"
    rate_limited=$((rate_limited + 1))
  elif echo "$output" | grep -q "TASK COMPLETE"; then
    result=$(echo "$output" | grep 'TASK COMPLETE' | tail -1)
    echo "  $sess: DONE — $result"
    done_count=$((done_count + 1))
  else
    last_line=$(echo "$output" | grep -v '^$' | tail -1)
    echo "  $sess: ACTIVE — ${last_line:0:80}"
    active=$((active + 1))
  fi
done <<< "$sessions"

echo ""
echo "Summary: $total sessions | $active active | $done_count done | $rate_limited rate-limited | $dead dead"
