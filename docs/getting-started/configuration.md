# Configuration

Gasclaw uses environment variables for all configuration. This makes it easy to deploy in containers and keeps secrets out of code.

## Required Variables

### GASTOWN_KIMI_KEYS

Colon-separated list of Kimi API keys for Gastown agents.

```bash
export GASTOWN_KIMI_KEYS="sk-abc123:sk-def456:sk-ghi789"
```

Each key corresponds to one agent account. The more keys you provide, the more agents can run in parallel.

### OPENCLAW_KIMI_KEY

Kimi API key for OpenClaw (the overseer). This should be different from the Gastown keys.

```bash
export OPENCLAW_KIMI_KEY="sk-overseer-key"
```

!!! note "Separate Key Pool"
    OpenClaw uses a separate key pool from Gastown agents. This ensures the overseer can always function even if all agent keys are rate-limited.

### TELEGRAM_BOT_TOKEN

Your Telegram bot token from @BotFather.

```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
```

### TELEGRAM_OWNER_ID

Your Telegram user ID (numeric). The bot will only respond to messages from this user.

```bash
export TELEGRAM_OWNER_ID="2045995148"
```

!!! tip "Finding Your User ID"
    Message @userinfobot on Telegram to get your user ID.

## Optional Variables

### GT_RIG_URL

Git URL or path for the Gastown rig (project repository).

```bash
export GT_RIG_URL="/project"           # Local path
export GT_RIG_URL="https://github.com/user/repo"  # Git URL
```

**Default:** `/project`

### GT_AGENT_COUNT

Number of crew worker agents to run.

```bash
export GT_AGENT_COUNT=6
```

**Default:** `6`

### MONITOR_INTERVAL

Seconds between health checks.

```bash
export MONITOR_INTERVAL=300  # 5 minutes
```

**Default:** `300` (5 minutes)

### ACTIVITY_DEADLINE

Maximum seconds allowed between code commits. If no activity is detected within this window, an alert is sent.

```bash
export ACTIVITY_DEADLINE=3600  # 1 hour
```

**Default:** `3600` (1 hour)

### DOLT_PORT

Port for the Dolt SQL server.

```bash
export DOLT_PORT=3307
```

**Default:** `3307`

### PROJECT_DIR

Directory for git activity checks.

```bash
export PROJECT_DIR="/workspace/gasclaw"
```

**Default:** `/project`

## Example Configuration

Create a `.env` file:

```bash
# Required
GASTOWN_KIMI_KEYS="sk-key1:sk-key2:sk-key3"
OPENCLAW_KIMI_KEY="sk-overseer"
TELEGRAM_BOT_TOKEN="123:ABC"
TELEGRAM_OWNER_ID="999999999"

# Optional (with defaults shown)
GT_RIG_URL="/project"
GT_AGENT_COUNT=6
MONITOR_INTERVAL=300
ACTIVITY_DEADLINE=3600
DOLT_PORT=3307
```

Load it with:

```bash
set -a && source .env && set +a
```

## Validation

Gasclaw validates configuration on startup:

- `TELEGRAM_OWNER_ID` must be numeric
- `GASTOWN_KIMI_KEYS` must contain at least one valid key
- Path variables should be absolute paths

If validation fails, the bootstrap will exit with a clear error message.
