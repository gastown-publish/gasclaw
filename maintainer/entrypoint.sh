#!/bin/bash
set -euo pipefail

echo "=== Gasclaw Maintainer Agent ==="
echo ""

# --- Auth ---
echo "$GITHUB_TOKEN" | gh auth login --with-token
git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"
git config --global user.email "gasclaw-bot@gastown.dev"
git config --global user.name "Gasclaw Maintainer"

# --- Kimi K2.5 as Claude backend ---
export ANTHROPIC_BASE_URL="https://api.kimi.com/coding/"
export ANTHROPIC_API_KEY="${KIMI_API_KEY}"
export DISABLE_COST_WARNINGS=true

# --- Claude Code config (isolated, API key auth) ---
export CLAUDE_CONFIG_DIR="/workspace/.claude-config"
mkdir -p "$CLAUDE_CONFIG_DIR"
echo '{}' > "$CLAUDE_CONFIG_DIR/.credentials.json"
cat > "$CLAUDE_CONFIG_DIR/.claude.json" <<CJSON
{
  "hasCompletedOnboarding": true,
  "bypassPermissionsModeAccepted": true,
  "customApiKeyResponses": {
    "approved": ["${KIMI_API_KEY: -20}"]
  }
}
CJSON

# --- Clone repo ---
echo "Cloning gasclaw..."
git clone https://github.com/gastown-publish/gasclaw.git /workspace/gasclaw
cd /workspace/gasclaw

# --- Dev setup ---
echo "Setting up dev environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" --quiet 2>/dev/null || pip install -e . --quiet

# --- Verify tests pass ---
echo "Running tests..."
python -m pytest tests/unit -v

# --- Launch Claude Code as maintainer ---
echo ""
echo "Starting Claude Code maintainer loop..."
exec claude --dangerously-skip-permissions \
  -p "$(cat <<'PROMPT'
You are the gasclaw repo maintainer. Read CLAUDE.md first.

Your continuous maintenance loop:

1. **Check issues**: `gh issue list --repo gastown-publish/gasclaw --state open`
2. **Check PRs**: `gh pr list --repo gastown-publish/gasclaw`
3. **Review open PRs**: For each PR, review code quality, run tests, approve or request changes
4. **Fix open issues**: Branch, implement with tests, create PR
5. **Improve test coverage**: Find untested paths, add edge case tests
6. **Code quality**: Run `make lint`, fix issues, improve types/error handling
7. **Report issues**: If you find bugs you can't fix in one PR, file an issue

After completing each task, move to the next. When all tasks done, look for improvements.

Rules:
- Always branch from latest main: `git checkout main && git pull`
- Branch naming: fix/, feat/, test/, docs/, refactor/
- Run `make test` before every commit
- One concern per PR, keep PRs small (<200 lines)
- Never push to main directly — always use PRs
- Write tests first (TDD)

Start now. Begin by reading CLAUDE.md, then check issues and PRs.
PROMPT
)'
