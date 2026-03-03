#!/bin/bash
# Gastown status report — sends to the gastown Telegram topic
# Runs every N minutes from the entrypoint loop
set -euo pipefail

exec python3 /opt/scripts/gastown-status.py
