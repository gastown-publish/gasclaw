#!/usr/bin/env bash
# Validate OpenClaw configuration against documented requirements.
# Run after ANY change to openclaw.json or gasclaw.yaml.
#
# Usage:
#   bash scripts/validate-openclaw-config.sh           # local
#   docker exec <container> bash /opt/gasclaw/scripts/validate-openclaw-config.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'
ERRORS=0
WARNINGS=0

pass() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; WARNINGS=$((WARNINGS + 1)); }
fail() { echo -e "${RED}✗${NC} $1"; ERRORS=$((ERRORS + 1)); }

echo "=== OpenClaw Config Validation ==="
echo ""

OC_CONFIG="${OPENCLAW_CONFIG:-$(openclaw config file 2>/dev/null || echo "$HOME/.openclaw/openclaw.json")}"

if [ ! -f "$OC_CONFIG" ]; then
    fail "Config file not found: $OC_CONFIG"
    exit 1
fi
pass "Config file exists: $OC_CONFIG"

# Validate JSON syntax
if python3 -c "import json; json.load(open('$OC_CONFIG'))" 2>/dev/null; then
    pass "Valid JSON"
else
    fail "Invalid JSON in $OC_CONFIG"
    exit 1
fi

# Extract and validate Telegram config
python3 << PYEOF
import json, sys

with open("$OC_CONFIG") as f:
    cfg = json.load(f)

tg = cfg.get("channels", {}).get("telegram", {})
if not tg:
    print("\033[0;31m✗\033[0m No channels.telegram section found")
    sys.exit(1)

errors = 0
warnings = 0

def p(msg): print(f"\033[0;32m✓\033[0m {msg}")
def w(msg):
    global warnings
    print(f"\033[0;33m⚠\033[0m {msg}")
    warnings += 1
def f(msg):
    global errors
    print(f"\033[0;31m✗\033[0m {msg}")
    errors += 1

# --- Telegram channel ---

if tg.get("enabled") is True:
    p("Telegram channel enabled")
else:
    f("Telegram channel not enabled (channels.telegram.enabled)")

if tg.get("botToken"):
    p("Bot token present")
else:
    f("Missing botToken (channels.telegram.botToken)")

# --- DM policy ---
dm_policy = tg.get("dmPolicy", "pairing")
allow_from = tg.get("allowFrom", [])

if dm_policy == "open":
    if "*" in allow_from:
        p(f"dmPolicy={dm_policy}, allowFrom includes '*'")
    else:
        f(f"dmPolicy=open requires allowFrom to include '*', got: {allow_from}")
elif dm_policy == "allowlist":
    numeric_ids = [x for x in allow_from if isinstance(x, (int, str)) and str(x).lstrip("-").isdigit()]
    if numeric_ids:
        p(f"dmPolicy=allowlist, allowFrom has {len(numeric_ids)} numeric ID(s)")
    else:
        f("dmPolicy=allowlist but allowFrom has no valid numeric IDs")
    for entry in allow_from:
        s = str(entry)
        if s.startswith("-"):
            f(f"allowFrom contains group chat ID '{s}' — allowFrom is for DM user IDs only. Group config goes in channels.telegram.groups")
elif dm_policy == "pairing":
    p("dmPolicy=pairing (default)")
elif dm_policy == "disabled":
    p("dmPolicy=disabled")
else:
    f(f"Invalid dmPolicy: '{dm_policy}' (valid: open, allowlist, pairing, disabled)")

# --- Group policy ---
group_policy = tg.get("groupPolicy", "allowlist")
valid_group_policies = ("open", "allowlist", "disabled")
if group_policy in valid_group_policies:
    p(f"groupPolicy={group_policy}")
else:
    f(f"Invalid groupPolicy: '{group_policy}' (valid: {', '.join(valid_group_policies)})")

# --- Groups config ---
groups = tg.get("groups", {})
if groups:
    for gid, gcfg in groups.items():
        rm = gcfg.get("requireMention", True)
        if rm is False:
            p(f"groups[{gid}].requireMention=false (bot replies without @mention)")
        else:
            w(f"groups[{gid}].requireMention=true (bot requires @mention to reply in groups)")
else:
    w("No channels.telegram.groups config — bot will require @mention in groups (default)")

# --- groupAllowFrom validation ---
group_allow = tg.get("groupAllowFrom", [])
for entry in group_allow:
    s = str(entry)
    if s.startswith("-"):
        f(f"groupAllowFrom contains '{s}' which looks like a group chat ID — groupAllowFrom is for user IDs only")

# --- Streaming ---
streaming = tg.get("streaming", "partial")
if streaming in ("off", "partial", "block", "progress"):
    p(f"streaming={streaming}")
else:
    f(f"Invalid streaming value: '{streaming}'")

# --- Messages config ---
messages = cfg.get("messages", {})
ack = messages.get("ackReactionScope", "")
if ack:
    p(f"messages.ackReactionScope={ack}")

# --- Gateway ---
gw = cfg.get("gateway", {})
if gw.get("port"):
    p(f"gateway.port={gw['port']}")

# --- Summary ---
print("")
if errors > 0:
    print(f"\033[0;31m{errors} error(s)\033[0m, {warnings} warning(s)")
    sys.exit(1)
elif warnings > 0:
    print(f"\033[0;32m0 errors\033[0m, \033[0;33m{warnings} warning(s)\033[0m")
else:
    print(f"\033[0;32mAll checks passed\033[0m")
PYEOF

echo ""

# Run openclaw doctor (non-interactive) if available
if command -v openclaw &>/dev/null; then
    echo "=== OpenClaw Doctor ==="
    openclaw doctor --non-interactive 2>&1 | grep -E "(ok|warn|error|Channel|Telegram|Session|Agent)" || true
    echo ""
    echo "=== Channel Probe ==="
    openclaw channels status --probe 2>&1 | grep -E "(configured|running|probe|canReadAll|allowUnmentioned)" || true
fi

echo ""
echo "Done."
