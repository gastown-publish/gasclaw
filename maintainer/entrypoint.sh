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

# --- 4. Kimi K2.5 as Claude Code backend ---
export ANTHROPIC_BASE_URL="${KIMI_BASE_URL}"
export ANTHROPIC_API_KEY="${KIMI_API_KEY}"
export DISABLE_COST_WARNINGS=true

# --- 5. Claude Code config (isolated, API key auth) ---
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
    curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d parse_mode=Markdown \
        -d text="$1" > /dev/null 2>&1 || true
}

# --- 7. Run openclaw doctor FIRST (before writing our config) ---
echo "Running OpenClaw doctor..."
OPENCLAW_DIR="$HOME/.openclaw"
mkdir -p "$OPENCLAW_DIR/agents/main/agent"
mkdir -p "$OPENCLAW_DIR/agents/main/sessions"
openclaw doctor --fix --yes 2>&1 || true

# --- 8. Write OpenClaw config AFTER doctor (so doctor can't strip it) ---
echo "Writing OpenClaw config..."

# Create agent workspace on bind mount (persists across restarts)
AGENT_WORKSPACE="/workspace/agent-workspace"
mkdir -p "$AGENT_WORKSPACE"

# Copy SOUL.md (agent identity — always refresh from image)
cp /opt/agent-soul.md "$AGENT_WORKSPACE/SOUL.md"

# Copy BOOTSTRAP.md (operational instructions — always refresh from image)
cp /opt/agent-bootstrap.md "$AGENT_WORKSPACE/BOOTSTRAP.md"

# Don't overwrite MEMORY.md if it exists (agent-generated, persists across restarts)
if [ ! -f "$AGENT_WORKSPACE/MEMORY.md" ]; then
    echo "# Gasclaw Maintainer Memory" > "$AGENT_WORKSPACE/MEMORY.md"
    echo "" >> "$AGENT_WORKSPACE/MEMORY.md"
    echo "This file is updated by the agent. Do not edit manually." >> "$AGENT_WORKSPACE/MEMORY.md"
fi

echo "Agent workspace: $AGENT_WORKSPACE (SOUL.md + BOOTSTRAP.md + MEMORY.md)"

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

# Read existing config to preserve doctor-generated fields (meta, auth token, etc.)
cfg_path = os.path.join(openclaw_dir, "openclaw.json")
existing = {}
if os.path.exists(cfg_path):
    with open(cfg_path) as f:
        existing = json.load(f)

# Merge our config on top (our values win)
# NOTE: No "instructions" key — OpenClaw loads context from workspace files
# (SOUL.md, BOOTSTRAP.md, MEMORY.md) in the agent workspace directory
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
# Telegram: support both DM and group
telegram_allow = [os.environ["TELEGRAM_CHAT_ID"]]
group_id = os.environ.get("TELEGRAM_GROUP_ID", "").strip()
if group_id:
    telegram_allow.append(group_id)

