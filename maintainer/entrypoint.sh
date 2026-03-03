#!/bin/bash
set -euo pipefail

echo "=== Gasclaw Maintainer Agent ==="
echo ""

# --- 1. Init directories ---
mkdir -p /workspace/config /workspace/logs /workspace/state

# Copy default config if missing
if [ ! -f /workspace/config/gasclaw.yaml ]; then
    if [ -f /opt/scripts/gasclaw-defaults.yaml ]; then
        cp /opt/scripts/gasclaw-defaults.yaml /workspace/config/gasclaw.yaml
    else
        cat > /workspace/config/gasclaw.yaml <<'DEFCFG'
maintenance:
  loop_interval: 300
  max_pr_size: 200
  auto_merge: true
  repo: "gastown-publish/gasclaw"
  working_dir: "/workspace/gasclaw"
  branch_prefixes: ["fix/", "feat/", "test/", "docs/", "refactor/"]
claude:
  kimi_base_url: "https://api.kimi.com/coding/"
  dangerously_skip_permissions: true
openclaw:
  gateway_port: 18789
logging:
  level: "INFO"
  log_dir: "/workspace/logs"
DEFCFG
    fi
    echo "Created default config at /workspace/config/gasclaw.yaml"
fi

# --- 2. Load config ---
echo "Loading config..."
MAINTENANCE_INTERVAL=$(python3 /opt/scripts/config-loader.py --get maintenance.loop_interval 2>/dev/null || echo "300")
MAINTENANCE_REPO=$(python3 /opt/scripts/config-loader.py --get maintenance.repo 2>/dev/null || echo "gastown-publish/gasclaw")
KIMI_BASE_URL=$(python3 /opt/scripts/config-loader.py --get claude.kimi_base_url 2>/dev/null || echo "https://api.kimi.com/coding/")
GATEWAY_PORT=$(python3 /opt/scripts/config-loader.py --get openclaw.gateway_port 2>/dev/null || echo "18789")
echo "  maintenance_interval=${MAINTENANCE_INTERVAL}s repo=${MAINTENANCE_REPO}"

# --- 3. Auth ---
: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
: "${KIMI_API_KEY:?KIMI_API_KEY is required}"
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN is required}"
: "${TELEGRAM_CHAT_ID:?TELEGRAM_CHAT_ID is required}"

echo "$GITHUB_TOKEN" | gh auth login --with-token --hostname github.com 2>&1 || true
gh auth status 2>&1 || true
git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"
git config --global user.email "gasclaw-bot@gastown.dev"
git config --global user.name "Gasclaw Maintainer"

# --- 4. Environment for Claude Code ---
export ANTHROPIC_BASE_URL="${KIMI_BASE_URL}"
export ANTHROPIC_API_KEY="${KIMI_API_KEY}"
export DISABLE_COST_WARNINGS=true

# --- 5. Claude Code config ---
export CLAUDE_CONFIG_DIR="$HOME/.claude-config"
mkdir -p "$CLAUDE_CONFIG_DIR"
echo '{}' > "$CLAUDE_CONFIG_DIR/.credentials.json"
FINGERPRINT="${KIMI_API_KEY:(-20)}"
cat > "$CLAUDE_CONFIG_DIR/.claude.json" <<CJSON
{
  "hasCompletedOnboarding": true,
  "bypassPermissionsModeAccepted": true,
  "customApiKeyResponses": {
    "approved": ["${FINGERPRINT}"]
  }
}
CJSON

# --- 6. Helper: send Telegram message ---
tg_send() {
    local msg="$1"
    local topic_type="${2:-discussion}"
    curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d parse_mode=Markdown \
        -d text="$msg" > /dev/null 2>&1 || true
}

# --- 7. Setup Gastown Workspace (/workspace/gt) ---
echo ""
echo "=== Setting up Gastown Workspace ==="
export GT_HOME="/workspace/gt"
mkdir -p "$GT_HOME"
cd "$GT_HOME"

# Initialize gt workspace if needed
if [ ! -d "$GT_HOME/.git" ]; then
    echo "Initializing Gastown workspace at $GT_HOME..."
    cd "$GT_HOME"
    git init
    git config user.email "gasclaw@gastown.dev"
    git config user.name "Gasclaw"
