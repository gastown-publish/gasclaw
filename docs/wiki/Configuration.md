# Configuration

All configuration is via environment variables. No secrets are hardcoded.

## Required Variables

| Variable | Format | Description |
|----------|--------|-------------|
| `GASTOWN_KIMI_KEYS` | `sk-xxx:sk-yyy:sk-zzz` | Colon-separated Kimi API keys for Gastown agents |
| `OPENCLAW_KIMI_KEY` | `sk-xxx` | Kimi API key for OpenClaw overseer (separate pool) |
| `TELEGRAM_BOT_TOKEN` | `123456:ABC-DEF` | Telegram bot token from @BotFather |
| `TELEGRAM_OWNER_ID` | `123456789` | Numeric Telegram user ID |

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GT_RIG_URL` | `/project` | Git URL or path for project rig |
| `GT_AGENT_COUNT` | `6` | Number of crew workers |
| `PROJECT_DIR` | `/project` | Directory for git activity checks |
| `MONITOR_INTERVAL` | `300` | Health check interval (seconds) |
| `ACTIVITY_DEADLINE` | `3600` | Max seconds between commits |
| `DOLT_PORT` | `3307` | Dolt SQL server port |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |

## Setup

```bash
cp .env.example .env
# Edit .env with your real keys
```

## Key Separation

Gastown and OpenClaw use **completely separate** key pools:

| Pool | Env Var | Used By |
|------|---------|---------|
| Gastown | `GASTOWN_KIMI_KEYS` | Mayor, Crew, Daemon |
| OpenClaw | `OPENCLAW_KIMI_KEY` | Overseer bot |

Never put the same key in both pools. This ensures the overseer always works even when agent keys are rate-limited.

## Validation

Gasclaw validates on startup:
- `TELEGRAM_OWNER_ID` must be numeric
- `GASTOWN_KIMI_KEYS` must contain at least one `sk-` prefixed key
- `TELEGRAM_BOT_TOKEN` must match `digits:alphanumeric` format

## Secrets Management

- `.env` files are gitignored
- Never commit real API keys
- Use Docker secrets or environment injection in production
- Keys tracked internally by BLAKE2b hash, never logged in plaintext
