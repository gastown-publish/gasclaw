#!/bin/bash
set -euo pipefail

ACTION="${1:-view}"
KEY="${2:-}"
VALUE="${3:-}"
LOADER="/opt/scripts/config-loader.py"

case "$ACTION" in
    view)
        python3 "$LOADER" --view
        ;;
    get)
        if [ -z "$KEY" ]; then
            echo "Usage: config.sh get <key>"
            echo "Example: config.sh get maintenance.loop_interval"
            exit 1
        fi
        python3 "$LOADER" --get "$KEY"
        ;;
    set)
        if [ -z "$KEY" ] || [ -z "$VALUE" ]; then
            echo "Usage: config.sh set <key> <value>"
            echo "Example: config.sh set maintenance.loop_interval 600"
            exit 1
        fi
        python3 "$LOADER" --set "$KEY" "$VALUE"
        echo "Config updated. Change takes effect on next maintenance cycle."
        ;;
    reload)
        echo "Config reloaded from /workspace/config/gasclaw.yaml"
        python3 "$LOADER" --validate
        ;;
    *)
        echo "Unknown action: $ACTION"
        echo "Available: view, get, set, reload"
        exit 1
        ;;
esac