fi

# Setup gt config
mkdir -p "$GT_HOME/.beads"

# Start Dolt SQL server
echo "Starting Dolt SQL server..."
mkdir -p "$GT_HOME/.dolt-data"

# Check if dolt is already running on port 3307
if dolt sql -q "SELECT 1" > /dev/null 2>&1; then
    echo "  ✅ Dolt already running on port 3307"
else
    # Start dolt in background
    nohup dolt sql-server --port 3307 --data-dir "$GT_HOME/.dolt-data" \
        --max-connections 100 --loglevel info \
        > "$GT_HOME/.dolt-data/dolt.log" 2>&1 &
    DOLT_PID=$!
    
    # Wait for dolt to be ready
    for i in {1..10}; do
        sleep 1
        if dolt sql -q "SELECT 1" > /dev/null 2>&1; then
            echo "$DOLT_PID" > "$GT_HOME/.dolt-data/dolt.pid"
            echo "  ✅ Dolt started (PID $DOLT_PID)"
            break
        fi
    done
    
    if ! dolt sql -q "SELECT 1" > /dev/null 2>&1; then
        echo "  ⚠️  Dolt may not have started properly"
    fi
fi

# Setup basic beads for gastown
echo "Setting up beads..."
for bead in hq deacon; do
    if [ ! -d "$GT_HOME/beads_${bead}" ]; then
        echo "  Creating bead: beads_${bead}"
        mkdir -p "$GT_HOME/beads_${bead}" 2>/dev/null || true
    fi
done

# Start gt daemon
echo "Starting gt daemon..."
if ! pgrep -f "gt daemon run" > /dev/null 2>&1; then
    # Start daemon manually since gt daemon start might fail
    nohup gt daemon run > "$GT_HOME/daemon.log" 2>&1 &
    sleep 3
fi

if pgrep -f "gt daemon run" > /dev/null 2>&1; then
    GT_DAEMON_PID=$(pgrep -f "gt daemon run")
    echo "  ✅ gt daemon running (PID $GT_DAEMON_PID)"
    echo "$GT_DAEMON_PID" > "$GT_HOME/daemon.pid"
else
    echo "  ⚠️  gt daemon not running (this is OK for basic maintenance)"
fi

echo "Gastown workspace ready at $GT_HOME"

# --- 8. Run OpenClaw doctor ---
echo ""
echo "Running OpenClaw doctor..."
OPENCLAW_DIR="$HOME/.openclaw"
mkdir -p "$OPENCLAW_DIR/agents/main/agent"
mkdir -p "$OPENCLAW_DIR/agents/main/sessions"
openclaw doctor --fix --yes 2>&1 || true

# --- 9. Write OpenClaw config ---
echo "Writing OpenClaw config..."
AGENT_WORKSPACE="/workspace/agent-workspace"
mkdir -p "$AGENT_WORKSPACE"
cp /opt/agent-soul.md "$AGENT_WORKSPACE/SOUL.md" 2>/dev/null || true
cp /opt/agent-bootstrap.md "$AGENT_WORKSPACE/BOOTSTRAP.md" 2>/dev/null || true
if [ ! -f "$AGENT_WORKSPACE/MEMORY.md" ]; then
    echo "# Gasclaw Maintainer Memory" > "$AGENT_WORKSPACE/MEMORY.md"
fi

python3 << 'PYEOF'
import json, os

openclaw_dir = os.path.expanduser("~/.openclaw")

