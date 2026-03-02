#!/bin/bash
# Force key rotation by marking current key as rate-limited
set -euo pipefail

STATE_FILE="${HOME}/.gasclaw/key-rotation.json"

echo "=== Force Key Rotation ==="

if [ ! -f "$STATE_FILE" ]; then
    echo "No state file — nothing to rotate"
    exit 0
fi

python3 -c "
import json, time
state = json.load(open('$STATE_FILE'))
last_used = state.get('last_used', {})
rate_limited = state.get('rate_limited', {})
now = time.time()

# Find the most recently used key and mark it rate-limited
if last_used:
    mru = max(last_used, key=last_used.get)
    rate_limited[mru] = now
    state['rate_limited'] = rate_limited
    with open('$STATE_FILE', 'w') as f:
        json.dump(state, f, indent=2)
    print(f'Marked key {mru} as rate-limited (5min cooldown)')
    print('Next request will use a different key')
else:
    print('No keys tracked yet')
"