config["channels"] = {
    "telegram": {
        "botToken": os.environ["TELEGRAM_BOT_TOKEN"],
        "dmPolicy": "allowlist",
        "allowFrom": telegram_allow,
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

print("OpenClaw config written (models.json + openclaw.json — workspace-based context)")
PYEOF

# --- 9. Install skills ---
echo "Installing OpenClaw skills..."
OPENCLAW_SKILLS="$OPENCLAW_DIR/skills"
mkdir -p "$OPENCLAW_SKILLS"
if [ -d /opt/maintainer-skills ]; then
    cp -r /opt/maintainer-skills/* "$OPENCLAW_SKILLS/" 2>/dev/null || true
    find "$OPENCLAW_SKILLS" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
    echo "Installed skills: $(ls "$OPENCLAW_SKILLS/" 2>/dev/null | tr '\n' ' ')"
fi

# --- 10. Clone/update repo ---
echo "Cloning gasclaw..."
if [ -d /workspace/gasclaw/.git ]; then
    cd /workspace/gasclaw && git pull origin main 2>&1 || true
else
    git clone "https://github.com/${MAINTENANCE_REPO}.git" /workspace/gasclaw
    cd /workspace/gasclaw
fi

# --- 11. Dev setup (venv persists on bind mount) ---
echo "Setting up dev environment..."
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip --timeout 120 --retries 5 -q
pip install --timeout 120 --retries 5 -q -e .
pip install --timeout 120 --retries 5 -q pytest pytest-asyncio respx

# --- 12. Run tests (non-fatal — bot can fix failures) ---
echo "Running tests..."
python -m pytest tests/unit -v 2>&1 | tee /workspace/logs/test-results.log | tail -3 || true
TEST_COUNT=$(tail -1 /workspace/logs/test-results.log 2>/dev/null || echo "unknown")
echo "Tests: $TEST_COUNT"

# --- 13. Start OpenClaw gateway ---
echo "Starting OpenClaw gateway..."
nohup openclaw gateway run > /workspace/logs/openclaw-gateway.log 2>&1 &
GATEWAY_PID=$!
echo "$GATEWAY_PID" > /workspace/state/gateway.pid
sleep 5
if kill -0 "$GATEWAY_PID" 2>/dev/null; then
    echo "OpenClaw gateway running (PID $GATEWAY_PID)"
else
    echo "WARNING: OpenClaw gateway failed to start"
    cat /workspace/logs/openclaw-gateway.log 2>/dev/null | tail -10 || true
fi

# --- 14. Startup notification ---
tg_send "🏭 *Gasclaw Maintainer online*
Tests: ${TEST_COUNT}
Skills: $(ls "$OPENCLAW_SKILLS/" 2>/dev/null | wc -l) installed
Config: /workspace/config/gasclaw.yaml
Maintenance interval: ${MAINTENANCE_INTERVAL}s
Ready to work."

# --- 15. Graceful shutdown ---
cleanup() {
    echo "Shutting down..."
    [ -f /workspace/state/claude.pid ] && kill "$(cat /workspace/state/claude.pid)" 2>/dev/null || true
    [ -f /workspace/state/gateway.pid ] && kill "$(cat /workspace/state/gateway.pid)" 2>/dev/null || true
    tg_send "🏭 *Gasclaw Maintainer shutting down*"
    exit 0
}
trap cleanup SIGTERM SIGINT

# --- 16. Maintenance loop ---
echo ""
echo "Starting maintenance loop (interval=${MAINTENANCE_INTERVAL}s)..."

MAINTAINER_PROMPT='You are the gasclaw repo maintainer with FULL merge authority. Read CLAUDE.md first.

TELEGRAM REPORTING: After every significant action, send a Telegram update using this command:
curl -s "https://api.telegram.org/bot'"${TELEGRAM_BOT_TOKEN}"'/sendMessage" -d chat_id="'"${TELEGRAM_CHAT_ID}"'" -d parse_mode=Markdown -d text="YOUR_MESSAGE"

Send updates for: PR created, PR merged, issue fixed, tests status, errors encountered.

Your continuous maintenance loop:

1. Check PRs: gh pr list --repo '"${MAINTENANCE_REPO}"' --state open
2. For EACH open PR:
   a. Check out the branch: gh pr checkout <number>
   b. Run tests: python -m pytest tests/unit -v
   c. If tests pass: merge it immediately with gh pr merge <number> --squash --delete-branch
   d. If tests fail: fix the issues on the branch, push, then merge
   e. After merging: git checkout main and git pull
   f. Send Telegram update
3. Check issues: gh issue list --repo '"${MAINTENANCE_REPO}"' --state open
4. Fix open issues: Branch, implement with tests, create PR, then merge
5. Improve test coverage
6. Code quality improvements

IMPORTANT: You have merge authority. Merge your own PRs with gh pr merge --squash --delete-branch.

Rules:
- Always branch from latest main
- Branch naming: fix/, feat/, test/, docs/, refactor/
- Run python -m pytest tests/unit -v before every commit
- One concern per PR, keep PRs small (under 200 lines)
- Never push to main directly
- TDD: Write tests first
- Send Telegram updates after each action

Start now. Read CLAUDE.md, then check and merge open PRs first.'

CYCLE=0
while true; do
    # Check if paused
    if [ -f /workspace/state/paused ]; then
        sleep 30
        continue
    fi

    # Re-read interval from config (allows hot changes)
    MAINTENANCE_INTERVAL=$(python3 /opt/scripts/config-loader.py --get maintenance.loop_interval 2>/dev/null || echo "300")

    # Check for manual trigger
    TRIGGERED=false
    if [ -f /workspace/state/trigger-now ]; then
        rm -f /workspace/state/trigger-now
        TRIGGERED=true
        echo "Manual trigger detected!"
    fi

    CYCLE=$((CYCLE + 1))
    echo ""
    echo "=== Maintenance cycle #${CYCLE} ($(date -Iseconds)) ==="

    # Run Claude Code maintenance
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
except (FileNotFoundError, json.JSONDecodeError):
    state = {'total_cycles': 0, 'total_prs_merged': 0}
state['status'] = 'running'
state['last_run'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
state['total_cycles'] = state.get('total_cycles', 0) + 1
state['cycle'] = $CYCLE
with open(state_file, 'w') as f:
    json.dump(state, f, indent=2)
"

    # Wait for Claude Code to finish
    wait "$CLAUDE_PID" || true
    rm -f /workspace/state/claude.pid

    # --- Post-cycle: detect changes and send Telegram report ---
    export CYCLE_NUM=$CYCLE
    export MAINTENANCE_REPO
    CYCLE_REPORT=$(python3 << 'REPORT_EOF'
import subprocess, json, datetime, os

repo = os.environ.get("MAINTENANCE_REPO", "gastown-publish/gasclaw")
cycle = os.environ.get("CYCLE_NUM", "?")

# Get PRs merged in the last 10 minutes
try:
    result = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--state", "merged",
         "--json", "number,title,mergedAt", "--limit", "20"],
        capture_output=True, text=True, timeout=30
    )
    merged_prs = json.loads(result.stdout) if result.returncode == 0 else []
except Exception:
    merged_prs = []

# Filter to recently merged (last 15 min)
now = datetime.datetime.now(datetime.timezone.utc)
recent = []
for pr in merged_prs:
    try:
        merged_at = datetime.datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00"))
        if (now - merged_at).total_seconds() < 900:  # 15 min
            recent.append(pr)
    except Exception:
        pass

# Get open issue count
try:
    result = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "open", "--json", "number"],
        capture_output=True, text=True, timeout=30
    )
    open_issues = len(json.loads(result.stdout)) if result.returncode == 0 else "?"
except Exception:
    open_issues = "?"

# Get open PR count
try:
    result = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--state", "open", "--json", "number"],
        capture_output=True, text=True, timeout=30
    )
    open_prs = len(json.loads(result.stdout)) if result.returncode == 0 else "?"
except Exception:
    open_prs = "?"

# Build message
lines = [f"🏭 *Maintenance cycle #{cycle} complete*"]

if recent:
    lines.append(f"\n*Merged {len(recent)} PR(s):*")
    for pr in recent:
        lines.append(f"  • #{pr['number']} {pr['title']}")

if not recent:
    lines.append("\nNo PRs merged this cycle.")

lines.append(f"\n📊 Open: {open_prs} PRs, {open_issues} issues")
print("\n".join(lines))
REPORT_EOF
    )

    if [ -n "$CYCLE_REPORT" ]; then
        export CYCLE_NUM=$CYCLE
        tg_send "$CYCLE_REPORT"
        echo "$CYCLE_REPORT"
    fi

    # Update state to completed
    python3 -c "
import json, datetime
state_file = '/workspace/state/maintenance.json'
with open(state_file) as f:
    state = json.load(f)
state['status'] = 'idle'
state['last_completed'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
with open(state_file, 'w') as f:
    json.dump(state, f, indent=2)
"

    echo "Cycle #${CYCLE} complete. Sleeping ${MAINTENANCE_INTERVAL}s..."
    sleep "$MAINTENANCE_INTERVAL"
done
