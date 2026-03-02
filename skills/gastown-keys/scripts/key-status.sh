#!/bin/bash
# Check Kimi API key pool status
set -euo pipefail

STATE_FILE="${HOME}/.gasclaw/key-rotation.json"

echo "=== Key Pool Status ==="
echo ""

if [ -f "$STATE_FILE" ]; then
    echo "State file: $STATE_FILE"
    echo ""

    # Check if file is readable and non-empty
    if [ ! -r "$STATE_FILE" ]; then
        echo "Error: Cannot read state file (permission denied)"
        exit 1
    fi

    if [ ! -s "$STATE_FILE" ]; then
        echo "State file is empty — key pool not initialized yet"
        exit 0
    fi

    # Parse with python (always available)
    python3 -c "
import json, time, sys
try:
    with open('$STATE_FILE', 'r') as f:
        state = json.load(f)
except json.JSONDecodeError as e:
    print(f'Error: Invalid JSON in state file: {e}', file=sys.stderr)
    sys.exit(1)
except OSError as e:
    print(f'Error: Cannot read state file: {e}', file=sys.stderr)
    sys.exit(1)

last_used = state.get('last_used', {})
rate_limited = state.get('rate_limited', {})
now = time.time()

print(f'Total tracked keys: {len(last_used)}')
print()

rl_count = 0
for h, ts in rate_limited.items():
    age = now - ts
    if age < 300:
        rl_count += 1
        remaining = int(300 - age)
        print(f'  Key {h}: RATE LIMITED (cooldown: {remaining}s remaining)')
    else:
        print(f'  Key {h}: available (cooldown expired)')

print()
print(f'Available: {len(last_used) - rl_count}')
print(f'Rate-limited: {rl_count}')
" || exit 1
else
    echo "No state file found — key pool not initialized yet"
fi
