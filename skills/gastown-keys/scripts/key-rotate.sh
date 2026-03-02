#!/bin/bash
# Force key rotation by marking current key as rate-limited
set -euo pipefail

STATE_FILE="${HOME}/.gasclaw/key-rotation.json"

echo "=== Force Key Rotation ==="

if [ ! -f "$STATE_FILE" ]; then
    echo "No state file — nothing to rotate"
    exit 0
fi

# Check if file is readable and writable
if [ ! -r "$STATE_FILE" ]; then
    echo "Error: Cannot read state file (permission denied)"
    exit 1
fi
if [ ! -w "$STATE_FILE" ]; then
    echo "Error: Cannot write state file (permission denied)"
    exit 1
fi

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

# Find the most recently used key and mark it rate-limited
if last_used:
    mru = max(last_used, key=last_used.get)
    rate_limited[mru] = now
    state['rate_limited'] = rate_limited
    try:
        with open('$STATE_FILE', 'w') as f:
            json.dump(state, f, indent=2)
        print(f'Marked key {mru} as rate-limited (5min cooldown)')
        print('Next request will use a different key')
    except OSError as e:
        print(f'Error: Failed to write state file: {e}', file=sys.stderr)
        sys.exit(1)
else:
    print('No keys tracked yet')
" || exit 1