# models.json — custom Kimi provider
models = {
    "providers": {
        "kimi-coding": {
            "baseUrl": os.environ.get("ANTHROPIC_BASE_URL", "https://api.kimi.com/coding/"),
            "api": "anthropic-messages",
            "models": [{
                "id": "k2p5",
                "name": "Kimi for Coding",
                "reasoning": True,
                "input": ["text", "image"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": 262144,
                "maxTokens": 32768,
            }],
            "apiKey": os.environ["KIMI_API_KEY"],
        }
    }
}
with open(os.path.join(openclaw_dir, "agents/main/agent/models.json"), "w") as f:
    json.dump(models, f, indent=2)

# Read existing config
cfg_path = os.path.join(openclaw_dir, "openclaw.json")
existing = {}
if os.path.exists(cfg_path):
    with open(cfg_path) as f:
        existing = json.load(f)

config = existing.copy()
config["agents"] = {
    "defaults": {
        "model": {"primary": "kimi-coding/k2p5"},
        "models": {"kimi-coding/k2p5": {}},
        "workspace": "/workspace/agent-workspace",
    },
    "list": [{
        "id": "main",
        "identity": {"name": "Gasclaw Maintainer", "emoji": "\U0001f3ed"},
    }],
}

owner_id = os.environ.get("TELEGRAM_CHAT_ID", "")
config["channels"] = {
    "telegram": {
        "botToken": os.environ["TELEGRAM_BOT_TOKEN"],
        "dmPolicy": "allowlist",
        "groupPolicy": "allowlist",
        "allowFrom": [owner_id] if owner_id else [],
    }
}
config["commands"] = {"native": "auto", "nativeSkills": "auto", "restart": True}
config["gateway"] = config.get("gateway", {})
config["gateway"]["port"] = int(os.environ.get("GATEWAY_PORT", "18789"))
config["gateway"]["mode"] = "local"
config["plugins"] = {"slots": {"memory": "none"}}
config["tools"] = {"exec": {"security": "full"}}
config["env"] = {"KIMI_API_KEY": os.environ["KIMI_API_KEY"]}

with open(cfg_path, "w") as f:
    json.dump(config, f, indent=2)

print("OpenClaw config written")
PYEOF

# --- 10. Install skills ---
echo "Installing OpenClaw skills..."
OPENCLAW_SKILLS="$OPENCLAW_DIR/skills"
mkdir -p "$OPENCLAW_SKILLS"
if [ -d /opt/maintainer-skills ]; then
    cp -r /opt/maintainer-skills/* "$OPENCLAW_SKILLS/" 2>/dev/null || true
    find "$OPENCLAW_SKILLS" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
    echo "  Installed: $(ls "$OPENCLAW_SKILLS/" 2>/dev/null | wc -l) skills"
fi

# --- 11. Clone/update gasclaw repo ---
echo "Cloning gasclaw..."
if [ -d /workspace/gasclaw/.git ]; then
    cd /workspace/gasclaw && git pull origin main 2>&1 || true
else
    git clone "https://github.com/${MAINTENANCE_REPO}.git" /workspace/gasclaw
    cd /workspace/gasclaw
fi

# --- 12. Dev setup ---
echo "Setting up dev environment..."
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip --timeout 120 --retries 5 -q
pip install --timeout 120 --retries 5 -q -e .
pip install --timeout 120 --retries 5 -q pytest pytest-asyncio respx

# --- 13. Run tests ---
echo "Running tests..."
python -m pytest tests/unit -v 2>&1 | tee /workspace/logs/test-results.log | tail -3 || true
TEST_COUNT=$(tail -1 /workspace/logs/test-results.log 2>/dev/null | grep -oE '[0-9]+ passed.*' || echo "unknown")
echo "  Tests: $TEST_COUNT"

# --- 14. Start OpenClaw gateway ---
echo "Starting OpenClaw gateway..."
export OPENCLAW_VERBOSE=1
nohup openclaw gateway run > /workspace/logs/openclaw-gateway.log 2>&1 &
GATEWAY_PID=$!
echo "$GATEWAY_PID" > /workspace/state/gateway.pid
sleep 5
if kill -0 "$GATEWAY_PID" 2>/dev/null; then
    echo "  ✅ OpenClaw gateway running (PID $GATEWAY_PID)"
else
    echo "  ⚠️  Gateway may not have started"
fi

# --- 15. Startup notification ---
tg_send "🏭 *Gasclaw Maintainer online*

*Gastown Workspace:*
• Location: /workspace/gt
• Dolt: $(cat /workspace/gt/.dolt-data/dolt.pid 2>/dev/null && echo 'running' || echo 'unknown')
• Daemon: $(pgrep -f 'gt daemon' > /dev/null && echo 'running' || echo 'unknown')

*Tests:* ${TEST_COUNT}
*Skills:* $(ls "$OPENCLAW_SKILLS/" 2>/dev/null | wc -l) installed

Ready to work." discussion

# --- 16. Background status loop ---
STATUS_INTERVAL=$(python3 /opt/scripts/config-loader.py --get telegram.status_interval 2>/dev/null || echo "900")
echo "Starting status loop (interval=${STATUS_INTERVAL}s)..."

export MAINTENANCE_REPO
export STATUS_GROUP_ID="-1003759869133"
export STATUS_THREAD_ID="114"

# Send initial status
bash /opt/scripts/gastown-status.sh 2>/dev/null || echo "Initial status failed"

# Background loop
(
    while true; do
        sleep "$STATUS_INTERVAL"
        bash /opt/scripts/gastown-status.sh 2>/dev/null || true
    done
) &
STATUS_LOOP_PID=$!
echo "$STATUS_LOOP_PID" > /workspace/state/status-loop.pid
echo "Status loop running (PID $STATUS_LOOP_PID)"

# --- 17. Graceful shutdown ---
cleanup() {
    echo "Shutting down..."
    [ -f /workspace/state/gateway.pid ] && kill "$(cat /workspace/state/gateway.pid)" 2>/dev/null || true
    [ -f /workspace/state/status-loop.pid ] && kill "$(cat /workspace/state/status-loop.pid)" 2>/dev/null || true
    tg_send "🏭 *Gasclaw Maintainer shutting down*"
    exit 0
}
trap cleanup SIGTERM SIGINT

# --- 18. Maintenance loop ---
echo ""
echo "Starting maintenance loop (interval=${MAINTENANCE_INTERVAL}s)..."

CYCLE=0
while true; do
    if [ -f /workspace/state/paused ]; then
        sleep 30
        continue
    fi

    # Gateway watchdog
    if [ -f /workspace/state/gateway.pid ]; then
        GATEWAY_PID=$(cat /workspace/state/gateway.pid)
        if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
            echo "Gateway died, restarting..."
            nohup openclaw gateway run > /workspace/logs/openclaw-gateway.log 2>&1 &
            GATEWAY_PID=$!
            echo "$GATEWAY_PID" > /workspace/state/gateway.pid
            echo "Gateway restarted (PID $GATEWAY_PID)"
        fi
    fi

    CYCLE=$((CYCLE + 1))
    echo ""
    echo "=== Maintenance cycle #${CYCLE} ($(date -Iseconds)) ==="

    MAINTAINER_PROMPT='You are the gasclaw repo maintainer. Read CLAUDE.md first.

Your maintenance loop:
1. Check PRs: gh pr list --repo '"${MAINTENANCE_REPO}"' --state open
2. For EACH open PR: checkout, test, merge if passing
3. Check issues: gh issue list --repo '"${MAINTENANCE_REPO}"' --state open
4. Fix open issues: branch, implement, create PR, merge
5. Improve test coverage

Rules: branch naming (fix/, feat/, test/), run tests before commit, TDD.

Start now. Check and merge open PRs first.'

    cd /workspace/gasclaw
    source .venv/bin/activate

    claude --dangerously-skip-permissions -p "$MAINTAINER_PROMPT" \
        >> /workspace/logs/claude-code.log 2>&1 &
    CLAUDE_PID=$!
    echo "$CLAUDE_PID" > /workspace/state/claude.pid

    # Write maintenance state
    python3 -c "
import json, datetime
state_file = '/workspace/state/maintenance.json'
try:
    with open(state_file) as f:
        state = json.load(f)
except:
    state = {'total_cycles': 0, 'total_prs_merged': 0}
state['status'] = 'running'
state['last_run'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
state['total_cycles'] = state.get('total_cycles', 0) + 1
state['cycle'] = $CYCLE
with open(state_file, 'w') as f:
    json.dump(state, f, indent=2)
"

    wait "$CLAUDE_PID" || true
    rm -f /workspace/state/claude.pid

    # Update state to completed
    python3 -c "
import json, datetime
with open('/workspace/state/maintenance.json') as f:
    state = json.load(f)
state['status'] = 'idle'
state['last_completed'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
with open('/workspace/state/maintenance.json', 'w') as f:
    json.dump(state, f, indent=2)
"

    echo "Cycle #${CYCLE} complete. Sleeping ${MAINTENANCE_INTERVAL}s..."
    sleep "$MAINTENANCE_INTERVAL"
done
