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

## Secrets Management

### Keeping Keys Secure

Never commit API keys to git. Use one of these approaches:

**Option 1: Environment File (Recommended for development)**

```bash
# .env file (add to .gitignore!)
GASTOWN_KIMI_KEYS="sk-..."
OPENCLAW_KIMI_KEY="sk-..."
TELEGRAM_BOT_TOKEN="..."
TELEGRAM_OWNER_ID="..."
```

**Option 2: Docker Secrets**

```yaml
# docker-compose.yml
secrets:
  kimi_keys:
    file: ./secrets/kimi_keys.txt
  openclaw_key:
    file: ./secrets/openclaw_key.txt
```

**Option 3: Environment Variables in Production**

```bash
# Systemd service or init script
export GASTOWN_KIMI_KEYS="$(cat /etc/gasclaw/kimi_keys)"
export OPENCLAW_KIMI_KEY="$(cat /etc/gasclaw/openclaw_key)"
```

### Key Permissions

Ensure key files have restricted permissions:

```bash
chmod 600 .env
chmod 600 /etc/gasclaw/*
```

## Multi-Key Configuration

### Why Multiple Keys?

Gasclaw supports multiple Kimi API keys for several reasons:

1. **Rate Limit Distribution** - Each key has its own rate limit; spreading load prevents throttling
2. **Redundancy** - If one key is rate-limited or revoked, others continue working
3. **Cost Tracking** - Separate keys per project or team for billing purposes
4. **Isolation** - Gastown agents and OpenClaw use completely separate key pools

### Key Pool Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Gasclaw                               │
├─────────────────────────────────────────────────────────────┤
│  Gastown Agents                                             │
│  ├── Key Pool: GASTOWN_KIMI_KEYS                            │
│  │   ├── sk-key1 (worker 1)                                 │
│  │   ├── sk-key2 (worker 2)                                 │
│  │   └── sk-key3 (worker 3)                                 │
│  └── Rotation: LRU with 5-min cooldown on rate limits       │
├─────────────────────────────────────────────────────────────┤
│  OpenClaw (Overseer)                                        │
│  ├── Key Pool: OPENCLAW_KIMI_KEY (single key)               │
│  │   └── sk-overseer-key                                    │
│  └── Never shares pool with Gastown                         │
└─────────────────────────────────────────────────────────────┘
```

### How Key Rotation Works

1. **LRU Selection** - Least recently used key is selected first
2. **Cooldown** - Rate-limited keys are excluded for 5 minutes
3. **Automatic Retry** - If all keys rate-limited, pool resets and tries again

### Best Practices

1. **Use Separate Keys** - Never share keys between Gastown and OpenClaw
2. **Monitor Usage** - Check Kimi dashboard for per-key usage
3. **Budget Alerts** - Set up spending alerts on Kimi for each key
4. **Rotate Regularly** - Refresh keys monthly for security

### Troubleshooting Key Issues

**"Keys exhausted" error:**
```bash
# Check key status in logs
gasclaw status

# All keys rate-limited - wait 5 minutes or add more keys
```

**Invalid key errors:**
```bash
# Verify key format (should start with sk-)
echo "$GASTOWN_KIMI_KEYS" | tr ':' '\n' | head -1

# Test a key directly
curl -H "Authorization: Bearer sk-your-key" \
  https://api.kimi.com/v1/users/me/balance
```
