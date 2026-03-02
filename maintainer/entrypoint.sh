#!/bin/bash
set -euo pipefail

echo "=== Gasclaw Maintainer Agent ==="
echo ""

# --- Auth ---
echo "$GITHUB_TOKEN" | gh auth login --with-token --hostname github.com 2>&1 || true
gh auth status 2>&1 || true
git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"
git config --global user.email "gasclaw-bot@gastown.dev"
git config --global user.name "Gasclaw Maintainer"

# --- Kimi K2.5 as Claude backend ---
export ANTHROPIC_BASE_URL="https://api.kimi.com/coding/"
export ANTHROPIC_API_KEY="${KIMI_API_KEY}"
export DISABLE_COST_WARNINGS=true

# --- Telegram config (from env, set in .env / docker-compose) ---
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN is required}"
: "${TELEGRAM_CHAT_ID:?TELEGRAM_CHAT_ID is required}"

# --- Claude Code config (isolated, API key auth) ---
export CLAUDE_CONFIG_DIR="/workspace/.claude-config"
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

# --- Helper: send Telegram message ---
tg_send() {
    curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d parse_mode=Markdown \
        -d text="$1" > /dev/null 2>&1 || true
}

# --- Clone repo ---
echo "Cloning gasclaw..."
if [ -d /workspace/gasclaw/.git ]; then
    cd /workspace/gasclaw && git pull origin main
else
    git clone https://github.com/gastown-publish/gasclaw.git /workspace/gasclaw
    cd /workspace/gasclaw
fi

# --- Dev setup ---
echo "Setting up dev environment..."
python3 -m venv .venv
source .venv/bin/activate
echo "Upgrading pip..."
pip install --upgrade pip --timeout 120 --retries 5
echo "Installing gasclaw + deps..."
pip install --timeout 120 --retries 5 -e .
echo "Installing test deps..."
pip install --timeout 120 --retries 5 pytest pytest-asyncio respx

# --- Verify tests pass (non-fatal, bot can fix failures) ---
echo "Running tests..."
TEST_COUNT=$(python -m pytest tests/unit -v 2>&1 | tail -1)
echo "$TEST_COUNT"
tg_send "🔄 *Gasclaw Maintainer starting*
Tests: ${TEST_COUNT}"

# --- Launch Claude Code as maintainer ---
echo ""
echo "Starting Claude Code maintainer loop..."

MAINTAINER_PROMPT='You are the gasclaw repo maintainer with FULL merge authority. Read CLAUDE.md first.

TELEGRAM REPORTING: After every significant action, send a Telegram update using this command:
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" -d chat_id="${TELEGRAM_CHAT_ID}" -d parse_mode=Markdown -d text="YOUR_MESSAGE"

Send updates for: PR created, PR merged, issue fixed, tests status, errors encountered.

Your continuous maintenance loop:

1. Check PRs: gh pr list --repo gastown-publish/gasclaw --state open
2. For EACH open PR:
   a. Check out the branch: gh pr checkout <number>
   b. Run tests: python -m pytest tests/unit -v
   c. If tests pass: merge it immediately with gh pr merge <number> --squash --delete-branch
   d. If tests fail: fix the issues on the branch, push, then merge
   e. After merging: git checkout main and git pull
   f. Send Telegram update: "Merged PR #N: title"
3. Check issues: gh issue list --repo gastown-publish/gasclaw --state open
4. Fix open issues: Branch, implement with tests, create PR, then immediately merge it
5. Improve test coverage: Find untested paths, add edge case tests, create PR, merge it
6. Code quality: Fix lint issues, improve types/error handling, create PR, merge it
7. Report issues: If you find bugs you cannot fix in one PR, file an issue

IMPORTANT: You have merge authority. After creating a PR, verify tests pass, then merge it yourself using gh pr merge --squash --delete-branch. Do not leave PRs open.

After completing each task, move to the next. When all tasks done, send a Telegram summary and look for improvements.

Rules:
- Always branch from latest main: git checkout main and git pull
- Branch naming: fix/, feat/, test/, docs/, refactor/
- Run python -m pytest tests/unit -v before every commit
- One concern per PR, keep PRs small (under 200 lines)
- Never push to main directly, always use PRs, then merge them
- Write tests first (TDD)
- Always merge your own PRs after tests pass
- Send Telegram updates after each action

Start now. Begin by reading CLAUDE.md, then check and merge any open PRs first.'

exec claude --dangerously-skip-permissions -p "$MAINTAINER_PROMPT"
